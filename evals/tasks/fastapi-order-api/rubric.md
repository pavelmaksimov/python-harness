# Rubric — fastapi-order-api

Judge the final workspace state against the criteria below. Each criterion is scored
0–4; cite the file paths that carry the evidence.

## thin versioned endpoints

| Score | Meaning |
|---|---|
| 4 | Every endpoint is a success-path adapter (validate → call → return), routes carry a version segment, and no endpoint inspects status codes or builds error payloads. |
| 3 | Endpoints are thin but a version segment is missing on some routes. |
| 2 | Some try/except or `HTTPException` handling survives in endpoints, or business logic leaked in. |
| 1 | Only one endpoint was cleaned up. |
| 0 | Endpoints still own their error translation. |

Evidence: `project/components/orders/endpoints.py`.

## centralized exception mapping

| Score | Meaning |
|---|---|
| 4 | The app registers handlers once and maps each application error family to the documented status code, with a generic 500 for unexpected failures that exposes nothing internal; unknown routes and validation failures follow the platform defaults. |
| 3 | Handlers exist and are correct, but one family is unmapped or a handler echoes the internal message for unexpected errors. |
| 2 | Some mapping is registered while other branches stay in endpoints. |
| 1 | A middleware or a wrapper function was added instead of exception handlers, with inconsistent coverage. |
| 0 | No centralized mapping. |

Evidence: `project/infrastructure/apps/api.py`.

## safe response and logging boundaries

| Score | Meaning |
|---|---|
| 4 | Responses use the project JSON response class, logging is configured once in the app lifespan, and no debug locals or stack traces are enabled in the response path. |
| 3 | Response and logging are wired, with one detail missing (for example logging configured at import time of a module that the app does not import). |
| 2 | Response class is right but logging setup is missing or duplicated per module. |
| 1 | Logging configured in endpoints. |
| 0 | Neither is present. |

Evidence: `project/infrastructure/apps/api.py`, `project/components/orders/endpoints.py`.
