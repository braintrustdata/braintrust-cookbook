"""Direct Loom memory retrieval for a three-case Braintrust component evaluation."""

import json
import os
import re
import time
from dataclasses import dataclass
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

FACTS = (
    (
        "exports",
        "The sample invoice export starts at 02:00 UTC.",
        "When does the sample invoice export start?",
    ),
    (
        "retry",
        "The sample image worker retries transient timeouts three times.",
        "How many times does the sample image worker retry a transient timeout?",
    ),
    (
        "reviews",
        "The sample access review checks tenant isolation before approval.",
        "What does the sample access review check before approval?",
    ),
)


@dataclass(frozen=True)
class Config:
    url: str
    org: str
    namespace: str
    token: str

    @classmethod
    def from_env(cls):
        config = cls(
            *(
                os.environ[name]
                for name in (
                    "LOOM_BASE_URL",
                    "LOOM_ORG",
                    "LOOM_NAMESPACE",
                    "LOOM_API_KEY",
                )
            )
        )
        parsed = urlsplit(config.url)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "LOOM_BASE_URL must be an HTTPS base URL without credentials or query"
            )
        if not all((config.org, config.namespace, config.token)):
            raise ValueError("Loom configuration must be nonempty")
        return config


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LoomHTTP:
    def __init__(self, config):
        self.config = config
        self.opener = build_opener(NoRedirect())

    def post(self, operation, body, *, request_id=None):
        if operation not in {"memory.set", "memory.search", "memory.delete_version"}:
            raise ValueError("Operation is outside this recipe")
        request_id = request_id or str(uuid4())
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", request_id):
            raise ValueError("Invalid request ID")
        request = Request(
            self.config.url.rstrip("/") + "/v1/" + operation,
            data=json.dumps(body).encode(),
            method="POST",
            headers={
                "Authorization": "Bearer " + self.config.token,
                "Content-Type": "application/json",
                "X-Request-Id": request_id,
            },
        )
        started = time.monotonic()
        status, data, error = 0, None, ""
        try:
            try:
                response = self.opener.open(request, timeout=30)
            except HTTPError as exc:
                response = exc
            with response:
                status = response.code
                raw = response.read(1_048_577)
            if len(raw) > 1_048_576:
                error = "RESPONSE_TOO_LARGE"
            else:
                try:
                    data = json.loads(raw)
                except (ValueError, UnicodeError):
                    error = "INVALID_JSON"
                if not isinstance(data, dict):
                    data, error = None, "INVALID_RESPONSE"
        except (URLError, TimeoutError, OSError, HTTPException):
            error = "NETWORK_ERROR"
        return {
            "http_status": status,
            "request_id": request_id,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "transport_error": error,
            "data": data,
        }


def metadata(response):
    result = {
        key: response[key]
        for key in ("http_status", "request_id", "elapsed_ms", "transport_error")
    }
    data = response["data"] or {}
    error = data.get("error", data.get("detail", {}))
    if isinstance(error, dict):
        code = error.get("code")
        if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", code):
            result["error_code"] = code
    degraded = data.get("degraded", [])
    result["degraded_component_count"] = (
        len(degraded) if isinstance(degraded, list) else 1
    )
    result["provider_usage"] = None
    return result


def succeeded(response):
    return (
        200 <= response["http_status"] < 300
        and not response["transport_error"]
        and isinstance(response["data"], dict)
    )


def append_event(path, event):
    with Path(path).open("a", encoding="utf-8") as file:
        file.write(json.dumps(event) + "\n")
        file.flush()
        os.fsync(file.fileno())


def canonical_version(value):
    if type(value) is int and 0 < value < 2**64:
        return str(value)
    if (
        isinstance(value, str)
        and len(value) <= 20
        and re.fullmatch(r"[1-9][0-9]*", value)
        and int(value) < 2**64
    ):
        return value
    return None


