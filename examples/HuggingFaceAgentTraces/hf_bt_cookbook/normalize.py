"""Chat / OTel / trace normalization — the fiddly bits worth not rewriting.

This is the one piece of the cookbook you import rather than copy inline: turning
loose or OpenTelemetry-GenAI message shapes into OpenAI-style
``{role, content, tool_calls?}`` messages, and pulling task/output/failure info
out of a list of trace spans.

It also carries a few small safety helpers (truncate, redact, byte-cap) so the
import scripts can apply them explicitly where they want to.

Nothing here reads or prints secrets; Braintrust/HF keys are read from the
environment by their own SDKs.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# ── small safety helpers ──────────────────────────────────────────────────────

DEFAULT_MAX_STR = 8000
DEFAULT_MAX_METADATA_BYTES = 16384


def truncate_str(value: str, max_len: int = DEFAULT_MAX_STR) -> str:
    """Truncate a string to ``max_len`` chars, marking that it was cut."""
    if max_len <= 0 or len(value) <= max_len:
        return value
    marker = " …[truncated]"
    keep = max(0, max_len - len(marker))
    return value[:keep] + marker


def safe_json_loads(raw: str) -> Any:
    """Plain ``json.loads`` — raises on bad input so the caller decides what to do."""
    return json.loads(raw)


# Conservative patterns for common credential shapes — a best-effort backstop,
# not a guarantee. Better to miss an exotic token than corrupt real content.
_SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),              # OpenAI / Braintrust style
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),               # HuggingFace token
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                  # AWS access key id
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),               # GitHub PAT
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}\b"),  # bearer tokens
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),      # Slack tokens
]
_REDACTED = "[REDACTED]"


def redact(value: Any) -> Any:
    """Recursively replace known secret shapes with ``[REDACTED]``."""
    if isinstance(value, str):
        out = value
        for pat in _SECRET_PATTERNS:
            out = pat.sub(_REDACTED, out)
        return out
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def cap_metadata(metadata: dict[str, Any], max_bytes: int = DEFAULT_MAX_METADATA_BYTES) -> dict[str, Any]:
    """Drop metadata keys (largest first) until the JSON payload fits ``max_bytes``.

    Records what was dropped under ``_dropped_keys`` so the cut is visible.
    """
    if max_bytes <= 0:
        return dict(metadata)

    def size(d: dict[str, Any]) -> int:
        return len(json.dumps(d, default=str).encode("utf-8"))

    out = dict(metadata)
    if size(out) <= max_bytes:
        return out

    dropped: list[str] = []
    for key in sorted(out, key=lambda k: len(json.dumps(out[k], default=str).encode("utf-8")), reverse=True):
        if key == "_dropped_keys":
            continue
        del out[key]
        dropped.append(key)
        out["_dropped_keys"] = dropped
        if size(out) <= max_bytes:
            break
    return out


# ── trace attribute keys ────────────────────────────────────────────────────


@dataclass(frozen=True)
class TraceKeys:
    """Attribute/field names used to read a trace span.

    Defaults match the OpenTelemetry GenAI conventions (e.g. the
    Exgentic/agent-llm-traces dataset). Override for other trace schemas.
    """

    input_messages: str = "gen_ai.input.messages"
    output_messages: str = "gen_ai.output.messages"
    request_model: str = "gen_ai.request.model"
    input_tokens: str = "gen_ai.usage.input_tokens"
    output_tokens: str = "gen_ai.usage.output_tokens"
    start_time: str = "start_time"
    end_time: str = "end_time"
    attributes: str = "attributes"
    status: str = "status"
    span_name: str = "name"


# ── timestamps ──────────────────────────────────────────────────────────────

_TS_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f+00:00",
    "%Y-%m-%dT%H:%M:%S+00:00",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
)


def to_unix(ts: Any) -> float:
    """Convert an ISO timestamp string / datetime / number to a Unix float."""
    if ts is None:
        return 0.0
    if isinstance(ts, (int, float)):
        return float(ts)
    if hasattr(ts, "timestamp"):
        return ts.timestamp()
    text = str(ts)
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            continue
    return 0.0


# ── message parsing ───────────────────────────────────────────────────────


def parse_messages(raw: Any) -> list[dict]:
    """Parse a messages field that may be a JSON string or an already-parsed list.

    Malformed JSON is kept as a single raw-text message so the row survives.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [m for m in raw if isinstance(m, dict)]
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, str):
        try:
            parsed = safe_json_loads(raw)
        except json.JSONDecodeError:
            return [{"role": "unknown", "content": raw}]
        if isinstance(parsed, list):
            return [m for m in parsed if isinstance(m, dict)]
        if isinstance(parsed, dict):
            return [parsed]
    return []


