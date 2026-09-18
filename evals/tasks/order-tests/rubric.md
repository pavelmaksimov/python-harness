# Rubric — order-tests

Judge the final workspace state against the criteria below. Each criterion is scored
0–4; cite the file paths that carry the evidence.

## observable behavior coverage

| Score | Meaning |
|---|---|
| 4 | Each requested behavior has its own test with an assertion on the outcome a caller can observe; error cases assert the raised error, and the expiry cases assert state at both sides of the boundary. |
| 3 | Coverage is complete but one test asserts internals (a private helper's return value) instead of the observable result. |
| 2 | Only the happy path and one extra case are covered. |
| 1 | A single test file exercises one path. |
| 0 | No meaningful coverage of the flow. |

Evidence: the test modules under `tests/`, one test per behavior.

## deterministic isolation

| Score | Meaning |
|---|---|
| 4 | No test touches the network: outbound calls are mocked at the transport level by URL, no patching of application functions appears anywhere, no live smoke test remains, and the suite passes offline. |
| 3 | Transport mocking is correct but one leftover test still depends on external state (a live endpoint, a fixed clock). |
| 2 | Mocking exists but is done by patching application internals, or a live call survives. |
| 1 | Only the live call was deleted; nothing is mocked. |
| 0 | Tests still hit the network or patch internals. |

Evidence: the test modules, the conftest fixtures, `tests/`.

## readable typed test data

| Score | Meaning |
|---|---|
| 4 | Wide payloads are produced by declared factories with per-test overrides where the case needs them; scenario data for the checked behavior lives in the test body, and time control is explicit for the expiry cases. |
| 3 | Factories and time control are present, but a helper fixture still hides scenario data. |
| 2 | Either factories or time control are missing. |
| 1 | Payloads are still hand-written dicts passed through a shared fixture. |
| 0 | No factories, no time control, fixed payloads in fixtures. |

Evidence: `tests/factories.py`, the test modules, any conftest fixture definitions.