def seed(client, journal):
    """Explicit fixture creation; persist each response before the next write."""
    run_tag = "loom-retrieval-" + uuid4().hex
    identity = {
        "org": client.config.org,
        "namespace": client.config.namespace,
        "agent": run_tag,
        "user_id": "-",
        "session_id": run_tag,
    }
    plan = {
        "kind": "run",
        "tag": run_tag,
        "identity": identity,
        "cases": [
            {"input": query, "expected": run_tag + "/" + slug}
            for slug, value, query in FACTS
        ],
    }
    fd = os.open(journal, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        file.write(json.dumps(plan) + "\n")
        file.flush()
        os.fsync(file.fileno())
    for slug, value, query in FACTS:
        key = run_tag + "/" + slug
        request_id = str(uuid4())
        append_event(
            journal,
            {
                "kind": "seed_intent",
                "operation": "memory.set",
                "key": key,
                "request_id": request_id,
            },
        )
        response = client.post(
            "memory.set",
            {
                **identity,
                "memory_key": key,
                "memory_type": "semantic",
                "value": value,
                "tags": [run_tag],
                "ttl_seconds": 86400,
            },
            request_id=request_id,
        )
        data = response["data"] or {}
        event = {"kind": "seed", "key": key, "metadata": metadata(response)}
        version = canonical_version(data.get("version"))
        if (
            succeeded(response)
            and version is not None
            and data.get("memory_key") == key
            and data.get("namespace") == identity["namespace"]
            and data.get("memory_id")
            and not data.get("merged_into_key")
        ):
            event["receipt"] = {"memory_key": key, "version": version}
        event["ready"] = (
            "receipt" in event
            and data.get("status") == "active"
            and not event["metadata"]["degraded_component_count"]
        )
        append_event(journal, event)
        if not event["ready"]:
            raise RuntimeError(
                "Fixture seed incomplete; inspect the local journal before evaluation"
            )
    return plan


def load_run(client, journal, require_complete=True):
    events = [json.loads(line) for line in Path(journal).read_text().splitlines()]
    run = events[0]
    tag = run.get("tag", "")
    if (
        run.get("kind") != "run"
        or not re.fullmatch(r"loom-retrieval-[0-9a-f]{32}", tag)
        or run.get("identity")
        != {
            "org": client.config.org,
            "namespace": client.config.namespace,
            "agent": tag,
            "user_id": "-",
            "session_id": tag,
        }
    ):
        raise ValueError("Journal identity does not match this fixture run")
    expected = {tag + "/" + slug for slug, value, query in FACTS}
    cases = [
        {"input": query, "expected": tag + "/" + slug} for slug, value, query in FACTS
    ]
    if run.get("cases") != cases:
        raise ValueError("Journal cases do not match the synthetic fixture")
    receipts = []
    for event in events[1:]:
        receipt = event.get("receipt") if event.get("kind") == "seed" else None
        if receipt:
            if (
                receipt.get("memory_key") not in expected
                or not isinstance(receipt.get("version"), str)
                or canonical_version(receipt["version"]) != receipt["version"]
            ):
                raise ValueError("Invalid fixture receipt")
            receipts.append(receipt)
    if len({r["memory_key"] for r in receipts}) != len(receipts):
        raise ValueError("Duplicate fixture receipts")
    if require_complete and (
        {r["memory_key"] for r in receipts} != expected
        or any(e.get("kind") == "cleanup" for e in events)
        or any(e.get("kind") == "seed" and not e.get("ready") for e in events)
    ):
        raise ValueError("Evaluation needs three acknowledged fixtures before cleanup")
    return run, receipts


def retrieve(client, run, query):
    response = client.post(
        "memory.search",
        {
            **run["identity"],
            "query": query,
            "memory_type": "semantic",
            "tags": [run["tag"]],
            "namespace_scope": "this",
            "scope": "private",
            "top_k": 3,
            "include_tags": True,
            "auto_touch": False,
            "legs": ["memory"],
            "explain": False,
        },
    )
    result = {"status": "request_failed", "keys": [], "metadata": metadata(response)}
    if not succeeded(response):
        return result
    data = response["data"]
    hits = data.get("results")
    partial = data.get("degraded", [])
    abstain = data.get("abstain", False)
    if (
        not isinstance(partial, list)
        or not all(isinstance(item, str) for item in partial)
        or type(abstain) is not bool
    ):
        result["status"] = "invalid_scope_or_response"
        return result
    allowed = {case["expected"] for case in run["cases"]}
    if (
        not isinstance(hits, list)
        or data.get("namespaces_searched") != [client.config.namespace]
        or any(
            not isinstance(hit, dict)
            or hit.get("memory_key") not in allowed
            or not isinstance(hit.get("tags"), list)
            or run["tag"] not in hit["tags"]
            for hit in hits
        )
    ):
        result["status"] = "invalid_scope_or_response"
        return result
    result["keys"] = [hit["memory_key"] for hit in hits]
    result["metadata"]["degraded_component_count"] = (
        len(partial) if isinstance(partial, list) else 1
    )
    count = data.get("tokens_returned")
    result["metadata"]["estimated_body_tokens"] = (
        count if type(count) is int and count >= 0 else None
    )
    result["metadata"]["provider_usage"] = None
    result["status"] = "partial" if partial else ("abstained" if abstain else "ok")
    return result


def retrieval_score(output, expected):
    complete = output["status"] in {"ok", "abstained"}
    top = output["keys"][0] if output["keys"] else None
    return {
        "name": "expected_key_at_1",
        "score": float(top == expected and output["status"] == "ok")
        if complete
        else None,
        "metadata": {"status": output["status"]},
    }


def cleanup(client, journal):
    """Explicit exact-version cleanup; failures stay in the journal for inspection."""
    run, receipts = load_run(client, journal, require_complete=False)
    results = []
    for index, receipt in enumerate(receipts):
        response = client.post("memory.delete_version", {**run["identity"], **receipt})
        data = response["data"] or {}
        result = {
            "kind": "cleanup",
            "key": receipt["memory_key"],
            "requested_version": receipt["version"],
            "metadata": metadata(response),
            "tombstoned": data.get("tombstoned") is True,
            "version_changed": data.get("reason") == "version_changed",
        }
        complete = succeeded(response) and type(data.get("tombstoned")) is bool
        result["status"] = "complete" if complete else "request_failed_or_unknown"
        result["remaining_pending"] = len(receipts) - index - int(complete)
        append_event(journal, result)
        results.append(result)
        if not complete:
            break
    return results