def normalize_message(msg: dict, *, max_str: int = 8000) -> list[dict]:
    """Convert an OTel parts-format message to OpenAI-compatible message(s).

    OTel:   {"role": "user", "parts": [{"type": "text", "content": "..."}]}
    OpenAI: {"role": "user", "content": "..."}

    Returns a list because one OTel message may yield several OpenAI messages
    (e.g. tool-result parts become their own messages).
    """
    role = msg.get("role", "user")
    parts = msg.get("parts") or []
    content = msg.get("content")

    if not parts and isinstance(content, str):
        return [{"role": role, "content": truncate_str(content, max_str)}]

    text_parts: list[str] = []
    tool_calls: list[dict] = []
    tool_results: list[dict] = []

    for part in parts:
        if not isinstance(part, dict):
            text_parts.append(str(part))
            continue
        ptype = part.get("type", "text")
        if ptype == "text":
            text_parts.append(part.get("content") or part.get("text") or "")
        elif ptype == "tool_call":
            args = part.get("arguments", {})
            tool_calls.append(
                {
                    "id": part.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": part.get("name", ""),
                        "arguments": json.dumps(args) if isinstance(args, dict) else str(args),
                    },
                }
            )
        elif ptype in ("tool_result", "tool_call_response"):
            raw_content = part.get("content") or part.get("result") or ""
            if isinstance(raw_content, list):
                texts = [r.get("text") or r.get("content") or "" for r in raw_content if isinstance(r, dict)]
                text_content = " ".join(texts)
            else:
                text_content = str(raw_content)
            tool_results.append(
                {"role": "tool", "tool_call_id": part.get("id", ""), "content": truncate_str(text_content, 1000)}
            )

    result: list[dict] = []

    if role in ("user", "human"):
        if tool_results:
            combined = "\n---\n".join(f"[tool result] {tr['content']}" for tr in tool_results)
            result.append({"role": "user", "content": truncate_str(combined, max_str)})
        else:
            text = " ".join(text_parts).strip() or (str(content) if content else "")
            if text:
                result.append({"role": "user", "content": truncate_str(text, max_str)})

    elif role == "assistant":
        text = " ".join(text_parts).strip() or (content if isinstance(content, str) else None)
        entry: dict[str, Any] = {"role": "assistant", "content": truncate_str(text, max_str) if text else None}
        if tool_calls:
            entry["tool_calls"] = tool_calls
        if entry.get("content") is not None or entry.get("tool_calls"):
            result.append(entry)

    elif role == "system":
        text = " ".join(text_parts).strip() or str(content or "")
        result.append({"role": "system", "content": truncate_str(text, max_str)})

    return result or [{"role": role, "content": ""}]


def normalize_messages(msgs: list, *, max_str: int = 8000) -> list[dict]:
    """Normalize a list of OTel/loose messages to OpenAI format."""
    out: list[dict] = []
    for msg in msgs:
        if isinstance(msg, dict):
            out.extend(normalize_message(msg, max_str=max_str))
    return out


# ── trace-level extraction ──────────────────────────────────────────────────


def extract_task_input(first_attrs: dict, keys: TraceKeys, *, max_str: int = 4000) -> dict:
    """Pull the first meaningful user message from the first LLM call's input."""
    messages = parse_messages(first_attrs.get(keys.input_messages))
    task_msgs = [m for m in messages if m.get("role") != "system"]
    if task_msgs:
        msg = task_msgs[0]
        content = msg.get("content") or msg.get("parts", "")
        if isinstance(content, list):
            text_parts = [
                p.get("content") or p.get("text") or "" if isinstance(p, dict) else str(p) for p in content
            ]
            content = " ".join(text_parts)
        return {"role": "user", "content": truncate_str(str(content), max_str)}
    return {"role": "user", "content": "(no task content found)"}


def extract_final_output(last_attrs: dict, keys: TraceKeys, *, max_str: int = 4000) -> dict:
    """Pull the assistant's final response from an LLM call's output.

    Falls back through: text parts → direct content → tool-call summary → empty.
    """
    messages = parse_messages(last_attrs.get(keys.output_messages))
    assistant_msgs = [m for m in messages if m.get("role") == "assistant"]

    def extract_from_msg(msg: dict) -> str:
        parts = msg.get("parts") or []
        text_parts = [
            p.get("content") or p.get("text") or ""
            for p in parts
            if isinstance(p, dict) and p.get("type") == "text"
        ]
        if text_parts:
            return " ".join(text_parts)
        direct = msg.get("content")
        if direct and isinstance(direct, str) and direct.strip():
            return direct
        tool_parts = [p for p in parts if isinstance(p, dict) and p.get("type") == "tool_call"]
        if tool_parts:
            tools = ", ".join(p.get("name", "tool") for p in tool_parts)
            return f"[tool calls: {tools}]"
        return ""

    for msg in reversed(assistant_msgs):
        text = extract_from_msg(msg)
        if text:
            return {"role": "assistant", "content": truncate_str(str(text), max_str)}

    return {"role": "assistant", "content": "(no output found)"}


@dataclass
class FailureSummary:
    has_errors: bool = False
    error_span_count: int = 0
    tool_error_count: int = 0
    sample_errors: list[str] = field(default_factory=list)


def detect_failures(spans_raw: list[dict], keys: TraceKeys) -> FailureSummary:
    """Scan spans for OTel error status codes and tool-result error messages."""
    error_spans = 0
    tool_errors: list[str] = []

    for span in spans_raw:
        status = span.get(keys.status) or {}
        if isinstance(status, dict) and status.get("code") == 2:  # OTel ERROR
            error_spans += 1

        attrs = span.get(keys.attributes) or {}
        for msg in parse_messages(attrs.get(keys.input_messages)):
            for part in msg.get("parts") or []:
                if not isinstance(part, dict):
                    continue
                if part.get("type") not in ("tool_call_response", "tool_result"):
                    continue
                raw_result = part.get("result") or part.get("content") or ""
                if isinstance(raw_result, list):
                    texts = [r.get("text") or r.get("content") or "" for r in raw_result if isinstance(r, dict)]
                    text = " ".join(texts)
                else:
                    text = str(raw_result)
                if text.lower().startswith("error"):
                    tool_errors.append(text[:200])

    seen: set[str] = set()
    unique: list[str] = []
    for err in tool_errors:
        if err not in seen:
            seen.add(err)
            unique.append(err)

    return FailureSummary(
        has_errors=error_spans > 0 or len(tool_errors) > 0,
        error_span_count=error_spans,
        tool_error_count=len(tool_errors),
        sample_errors=unique[:5],
    )
