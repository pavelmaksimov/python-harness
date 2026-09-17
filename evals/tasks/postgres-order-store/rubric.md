# Rubric — postgres-order-store

Judge the final workspace state against the criteria below. Each criterion is scored
0–4; cite the file paths that carry the evidence.

## domain and ORM separation

| Score | Meaning |
|---|---|
| 4 | The ORM type lives in the component's `models.py` under its own name, the domain entity keeps the domain name and imports nothing from the ORM, and no ORM object crosses the repository boundary. |
| 3 | Separation is right but the entity still exposes a persistence-shaped helper (a session parameter, an ORM-typed field). |
| 2 | Two types exist, but one imports the other in the wrong direction or the entity keeps the ORM-facing name. |
| 1 | Only one type remains, or names were swapped without separating concerns. |
| 0 | The entity is still the persistence type. |

Evidence: `project/components/orders/models.py`, `project/components/orders/entities.py`.

## transaction-safe repository mapping

| Score | Meaning |
|---|---|
| 4 | The repository opens sessions only through the shared adapter helpers, writes inside the project's transaction helper (a savepoint when nested), never commits or closes sessions by hand, and maps rows to entities explicitly in both directions. |
| 3 | Mapping is right, but one call still builds its own engine or sessionmaker. |
| 2 | The repository was rewritten but still commits per call or opens engines itself. |
| 1 | Only SQL text changed. |
| 0 | Own engine and session lifecycle per call, unchanged. |

Evidence: `project/components/orders/repositories.py`.

## reviewed async migrations

| Score | Meaning |
|---|---|
| 4 | Alembic is configured for async use with the DSN taken from project settings, `sqlalchemy.url` is left unset, component models are imported explicitly for autogenerate, metadata comes from the shared base, and revisions live in the standard versions directory — with no migration drops caused by an unreviewed autogenerate. |
| 3 | Environment is wired correctly, with one detail missing (for example a stock sync `env.py`). |
| 2 | A migrations directory exists but the environment still hardcodes a URL or globs model files. |
| 1 | Only a stub config was added. |
| 0 | No migrations. |

Evidence: `alembic/`, `alembic.ini`.
