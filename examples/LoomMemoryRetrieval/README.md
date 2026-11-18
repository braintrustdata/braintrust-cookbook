# Evaluate scoped Loom memory retrieval with Braintrust

This recipe measures whether a direct Loom `memory.search` call returns the expected synthetic memory first. Three cases cover a schedule, a retry policy, and an access review. Braintrust records retrieval scores, response status, and request latency. No model chooses the calls, generates answers, or judges them.

This is a component evaluation. It does not measure coding success, model adoption, memory warm-up, cost savings, or an end-to-end speed improvement. Three synthetic cases are a starting point for checking an integration, not a product benchmark.

## Run

Open `LoomMemoryRetrieval.ipynb` with a Python kernel from this directory. Install `requirements.txt` in your own environment. Set these environment variables outside the notebook:

- `LOOM_BASE_URL`: your Loom HTTPS base URL.
- `LOOM_ORG` and `LOOM_NAMESPACE`: an existing dedicated evaluation scope.
- `LOOM_API_KEY`: a token authorized to create, read, and delete fixture memories in that scope.
- `BRAINTRUST_API_KEY`: your Braintrust API key.

The server needs working embedding providers for semantic memory. Its configured providers may incur charges. Running the evaluation uploads synthetic questions, expected keys, returned fixture keys, and bounded receipt metadata to Braintrust. No memory values, credentials, endpoint, organization name, namespace name, raw errors, or unrelated keys are sent by the recipe. Automatic Git metadata collection is disabled.

Run the fixture cell once. It creates three memories with one unique run tag and a one-day expiry, then writes acknowledged identity/key/version receipts to a local journal with owner-only permissions. Keep this journal out of version control. A request intent and ID are persisted before dispatch; the HTTP request sends that same ID. Each successful response is recorded before the next write. An interrupted write without a receipt needs investigation using the request ID; do not reseed the same run or guess its version.

Run the evaluation cell after the server has indexed the fixtures. It awaits `EvalAsync` before returning, so the following cleanup cell cannot run ahead of the evaluation. There is no polling or retry loop. Search uses exactly one tag because Loom combines multiple tags with OR. It also sets one namespace, the fixture agent and session, memory-only retrieval, and `auto_touch=False`. The evaluation makes no memory writes or outcome claims.

An HTTP failure, refusal, malformed scope, or degraded response has a null retrieval score. Inspect the status and the `response_complete` score alongside accuracy; skipped cases must not be counted as successful retrievals. If every retrieval score is null, there is no accuracy result. An ordinary empty result or abstention receives zero. A scope mismatch suppresses every returned key. The recipe retains only the number of degraded components; raw diagnostic prose can contain unrelated content.

Run the cleanup cell explicitly, including after a partial seed or evaluation failure. It requests `memory.delete_version` only for acknowledged fixture versions. A changed version remains untouched. Cleanup results stay in the local journal; cleanup never runs in a `finally` block that could hide the original error. Cleanup stops at the first refusal or uncertain request outcome and records how many receipts remain pending. Diagnose that result before any explicit rerun. No broader deletion is attempted. Deletion follows the server's tombstone and erasure lifecycle; it is not an immediate physical purge.

A namespace configured for conflict checks can merge or refuse a fixture write. The seed stops and retains any acknowledged version receipts. Inspect that result and clean up before starting a new run in an appropriate evaluation scope. Do not bypass authentication or session-protection refusals by adding an unimplemented attestation header.

## Read the results

`expected_key_at_1` checks the first result against the expected key. `response_complete` reports whether the request returned a complete response, including ordinary abstentions. Scores must be read together. Failed and partial requests remain visible and do not silently become retrieval misses or successes.

`elapsed_ms` measures one HTTP request, excluding fixture creation and Braintrust upload time. `estimated_body_tokens` is Loom's returned body-size estimate, not provider billing. `provider_usage` is null because this response contract does not give complete provider usage. No aggregate token, monetary, or no-Loom comparison is claimed.

Replace these synthetic cases with a reviewed, held-out dataset before drawing conclusions about your application. Keep a separate record of setup failures, skipped cases, indexing readiness, and the number of completed requests.

## Sources and license

The implementation follows Loom's published [memory contracts](https://github.com/ClickHouse/loom/blob/v1.2.0/server/memory/api/models_crud.py), [search contract](https://github.com/ClickHouse/loom/blob/v1.2.0/server/memory/api/models_search.py), and [HTTP transport](https://github.com/ClickHouse/loom/blob/v1.2.0/sdk/python/loom/transport.py). Braintrust's published [EvalAsync API](https://github.com/braintrustdata/braintrust-sdk-python/blob/py-sdk-v0.51.0/py/src/braintrust/framework.py) accepts the task and scorers; [Score](https://github.com/braintrustdata/braintrust-sdk-python/blob/py-sdk-v0.51.0/py/src/braintrust/score.py) treats a null score as skipped.

This contribution follows the cookbook's CC BY-NC-SA 4.0 license. Loom itself is Apache 2.0 licensed.
