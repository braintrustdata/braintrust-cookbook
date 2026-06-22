"""Build a Braintrust span tree from trace rows and push it via ``bt sync push``.

The non-obvious part of the logs recipe: one root ``task`` span per session, one
child ``llm`` span per LLM call, with deterministic IDs so re-importing the same
session *upserts* instead of duplicating. The import script decides which columns
hold the id / trace / metadata / scores and passes them in — there's no config
object or inference here.
"""
from __future__ import annotations

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import requests

from normalize import (
    TraceKeys,
    cap_metadata,
    detect_failures,
    extract_final_output,
    extract_task_input,
    normalize_messages,
    parse_messages,
    redact,
    to_unix,
)

API_URL = os.environ.get("BRAINTRUST_API_URL", "https://api.braintrust.dev").rstrip("/")


def resolve_project(name: str) -> tuple[str, str]:
    """Resolve ``(project_id, org_id)`` from a project name via the Braintrust API.

    Reads ``BRAINTRUST_API_KEY`` from the environment; never logs it.
    """
    key = os.environ.get("BRAINTRUST_API_KEY")
    if not key:
        raise RuntimeError("BRAINTRUST_API_KEY not set; required to resolve a project.")
    resp = requests.get(
        f"{API_URL}/v1/project",
        headers={"Authorization": f"Bearer {key}"},
        params={"project_name": name},
        timeout=60,
    )
    resp.raise_for_status()
    objs = resp.json().get("objects", [])
    if not objs:
        raise ValueError(f"No Braintrust project named {name!r}")
    return objs[0]["id"], objs[0]["org_id"]


def _build_scores(row: dict[str, Any], score_cols: dict[str, str]) -> Optional[dict[str, float]]:
    """Pull ``{score_name: float}`` from a row. Missing/non-numeric values are skipped."""
    scores: dict[str, float] = {}
    for name, col in score_cols.items():
        val = row.get(col)
        if val is None or isinstance(val, bool):
            continue
        try:
            scores[name] = float(val)
        except (TypeError, ValueError):
            continue
    return scores or None


def _make_span(**kw: Any) -> dict:
    """Assemble one Braintrust span dict from keyword fields."""
    return {
        "id": kw["span_id"],
        "span_id": kw["span_id"],
        "root_span_id": kw["root_span_id"],
        "span_parents": kw.get("span_parents"),
        "is_root": kw.get("is_root", False),
        "input": kw.get("input_data"),
        "output": kw.get("output_data"),
        "metadata": kw.get("metadata") or {},
        "metrics": kw.get("metrics") or {},
        "error": kw.get("error"),
        "expected": None,
        "scores": kw.get("scores"),
        "tags": None,
        "created": kw["created"],
        "log_id": "g",
        "org_id": kw["org_id"],
        "project_id": kw["project_id"],
        "span_attributes": {"exec_counter": kw["exec_counter"], "name": kw["name"], "type": kw["span_type"]},
    }


