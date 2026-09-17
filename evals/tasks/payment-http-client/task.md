# Task

`project/infrastructure/adapters/invoices.py` talks to the invoices provider with a raw
async HTTP client, hand-rolled retry arithmetic and `raise_for_status()`. Payments is about
to depend on it, so it has to follow the project's outbound-call conventions.

- the shared outbound HTTP helper module does not exist in this tree yet: add it in the
  location this project documents for outbound HTTP, using the asynchronous implementation,
  because nothing else in the repo is sync;
- the invoices adapter becomes a client built on that helper — it declares the name used
  for monitoring, a resource template without ids, and reuses a caller-provided session
  when one is passed in, otherwise opening its own;
- provider failures are translated at the adapter boundary into the project's error types,
  so no caller ever sees an httpx exception: 4xx → client error, 5xx → server error,
  transport and timeout failures → connection error;
- the hand-rolled retry loop and its sleeps must not survive: retries come from the
  project's retry helper, applied to the adapter method, only for transient failures, with
  a bounded number of attempts;
- request and response bodies are encoded with the project's JSON serializer.

`uv run python -c "import project"` must work, and importing the adapter must not perform
any network call.
