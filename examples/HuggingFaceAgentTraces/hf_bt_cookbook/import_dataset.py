"""Cookbook: import a HuggingFace dataset into Braintrust as a Dataset.

A worked example, not a maintained tool. To use it:
  1. edit the EDIT ME block — the repo/split and the `to_record` mapping.
  2. run `python cookbook/import_dataset.py` to preview the first few records.
  3. set PUSH = True (or pass --push) to actually write to Braintrust.

A Braintrust Dataset is rows of {input, expected, metadata} — the thing you run
and score evals against. (For agent traces you want to analyze instead, see
import_logs.py.)

Needs BRAINTRUST_API_KEY in the environment to push (read by the SDK, never by
this script). HF_TOKEN is optional — only for gated/private datasets.
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

# Reusable helpers — only needed for the chat / traces-as-expected mappings below.
from normalize import normalize_messages, parse_messages  # noqa: F401

load_dotenv()

# ── EDIT ME ───────────────────────────────────────────────────────────────────
HF_REPO = "openai/gsm8k"
HF_SUBSET = "main"   # dataset config name, or None
HF_SPLIT = "test"
LIMIT = None         # cap the number of rows while iterating, or None for all

BT_PROJECT = "hf-imports"
BT_DATASET = "gsm8k"

PUSH = False         # False = preview only; True = write to Braintrust (or pass --push)


def to_record(row: dict, i: int) -> dict:
    """Map one HuggingFace row → one Braintrust dataset record.

    Return {id, input, expected, metadata}. `expected` is optional. This is the
    one function you rewrite per dataset — the column names below are the whole
    "mapping" the old tool tried to infer.
    """
    return {
        "id": str(row.get("task_id") or i),
        "input": row["question"],
        "expected": row["answer"],
        "metadata": {
            # provenance: where this row came from
            "hf_dataset": HF_REPO,
            "hf_subset": HF_SUBSET,
            "hf_split": HF_SPLIT,
        },
    }


# Other mappings you'll commonly want — drop one in over `to_record` above:
#
#   # chat-formatted prompt (a column that's a list of {role, content}):
#   "input": normalize_messages(parse_messages(row["messages"])),
#
#   # several columns into metadata:
#   "metadata": {"category": row["category"], "difficulty": row["difficulty"]},
#
#   # traces-as-expected — turn a recorded trace into a gradable example
#   # (lift the task into input and the recorded final answer into expected);
#   # see import_logs.py for the trace helpers (extract_task_input/_final).
# ── /EDIT ME ──────────────────────────────────────────────────────────────────


def load_rows():
    from datasets import load_dataset

    args = [HF_REPO] + ([HF_SUBSET] if HF_SUBSET else [])
    kwargs = {"split": HF_SPLIT, "streaming": True}
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if token:
        kwargs["token"] = token
    ds = load_dataset(*args, **kwargs)
    for i, row in enumerate(ds):
        if LIMIT is not None and i >= LIMIT:
            break
        yield i, dict(row)


def main(push: bool) -> None:
    if not push:
        import json

        print(f"# preview — {HF_REPO} (no writes; set PUSH=True or pass --push to import)\n")
        for i, row in load_rows():
            if i >= 3:
                break
            print(json.dumps(to_record(row, i), indent=2, default=str))
        return

    import braintrust

    dataset = braintrust.init_dataset(project=BT_PROJECT, name=BT_DATASET)
    n = 0
    for i, row in load_rows():
        dataset.insert(**to_record(row, i))
        n += 1
    dataset.flush()
    print(f"inserted {n} records into {BT_PROJECT}/{BT_DATASET}")
    try:
        print(dataset.summarize().dataset_url)
    except Exception:
        pass


if __name__ == "__main__":
    main(push=PUSH or "--push" in sys.argv)
