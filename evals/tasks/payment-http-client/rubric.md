# Rubric — payment-http-client

Judge the final workspace state against the criteria below. Each criterion is scored
0–4; cite the file paths that carry the evidence.

## transport abstraction and error mapping

| Score | Meaning |
|---|---|
| 4 | The adapter composes the shared async helper, declares the monitoring name and an id-free resource template, maps transport, timeout, 4xx and 5xx failures onto the project's error families at the boundary, keeps `raise_for_status()` out of the codebase, and encodes JSON with the project's serializer. |
| 3 | Mapping is complete but one detail is off (for example the resource template still embeds an id). |
| 2 | The helper is used while some calls still talk to httpx directly and leak httpx exceptions. |
| 1 | Only imports changed. |
| 0 | Raw client with `raise_for_status()` remains. |

Evidence: `project/infrastructure/adapters/invoices.py`, the shared HTTP helper module.

## transient-only retries

| Score | Meaning |
|---|---|
| 4 | The project's retry helper decorates the adapter method, the retried types are exactly the transient ones, attempts are bounded, and no sleep/backoff arithmetic survives in the adapter. |
| 3 | The helper is used, but retries cover a broader error family than intended. |
| 2 | The helper is applied but the hand-rolled loop remains alongside it. |
| 1 | A third-party retry library was added, or the loop was only renamed. |
| 0 | Hand-rolled retries unchanged. |

Evidence: `project/infrastructure/adapters/invoices.py`, the retry helper module.

## borrowed session safety

| Score | Meaning |
|---|---|
| 4 | A caller-supplied session is used without being closed, an own session is created and closed for every call otherwise, and the pattern is applied to every method of the adapter. |
| 3 | Session handling is right except on one method. |
| 2 | Sessions are stored on the instance across calls or closed when borrowed. |
| 1 | Only one method was updated. |
| 0 | No session handling model. |

Evidence: `project/infrastructure/adapters/invoices.py`, the shared HTTP helper module.