def session_to_spans(
    row: dict[str, Any],
    *,
    project_id: str,
    org_id: str,
    id_col: Optional[str] = None,
    trace_col: Optional[str] = None,
    metadata_cols: Iterable[str] = (),
    score_cols: Optional[dict[str, str]] = None,
    keys: TraceKeys = TraceKeys(),
    source: Optional[dict[str, Any]] = None,
    max_str: int = 4000,
    max_metadata_bytes: int = 16384,
) -> list[dict]:
    """Convert one row to a list of span dicts (root + one child per LLM call)."""
    score_cols = score_cols or {}
    session_id = str(row.get(id_col) if id_col and row.get(id_col) else uuid.uuid4())
    collected = row.get("collected_at") or datetime.now(timezone.utc).isoformat()
    if hasattr(collected, "isoformat"):
        collected = collected.isoformat()

    metadata_base = {c: row.get(c) for c in metadata_cols if c in row}
    if source:
        metadata_base = {**metadata_base, **source}  # provenance wins on key clash
    root_scores = _build_scores(row, score_cols)
    root_span_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"root:{session_id}"))

    spans_raw = row.get(trace_col) if trace_col else None

    # No trace column / empty trace — a single root span carrying just metadata.
    if not spans_raw:
        return [
            _make_span(
                span_id=root_span_id,
                root_span_id=root_span_id,
                is_root=True,
                name=str(session_id),
                span_type="task",
                input_data=None,
                output_data=None,
                metadata=cap_metadata({**metadata_base, "session_id": session_id}, max_metadata_bytes),
                created=str(collected),
                exec_counter=1,
                project_id=project_id,
                org_id=org_id,
                scores=root_scores,
            )
        ]

    spans_raw = sorted(spans_raw, key=lambda s: to_unix(s.get(keys.start_time)))
    first_attrs = spans_raw[0].get(keys.attributes) or {}
    session_start = to_unix(spans_raw[0].get(keys.start_time))
    session_end = to_unix(spans_raw[-1].get(keys.end_time))

    task_input = extract_task_input(first_attrs, keys, max_str=max_str)

    final_out = {"role": "assistant", "content": "(no output found)"}
    for span in reversed(spans_raw):
        candidate = extract_final_output(span.get(keys.attributes) or {}, keys, max_str=max_str)
        if candidate["content"] != "(no output found)":
            final_out = candidate
            break

    failures = detect_failures(spans_raw, keys)
    if failures.has_errors:
        examples = f" Examples: {'; '.join(failures.sample_errors)}" if failures.sample_errors else ""
        error_summary = (
            f"[{failures.error_span_count} error span(s); {failures.tool_error_count} tool error(s) detected.{examples}]"
        )
        root_output = {"role": "assistant", "content": final_out["content"], "issues": error_summary}
        root_error = error_summary
    else:
        root_output, root_error = final_out, None

    root_metadata = cap_metadata(
        {
            **metadata_base,
            "session_id": session_id,
            "num_llm_calls": len(spans_raw),
            "has_errors": failures.has_errors,
            "tool_error_count": failures.tool_error_count,
            "error_span_count": failures.error_span_count,
        },
        max_metadata_bytes,
    )

    root_span = _make_span(
        span_id=root_span_id,
        root_span_id=root_span_id,
        is_root=True,
        name=str(session_id),
        span_type="task",
        input_data=task_input,
        output_data=root_output,
        metadata=root_metadata,
        metrics={"start": session_start, "end": session_end},
        created=str(collected),
        exec_counter=1,
        project_id=project_id,
        org_id=org_id,
        scores=root_scores,
        error=root_error,
    )
    result = [root_span]

    for i, span in enumerate(spans_raw, start=2):
        attrs = span.get(keys.attributes) or {}
        child_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"child:{session_id}:{i}:{span.get('span_id', '')}"))
        child_input = normalize_messages(parse_messages(attrs.get(keys.input_messages)), max_str=max_str)
        child_output = normalize_messages(parse_messages(attrs.get(keys.output_messages)), max_str=max_str)
        if len(child_input) > 20:
            child_input = child_input[-20:]
        if len(child_output) > 5:
            child_output = child_output[-5:]

        in_tok = attrs.get(keys.input_tokens) or 0
        out_tok = attrs.get(keys.output_tokens) or 0

        result.append(
            _make_span(
                span_id=child_id,
                root_span_id=root_span_id,
                span_parents=[root_span_id],
                name=span.get(keys.span_name) or "llm-call",
                span_type="llm",
                input_data=child_input,
                output_data=child_output,
                metadata={"model": attrs.get(keys.request_model)},
                metrics={
                    "start": to_unix(span.get(keys.start_time)),
                    "end": to_unix(span.get(keys.end_time)),
                    "prompt_tokens": in_tok,
                    "completion_tokens": out_tok,
                    "tokens": in_tok + out_tok,
                },
                created=str(collected),
                exec_counter=i,
                project_id=project_id,
                org_id=org_id,
            )
        )

    return result


def build_spans(rows: Iterable[dict[str, Any]], *, do_redact: bool = True, **kw: Any) -> Iterable[dict]:
    """Yield span dicts for every row. Remaining kwargs go to :func:`session_to_spans`."""
    for row in rows:
        for span in session_to_spans(row, **kw):
            yield redact(span) if do_redact else span


def write_spans_jsonl(spans: Iterable[dict], out_dir: str | Path) -> tuple[int, int, Path]:
    """Write spans to ``<out_dir>/part-000001.jsonl``. Returns (sessions, spans, path)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "part-000001.jsonl"
    span_count = session_count = 0
    with open(out_path, "w") as fout:
        for span in spans:
            if span.get("is_root"):
                session_count += 1
            fout.write(json.dumps(span, default=str) + "\n")
            span_count += 1
    return session_count, span_count, out_path


def bt_sync_push(out_dir: str | Path, project_name: str) -> None:
    """Shell out to ``bt sync push`` for the written JSONL directory."""
    subprocess.run(
        ["bt", "sync", "push", f"project_logs:{project_name}", "--in", str(out_dir), "--no-input"],
        check=True,
    )
