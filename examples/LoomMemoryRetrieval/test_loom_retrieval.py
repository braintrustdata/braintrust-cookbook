"""Offline contracts for scoping, disclosure, skipped scores, and fixture receipts."""

import json
import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from loom_retrieval import (
    FACTS,
    Config,
    LoomHTTP,
    cleanup,
    load_run,
    retrieval_score,
    retrieve,
    seed,
)


class FakeLoom:
    config = Config(
        "https://loom.example", "fixture-org", "fixture-namespace", "not-a-token"
    )

    def __init__(self):
        self.calls = []
        self.response = None
        self.fail_seed_at = None

    def post(self, operation, body, *, request_id=None):
        self.calls.append((operation, body))
        data = self.response
        status = 200
        if data is None:
            if operation == "memory.set":
                status = 409 if len(self.calls) == self.fail_seed_at else 200
                data = {
                    "memory_key": body["memory_key"],
                    "namespace": body["namespace"],
                    "memory_id": "synthetic-id",
                    "version": 1700000000000000001,
                    "status": "active",
                }
            else:
                data = {"tombstoned": True}
        return {
            "http_status": status,
            "request_id": request_id or "synthetic-request",
            "elapsed_ms": 1.0,
            "transport_error": "",
            "data": data,
        }


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal = Path(self.temp.name) / "fixture.jsonl"
        self.client = FakeLoom()
        self.run = seed(self.client, self.journal)
        self.client.calls.clear()

    def hit(self, key=None):
        return {
            "memory_key": key or self.run["cases"][0]["expected"],
            "tags": [self.run["tag"]],
            "content_excerpt": "MUST NOT BE LOGGED",
        }

    def response(self, **updates):
        return {
            "results": [self.hit()],
            "namespaces_searched": [self.client.config.namespace],
            "tokens_returned": 12,
            **updates,
        }

    def test_search_is_one_tag_one_identity_and_omits_values(self):
        self.client.response = self.response()
        result = retrieve(self.client, self.run, FACTS[0][2])
        operation, body = self.client.calls[0]
        self.assertEqual(operation, "memory.search")
        self.assertEqual(body["tags"], [self.run["tag"]])
        self.assertEqual(body["namespace_scope"], "this")
        self.assertEqual(body["agent"], self.run["identity"]["agent"])
        self.assertEqual(body["session_id"], self.run["identity"]["session_id"])
        self.assertEqual(body["legs"], ["memory"])
        self.assertFalse(body["auto_touch"])
        serialized = json.dumps(result)
        self.assertNotIn("MUST NOT", serialized)
        self.assertNotIn(self.client.config.namespace, serialized)
        self.assertEqual(result["metadata"]["estimated_body_tokens"], 12)
        self.assertIsNone(result["metadata"]["provider_usage"])
        self.assertEqual(
            retrieval_score(result, self.run["cases"][0]["expected"])["score"], 1
        )

    def test_unrelated_key_is_never_disclosed(self):
        self.client.response = self.response(
            results=[self.hit("PRIVATE_UNRELATED_KEY")]
        )
        result = retrieve(self.client, self.run, FACTS[0][2])
        self.assertEqual(result["status"], "invalid_scope_or_response")
        self.assertEqual(result["keys"], [])
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertIsNone(retrieval_score(result, "anything")["score"])

    def test_foreign_namespace_and_tag_are_rejected(self):
        for changes in (
            {"namespaces_searched": ["other"]},
            {"results": [{**self.hit(), "tags": ["other"]}]},
        ):
            self.client.response = self.response(**changes)
            self.assertEqual(retrieve(self.client, self.run, FACTS[0][2])["keys"], [])

    def test_partial_preserves_receipt_but_skips_accuracy(self):
        self.client.response = self.response(degraded=["PRIVATE_DIAGNOSTIC"])
        result = retrieve(self.client, self.run, FACTS[0][2])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["metadata"]["degraded_component_count"], 1)
        self.assertEqual(len(result["keys"]), 1)
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertIsNone(retrieval_score(result, result["keys"][0])["score"])

    def test_abstention_is_a_miss_even_if_a_hit_is_returned(self):
        self.client.response = self.response(abstain=True)
        result = retrieve(self.client, self.run, FACTS[0][2])
        self.assertEqual(retrieval_score(result, result["keys"][0])["score"], 0)

    def test_refusal_preserves_safe_error_code(self):
        self.client.response = {
            "error": {"code": "SESSION_PROTECTION_REQUIRED", "message": "PRIVATE"}
        }
        original = self.client.post

        def refused(operation, body, **options):
            return {**original(operation, body, **options), "http_status": 409}

        with patch.object(self.client, "post", side_effect=refused):
            result = retrieve(self.client, self.run, FACTS[0][2])
        self.assertEqual(
            result["metadata"]["error_code"], "SESSION_PROTECTION_REQUIRED"
        )
        self.assertEqual(result["metadata"]["http_status"], 409)
        self.assertIsNone(retrieval_score(result, "anything")["score"])
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_exact_version_cleanup_preserves_integer_precision(self):
        results = cleanup(self.client, self.journal)
        self.assertEqual(len(results), 3)
        for operation, body in self.client.calls:
            self.assertEqual(operation, "memory.delete_version")
            self.assertEqual(body["version"], "1700000000000000001")
            self.assertTrue(body["memory_key"].startswith(self.run["tag"] + "/"))
        with self.assertRaises(ValueError):
            load_run(self.client, self.journal)

    def test_changed_version_is_reported_without_broad_delete(self):
        self.client.response = {"tombstoned": False, "reason": "version_changed"}
        results = cleanup(self.client, self.journal)
        self.assertTrue(all(r["version_changed"] for r in results))
        self.assertFalse(any(r["tombstoned"] for r in results))
        self.assertEqual(len(self.client.calls), 3)

    def test_journal_identity_mismatch_prevents_cleanup(self):
        self.client.config = Config(
            "https://loom.example", "other-org", "fixture-namespace", "not-a-token"
        )
        with self.assertRaises(ValueError):
            cleanup(self.client, self.journal)
        self.assertEqual(self.client.calls, [])

    def test_partial_seed_keeps_prior_receipts_without_automatic_cleanup(self):
        path = Path(self.temp.name) / "partial.jsonl"
        client = FakeLoom()
        client.fail_seed_at = 2
        with self.assertRaisesRegex(RuntimeError, "seed incomplete"):
            seed(client, path)
        self.assertEqual([op for op, _ in client.calls], ["memory.set", "memory.set"])
        with self.assertRaises(ValueError):
            load_run(client, path)
        client.calls.clear()
        results = cleanup(client, path)
        self.assertEqual(len(results), 1)
        self.assertEqual(client.calls[0][0], "memory.delete_version")

    def test_degraded_seed_retains_receipt_and_blocks_evaluation(self):
        path = Path(self.temp.name) / "degraded.jsonl"
        original = self.client.post

        def degraded(operation, body, **options):
            response = original(operation, body, **options)
            response["data"]["degraded"] = ["PRIVATE"]
            return response

        with (
            patch.object(self.client, "post", side_effect=degraded),
            self.assertRaises(RuntimeError),
        ):
            seed(self.client, path)
        with self.assertRaises(ValueError):
            load_run(self.client, path)
        self.assertNotIn("PRIVATE", path.read_text())
        self.assertEqual(len(load_run(self.client, path, require_complete=False)[1]), 1)

    def test_cleanup_stops_on_first_refusal_and_keeps_remaining_receipts(self):
        original = self.client.post

        def refused(operation, body, **options):
            response = original(operation, body, **options)
            response["http_status"] = 409
            response["data"] = {"error": {"code": "SESSION_PROTECTION_REQUIRED"}}
            return response

        with patch.object(self.client, "post", side_effect=refused):
            results = cleanup(self.client, self.journal)
        self.assertEqual(len(self.client.calls), 1)
        self.assertEqual(results[0]["status"], "request_failed_or_unknown")
        self.assertEqual(results[0]["remaining_pending"], 3)
        self.assertEqual(
            len(load_run(self.client, self.journal, require_complete=False)[1]), 3
        )

    def test_cleanup_stops_on_unknown_network_outcome(self):
        original = self.client.post

        def disconnected(operation, body, **options):
            return {
                **original(operation, body, **options),
                "http_status": 0,
                "transport_error": "NETWORK_ERROR",
                "data": None,
            }

        with patch.object(self.client, "post", side_effect=disconnected):
            results = cleanup(self.client, self.journal)
        self.assertEqual(len(self.client.calls), 1)
        self.assertEqual(results[0]["remaining_pending"], 3)

    def test_decimal_string_acknowledgement_preserves_version(self):
        path = Path(self.temp.name) / "string-version.jsonl"
        original = self.client.post

        def string_version(operation, body, **options):
            response = original(operation, body, **options)
            response["data"]["version"] = "1700000000000000001"
            return response

        with patch.object(self.client, "post", side_effect=string_version):
            seed(self.client, path)
        self.assertEqual(
            load_run(self.client, path)[1][0]["version"], "1700000000000000001"
        )

    def test_invalid_acknowledgement_versions_are_not_cleanup_targets(self):
        from loom_retrieval import canonical_version

        for value in (True, 1.7e18, "01", "-1", str(2**64), 0):
            self.assertIsNone(canonical_version(value))

    def test_malformed_health_fields_skip_accuracy_and_completion(self):
        for field, values in (
            ("degraded", (None, False, {}, "", [False])),
            ("abstain", (None, 0, {}, "false")),
        ):
            for value in values:
                with self.subTest(field=field, value=value):
                    self.client.response = self.response(**{field: value})
                    result = retrieve(self.client, self.run, FACTS[0][2])
                    self.assertEqual(result["status"], "invalid_scope_or_response")
                    self.assertEqual(result["keys"], [])
                    self.assertIsNone(
                        retrieval_score(result, self.run["cases"][0]["expected"])[
                            "score"
                        ]
                    )
                    self.assertNotIn(result["status"], {"ok", "abstained"})

    def test_last_uncertain_cleanup_receipt_remains_pending(self):
        original = self.client.post

        def third_refused(operation, body, **options):
            response = original(operation, body, **options)
            if len(self.client.calls) == 3:
                response["http_status"] = 403
            return response

        with patch.object(self.client, "post", side_effect=third_refused):
            results = cleanup(self.client, self.journal)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[-1]["remaining_pending"], 1)

    def test_seed_intent_and_actual_request_id_survive_interruption(self):
        path = Path(self.temp.name) / "interrupted.jsonl"
        captured_ids = []

        def interrupted(operation, body, *, request_id):
            events = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(events[-1]["kind"], "seed_intent")
            self.assertEqual(events[-1]["key"], body["memory_key"])
            self.assertEqual(events[-1]["request_id"], request_id)
            captured_ids.append(request_id)
            raise RuntimeError("simulated interruption before acknowledgement")

        with (
            patch.object(self.client, "post", side_effect=interrupted),
            self.assertRaisesRegex(RuntimeError, "simulated interruption"),
        ):
            seed(self.client, path)
        events = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(events[-1]["request_id"], captured_ids[0])
        self.assertEqual(load_run(self.client, path, require_complete=False)[1], [])

    def test_each_seed_response_reuses_its_durable_intent_id(self):
        events = [json.loads(line) for line in self.journal.read_text().splitlines()]
        intents = {
            e["key"]: e["request_id"] for e in events if e["kind"] == "seed_intent"
        }
        for event in events:
            if event["kind"] == "seed":
                self.assertEqual(event["metadata"]["request_id"], intents[event["key"]])


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.client = LoomHTTP(FakeLoom.config)

    def test_wire_headers_and_non_json_refusal_without_raw_error(self):
        error = HTTPError(
            "https://loom.example", 403, "PRIVATE", {}, BytesIO(b"PRIVATE")
        )
        with patch.object(self.client.opener, "open", side_effect=error) as opened:
            response = self.client.post(
                "memory.search", {"query": "synthetic"}, request_id="persisted-request"
            )
        request = opened.call_args.args[0]
        self.assertEqual(request.get_header("X-request-id"), "persisted-request")
        self.assertEqual(request.full_url, "https://loom.example/v1/memory.search")
        self.assertEqual(request.get_header("Authorization"), "Bearer not-a-token")
        self.assertEqual(json.loads(request.data), {"query": "synthetic"})
        self.assertEqual(response["http_status"], 403)
        self.assertEqual(response["transport_error"], "INVALID_RESPONSE")
        self.assertNotIn("PRIVATE", json.dumps(response))

    def test_network_error_is_bounded_and_not_retried(self):
        with patch.object(
            self.client.opener, "open", side_effect=URLError("PRIVATE")
        ) as opened:
            response = self.client.post("memory.search", {})
        self.assertEqual(opened.call_count, 1)
        self.assertEqual(response["http_status"], 0)
        self.assertEqual(response["transport_error"], "NETWORK_ERROR")
        self.assertNotIn("PRIVATE", json.dumps(response))

    def test_redirect_handler_does_not_forward_credentials(self):
        from loom_retrieval import NoRedirect

        self.assertIsNone(
            NoRedirect().redirect_request(
                None, None, 302, "", {}, "https://other.example"
            )
        )


if __name__ == "__main__":
    unittest.main()
