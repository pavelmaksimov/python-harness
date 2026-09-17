# Task

The order HTTP API lives in `project/infrastructure/apps/api.py` and
`project/components/orders/endpoints.py`. Today every endpoint translates its own
failures: try/except blocks that raise `HTTPException` with hand-picked status codes.

Team policy is that the HTTP boundary is owned in one place. Rework the API so that:

- endpoints describe the success path only and let application errors propagate;
- the mapping from application errors to HTTP responses is declared once, at the app
  level, covering: not found → 404, authentication → 401, external API failure → 500,
  invalid request bodies → 422, and anything unexpected → a generic 500 that leaks no
  internals;
- routes are versioned per path (`/orders/v1/...`) and the API answers with the project's
  JSON response class;
- application logging is configured once when the app starts, not per request.

`uv run python -c "from project.infrastructure.apps.api import app"` must work.
