# Rubric — order-cache-rate-limit

Judge the final workspace state against the criteria below. Each criterion is scored
0–4; cite the file paths that carry the evidence.

## namespaced cache keys with ttl

| Score | Meaning |
|---|---|
| 4 | The cache type subclasses the project's cache repository, declares a key template and a TTL, every key is produced through the shared key builder under the single application prefix, and no component imports the Redis client. |
| 3 | Keys and TTL are right, but the prefix comes from a literal instead of the settings constants. |
| 2 | The subclass exists but keys are still concatenated by hand in some methods. |
| 1 | Raw keys remain, only moved into a different module. |
| 0 | Unchanged raw client usage. |

Evidence: `project/components/orders/repositories.py`, `project/settings.py`.

## transaction-safe serialization

| Score | Meaning |
|---|---|
| 4 | Values are serialized with the project's JSON serializer through a schema, writes and deletes go through the transaction helpers (never a hand-executed pipeline or a bare client call), the client itself lives in the infrastructure adapter, and reads reuse the helper. |
| 3 | Serialization and transactions are right, but one call still uses the client directly for a read. |
| 2 | Pipeline handling is manual, or serialization bypasses the project's serializer. |
| 1 | Only `json.dumps` was renamed. |
| 0 | Raw JSON strings through a module-level client. |

Evidence: the cache adapter module and `project/components/orders/repositories.py`.

## single limiter initialization

| Score | Meaning |
|---|---|
| 4 | The limiter is initialized exactly once with the shared Redis client during app start-up, the hot routes depend on the released limiter API, no hand-rolled middleware or in-memory counters remain, and rejected requests get 429 with a retry hint. |
| 3 | Limiter wiring is right but registration happens outside the app start-up path or one route kept the old middleware behaviour. |
| 2 | The dependency is attached to routes but initialization is repeated per request or per module import. |
| 1 | A new library is imported while the middleware still enforces the limit. |
| 0 | Middleware unchanged. |

Evidence: `project/infrastructure/apps/api.py`, the order endpoint module.
