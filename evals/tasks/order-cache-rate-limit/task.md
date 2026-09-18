# Task

Order reads are hammered: every request goes to Postgres, and the login and search routes
are being abused. Two things need fixing in this repo.

**Cache order reads in Redis.** Today `project/components/orders/repositories.py` builds a
Redis client at import time, writes raw keys and serializes with `json.dumps`. Move it onto
the project's cache conventions: the repository subclass that owns one cache concern, keys
built from a declared key template under a single application prefix, values stored through
the project's JSON serializer, a TTL on every entry, and all Redis I/O going through the
adapter helpers so the component never talks to the client directly.

**Rate-limit the hot routes.** The API in `project/infrastructure/apps/api.py` throttles
with a hand-written middleware and a module-level dictionary. Replace it with the project's
rate-limiting library, using its released API: initialization happens once per process at
app start-up, the limiter is attached to the affected routes as a dependency, and route
signatures stay clean (no extra request parameter). Throttled responses must be 429 and
tell the client how long to wait.

`uv run python -c "import project"` must work — nothing may connect to Redis or to any
network at import time.
