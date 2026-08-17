# python-harness

Opinionated agent harness catalog for Python backend services.

It is both:

- a showcase of practical Python agent rules and enforcement skills;
- a bootstrap source for new Python repositories.

Default package root is `project/` (substitute globs if the repo differs).
Async entrypoints use uvloop: FastAPI via uvicorn `--loop uvloop`; other
processes via `asyncio.Runner(loop_factory=uvloop.new_event_loop)`
(`python-telegram` for the bot).

For non-Python agent harnesses, standards, and reference tooling, see
[agent-setup](https://github.com/pavelmaksimov/agent-setup).

## Bootstrap a new repository

Open a clean repository in your coding agent and send:

```text
Read and follow:
https://raw.githubusercontent.com/pavelmaksimov/python-harness/main/skills/setup-python-harness/SKILL.md

Inspect this repository, ask which Python harness bands I want
(core / adapters / enforcement), recommend a compatible set, and install
only the set I approve.
```

The setup skill reads this README catalog, presents the three bands, asks only
what it cannot infer, and installs **installable** entries after approval.
**Reference** / hybrid notes (upstream tools) are printed from the Notes column.

Installed copies are snapshots. Periodically update them from this repository
(re-run the bootstrap skill or re-copy the approved installable paths) so the
target stays aligned with the catalog.

## What Kind means

Kind answers: **where is the real product installed from?**

| Kind | Meaning |
|---|---|
| **installable** | This repo is the source of truth for the artifact. Copy from `harnesses/<type>/<id>/`. The underlying CLI/package may still need a separate upstream install (see Notes). |
| **reference** | Upstream is the source of truth for the whole product. Do not treat a local mirror as the product. |

Installable artifacts live only under typed dirs in `harnesses/` (`skills/`,
`rules/`, `hooks/`, `agents/`). Never vendor upstream/reference packs here.

## Catalog

Three bands: install **core** for any Python service, add **adapters** the repo
actually uses, and take `layers-linter` and `domain-types-linter` with the stack
so the same boundaries are enforced. `di-linter` is optional — add it when the
repo uses Container/LazyInit and you want DI001/DI002 enforced. If it is added,
patch companion rules that already pair the other linters so they mention it too.

```text
Core          python-tooling · python-structure · python-exceptions · python-settings · python-logging · python-di · python-fsm · python-retry · python-tests
Adapters      python-fastapi · python-base-client · python-sqlalchemy · python-alembic · python-redis · python-telegram · python-monitoring
Enforcement   layers-linter · domain-types-linter · di-linter (optional)
```

Recommended set for a FastAPI + Postgres service: every core and adapter row
that the repo uses, plus `layers-linter` and `domain-types-linter`. Offer
`di-linter` separately. Skip `python-fastapi` when the repo has no inbound HTTP API.
Skip `python-base-client` when the repo has no outbound HTTP adapters. Skip an adapter
when the repo has no database or no Redis cache. Skip `python-alembic` when tables are
created from metadata only (`create_all`). Skip `python-telegram` when the repo has no
Telegram bot. Skip `python-monitoring` when the repo does not scrape Prometheus.

### Core

| ID | Name | Kind | Summary | Upstream | Install from |
|---|---|---|---|---|---|
| `python-tooling` | Python tooling | installable | uv, Ruff, Black, isort, pre-commit, log call sites | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-tooling/` → `.cursor/rules/python-tooling/` |
| `python-structure` | Python structure | installable | Components, layers, adapters, domain types, `layers.toml` | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-structure/` → `.cursor/rules/python-structure/` |
| `python-exceptions` | Python exceptions | installable | `AppError` hierarchy, where to put error types | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-exceptions/` → `.cursor/rules/python-exceptions/` |
| `python-settings` | Python settings | installable | pydantic-settings env contract, `Settings().PARAM` | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-settings/` → `.cursor/rules/python-settings/` |
| `python-logging` | Python logging | installable | `setup_logging()` / dictConfig, levels from Settings | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-logging/` → `.cursor/rules/python-logging/` |
| `python-di` | Python DI | installable | LazyInit, Container, LazyService — no process globals | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-di/` → `.cursor/rules/python-di/` |
| `python-fsm` | Python FSM | installable | StateMachine / AsyncStateMachine, validated transitions | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-fsm/` → `.cursor/rules/python-fsm/` |
| `python-retry` | Python retry | installable | `retry_on_exception` / `retry_unless_exception` for transient I/O | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-retry/` → `.cursor/rules/python-retry/` |
| `python-tests` | Python tests | installable | pytest factories, modular vs e2e, HTTP mocks, no patch | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-tests/` → `.cursor/rules/python-tests/` |

Templates (copy only if missing): `python-structure` → `BASE_MODELS.md` into
`project/components/base/models.py` and `BASE_SCHEMAS.md` into
`project/components/base/schemas.py`;
`python-settings` → `SETTINGS.md` into `project/settings.py`;
`python-logging` → `LOGGER.md` into `project/logger.py`;
`python-di` → `STRUCTURES.md` into `project/libs/structures.py`;
`python-fsm` → `FSM.md` into `project/libs/fsm.py`;
`python-retry` → `RETRY.md` into `project/libs/retry.py`;
`python-tests` → `CONFTEST.md` into `tests/conftest.py`.

### Adapters

| ID | Name | Kind | Summary | Upstream | Install from |
|---|---|---|---|---|---|
| `python-fastapi` | FastAPI HTTP | installable | FastAPI, SSE, ORJSON, URL versioning, AppError handlers, httpx, uvloop | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-fastapi/` → `.cursor/rules/python-fastapi/` |
| `python-base-client` | HTTP adapter helper | installable | httpx `AsyncApi` / `SyncApi`, AppError mapping, Session reuse | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-base-client/` → `.cursor/rules/python-base-client/` |
| `python-sqlalchemy` | SQLAlchemy async | installable | `asession` / `atransaction`, ORM models, optional Postgres | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-sqlalchemy/` → `.cursor/rules/python-sqlalchemy/` |
| `python-alembic` | Alembic migrations | installable | Async Alembic env, autogenerate from ORM models, versions outside `project/` | https://alembic.sqlalchemy.org/ | `harnesses/rules/python-alembic/` → `.cursor/rules/python-alembic/` |
| `python-redis` | Redis cache | installable | `CacheRepository`, `redis_atransaction`, orjson | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-redis/` → `.cursor/rules/python-redis/` |
| `python-telegram` | Telegram bot | installable | python-telegram-bot polling, handlers, error decorators | https://docs.python-telegram-bot.org/ | `harnesses/rules/python-telegram/` → `.cursor/rules/python-telegram/` |
| `python-monitoring` | Prometheus metrics | installable | FastAPI `/prometheus`, action tracking, monitored httpx | https://pypi.org/project/llm_common/ | Rule: `harnesses/rules/python-monitoring/` → `.cursor/rules/python-monitoring/`. Tool from PyPI `llm_common` (`uv add llm_common prometheus_client`); skill/rule from this repo. Do not confuse with PyPI `pycommons`. |

Templates (copy only if missing): `python-base-client` → `CLIENT.md` into
`project/infrastructure/utils/base_client.py`; `python-sqlalchemy` → `DATABASE.md` into
`project/infrastructure/adapters/database.py`; `python-alembic` → `ENV.md` into
`alembic/env.py`; `python-redis` → `CACHE.md` into
`project/infrastructure/adapters/acache.py`; `python-telegram` → `TELEGRAM.md`
into `project/infrastructure/utils/telegram.py` and `BOT.md` into
`project/infrastructure/apps/bot.py`.

### Enforcement

Hybrid: tool from upstream, skill from this repo.

| ID | Name | Kind | Summary | Upstream | Notes |
|---|---|---|---|---|---|
| `layers-linter` | layers-linter | installable | Import boundaries between layers and libraries | https://github.com/pavelmaksimov/layers-linter | Tool: `uvx layers-linter`. Skill: `harnesses/skills/layers-linter/` → `.cursor/skills/layers-linter/`. Template: sibling `layers.toml` → repo-root `layers.toml` (copy only if missing; substitute package name if not `project/`) |
| `domain-types-linter` | domain-types-linter | installable | Domain types in business-logic annotations | https://github.com/pavelmaksimov/domain-types-linter | Tool: `uvx --from domain-types-linter dt-linter`. Skill: `harnesses/skills/domain-types-linter/SKILL.md` → `.cursor/skills/domain-types-linter/SKILL.md` |
| `di-linter` | di-linter | installable | Optional. In-process construction and test patches | https://github.com/pavelmaksimov/di-linter | Tool: `uvx di-linter`. Skill: `harnesses/skills/di-linter/` → `.cursor/skills/di-linter/`. Template: sibling `di.toml` → repo-root `di.toml` (copy only if missing; substitute package name if not `project/`). If added, patch companion rules so they pair it with the other linters |

Templates (copy only if missing): `layers-linter` → `layers.toml` into repo-root
`layers.toml`; `di-linter` → `di.toml` into repo-root `di.toml`. Substitute
`project` if the package name differs.

## Install the setup skill globally

Then ask the agent to run `setup-python-harness` in any Python repository.

## License

[MIT](LICENSE)

Third-party skills keep their upstream licenses and attributions where applicable.
