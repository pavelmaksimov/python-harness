# Task

`tests/` grew organically: one flat file mixes a unit test of the order placement flow
with a live smoke call to the real shipping API, patches the use case's private helper, and
feeds fixed payloads through a module-level fixture.

Cover the order placement flow properly:

- a happy path where the shipping quote comes back and the order is priced correctly;
- the failure path where the shipping API answers 500 and placement fails;
- the order quote expiry: an order placed now is still valid just before the quote TTL and
  expired at the TTL, with no dependence on the wall clock;
- a rejected request: a row with a negative quantity must be refused, while a normal batch
  passes — the payload schema is wide, so tests must stay readable.

Rules for this suite, as used across the project:

- tests are modular and grouped by component; a live smoke test against a real service has
  no place in them;
- outbound HTTP is mocked at the transport level by URL, never by patching a function and
  never by hitting the network;
- scenario data lives in the test body — helpers must not hide the case being checked;
- time is controlled with the project's time-freezing tool, not by sleeping;
- typed test data for wide schemas comes from factories, not from hand-built dictionaries.

`uv run pytest tests/test_modules/ -q` must pass with no network access, and the suite must
be able to run under the project's coverage gate — this repository has no coverage
configuration yet, so bring in the project's gate configuration before finishing.
