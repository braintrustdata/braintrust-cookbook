"""Cookbook: import HuggingFace agent traces into Braintrust as Logs.

A worked example, not a maintained tool. To use it:
  1. edit the EDIT ME block — repo/split, which columns hold the id / trace /
     metadata / scores, and (if your traces aren't OTel-GenAI) the attribute keys.
  2. run `python cookbook/import_logs.py` to write the JSONL and see the counts.
  3. set PUSH = True (or pass --push) to run `bt sync push` for you.

Each row becomes a span tree: one root `task` span per session, one child `llm`
span per LLM call. Root span IDs are deterministic (uuid5 of the session id), so
re-importing the same session upserts instead of duplicating — which is also how
you write scores back onto existing spans (join the score on as a column, map it
in SCORE_COLS, re-run).

Needs BRAINTRUST_API_KEY in the environment (to resolve the project and push)
and the `bt` CLI on PATH for the push step.
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from braintrust_logs import bt_sync_push, build_spans, resolve_project, write_spans_jsonl
from normalize import TraceKeys

load_dotenv()

# ── EDIT ME ───────────────────────────────────────────────────────────────────
HF_REPO = "Exgentic/agent-llm-traces"
HF_SPLIT = "train"
LIMIT = None                       # cap rows while iterating, or None for all

BT_PROJECT = "Hugging Face topics"  # must already exist in Braintrust

ID_COL = "session_id"              # stable id per session (drives the root span id)
TRACE_COL = "spans"               # column holding the list of OTel spans
METADATA_COLS = ["benchmark", "harness", "models", "total_tokens"]
SCORE_COLS: dict[str, str] = {}    # {"task_success": "judge_task_success"} — root-span scores

# Attribute keys for reading each span. Defaults follow the OTel GenAI
# conventions; override only if your trace dataset uses different keys.
KEYS = TraceKeys()

OUT_DIR = "out/logs"               # where the bt-sync JSONL is written
PUSH = False                       # False = write JSONL only; True = also `bt sync push`
# ── /EDIT ME ──────────────────────────────────────────────────────────────────


def load_rows():
    from datasets import load_dataset

    kwargs = {"split": HF_SPLIT, "streaming": True}
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if token:
        kwargs["token"] = token
    ds = load_dataset(HF_REPO, **kwargs)
    for i, row in enumerate(ds):
        if LIMIT is not None and i >= LIMIT:
            break
        yield dict(row)


def main(push: bool) -> None:
    project_id, org_id = resolve_project(BT_PROJECT)
    source = {"hf_dataset": HF_REPO, "hf_split": HF_SPLIT}

    spans = build_spans(
        load_rows(),
        project_id=project_id,
        org_id=org_id,
        id_col=ID_COL,
        trace_col=TRACE_COL,
        metadata_cols=METADATA_COLS,
        score_cols=SCORE_COLS,
        keys=KEYS,
        source=source,
    )

    sessions, span_count, out_path = write_spans_jsonl(spans, OUT_DIR)
    print(f"wrote {span_count} spans across {sessions} sessions → {out_path}")

    if push:
        bt_sync_push(OUT_DIR, BT_PROJECT)
        print(f"pushed to project_logs:{BT_PROJECT}")
    else:
        print("(no push; set PUSH=True or pass --push to run `bt sync push`)")


if __name__ == "__main__":
    main(push=PUSH or "--push" in sys.argv)
