# python-harness

Opinionated agent harness catalog for Python backend services.

**Catalog version:** `1.3.0` (see root `VERSION`).

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

Installed copies are snapshots stamped with the catalog `VERSION`. Periodically
update them from this repository (re-run the bootstrap skill or re-copy the
approved installable paths) when the local `.cursor/python-harness-version`
differs from the source `VERSION`.

## Version

The catalog has one shared version for the whole installable set (semver in
root `VERSION`, mirrored here). It is not a per-ID version.

On install, the setup skill writes that string to
`.cursor/python-harness-version` in the target (or `~/.cursor/python-harness-version`
for a personal install). Compare that file to this repo's `VERSION` (or to the
line above) to see whether the local snapshot is current.

| Where | What it means |
|---|---|
| This repo `VERSION` / README line | Latest catalog release in the source |
| Target `.cursor/python-harness-version` | Catalog version that was last installed there |

Bump `VERSION` (and the README line) when installable harnesses, the setup
skill, or catalog install semantics change. Docs-only README edits that do not
change what gets copied may leave the version unchanged.

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
so the same boundaries are enforced. Add `patch-linter` when automated tests
are selected. Install `conventional-commits` with every core bundle; when a
task changes tracked files without creating a commit, `python-workflow` ends
the response with a proposed Conventional Commit message. `keep-a-changelog`
is optional; when selected, the workflow records notable completed changes and
updates the current entry when a task is refined. `python-coverage` is optional —
offer it when automated tests
are selected; on approval it also appends the post-task coverage-gate step to
the installed `python-workflow` rule (catalog `COMPANION.md`). Without it, the
`python-workflow` coverage check stays skipped and no gate is configured.
`di-linter` is optional — add it when the repo uses Container/LazyInit and you
want DI001/DI002 enforced. If it is added, patch companion rules that already
pair the other linters so they mention it too.

```text
Core          conventional-commits · keep-a-changelog (optional) · python-tooling · python-workflow · python-libs · python-architecture · python-fsm · python-retry · python-tests · python-freezegun · python-polyfactory · python-semver (libraries)
Adapters      python-fastapi · python-base-client · python-sqlalchemy · sqlalchemy · python-db-sessions · python-alembic · python-sqladmin · python-redis · python-fastapi-limiter · python-telegram · python-monitoring
Enforcement   layers-linter · domain-types-linter · patch-linter · di-linter (optional) · python-coverage (optional)
```

Recommended set for a FastAPI + Postgres service: every core and adapter row
that the repo uses, plus `layers-linter` and `domain-types-linter`; add
`patch-linter` when automated tests are selected.
Add `python-freezegun` and `python-polyfactory` with every automated-test
bundle. Offer `keep-a-changelog` for post-task release notes and `di-linter`
as strict enforcement. Add `python-semver` when
the repo is (or will be) a publishable Python library with a public API; skip
it for internal apps/services.
For a FastAPI API, add `python-fastapi`; ask separately whether Prometheus
monitoring is needed and add `python-monitoring` only when selected.
Skip `python-fastapi` when the repo has no inbound HTTP API.
Skip `python-base-client` when the repo has no outbound HTTP adapters. Skip an adapter
when the repo has no database or no Redis cache. A selected database installs
`python-sqlalchemy`, the `sqlalchemy` skill, `python-db-sessions`, and
`python-alembic` together. Ask whether the service needs an operator admin panel;
a yes selects `python-sqladmin` (SQLAlchemy models only), only with the database
bundle. Ask whether inbound FastAPI
routes need rate limiting; a yes selects `python-fastapi-limiter` together with
`python-redis` (shared Redis client and Settings). Skip
`python-telegram` when the repo has no Telegram bot. Skip `python-monitoring`
when Prometheus monitoring is not selected. Render the speech adapter from
`python-libs` (`SPEECH.md`) when the project uses speech-to-text,
text-to-speech, or both; skip it when there is no speech I/O.
For SQLAlchemy-backed persistence, install `python-sqlalchemy` (project
structure: `Base` / `TimeMixin`, generic repositories), `python-db-sessions`
(runtime session lifecycle), and the `sqlalchemy` skill (low-level 2.x
mechanics: models, queries, dialects). The skill is architecture-neutral and
pairs with any project layout.

### Core

| ID | Name | Kind | Summary | Upstream | Install from |
|---|---|---|---|---|---|
| `conventional-commits` | Conventional Commits | installable | Default commit-message drafting and validation; `python-workflow` proposes a message after changed tasks that did not create a commit | https://www.conventionalcommits.org/en/v1.0.0/ | `harnesses/skills/conventional-commits/` → `.cursor/skills/conventional-commits/`; install with every core bundle |
| `keep-a-changelog` | Keep a Changelog | installable | Optional post-task changelog: SemVer release sections for libraries, ISO-date sections for projects without library versions; refinements update the current entry | https://keepachangelog.com/en/1.1.0/ | `harnesses/skills/keep-a-changelog/` → `.cursor/skills/keep-a-changelog/`; offer during onboarding, never auto-install |
| `python-tooling` | Python tooling | installable | uv, Ruff, Black, isort, pre-commit, log call sites | https://github.com/pavelmaksimov/python-harness | Rule: `harnesses/rules/python-tooling/` → `.cursor/rules/python-tooling/`. Merge selected Ruff / Black / isort tables from sibling `PYPROJECT.toml` into repo-root `pyproject.toml`; render sibling `PRE_COMMIT.yaml` into repo-root `.pre-commit-config.yaml`. Adapt package/test paths and selected hooks; preserve existing files unless the user approves a merge or replacement |
| `python-workflow` | Python workflow | installable | Navigate from `project/container.py` and Python modules; verify tasks through subagents; preserve reusable research; propose uncreated commits | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-workflow/` → `.cursor/rules/python-workflow/` |
| `python-libs` | Python helper libraries | installable | Always-on index and disclosed implementations for FSM, retry, outbound HTTP, and speech helpers; indexes the admin-panel and rate-limiting rules that live in the same dir |
| `python-architecture` | Python structure | installable | Module layout, layers, adapters, domain types, `layers.toml`; sibling rule files: `python-exceptions.mdc`, `python-settings.mdc`, `python-logging.mdc`, `python-di.mdc`, `python-development-rules.mdc` | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-architecture/` → `.cursor/rules/python-architecture/` |
| `python-fsm` | Python FSM | installable | StateMachine / AsyncStateMachine, validated transitions | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-libs/python-fsm.mdc` → `.cursor/rules/python-libs/python-fsm.mdc`; render `python-libs/FSM.md` to `project/libs/fsm.py` if missing |
| `python-retry` | Python retry | installable | `retry_on_exception` / `retry_unless_exception` for transient I/O | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-libs/python-retry.mdc` → `.cursor/rules/python-libs/python-retry.mdc`; render `python-libs/RETRY.md` to `project/libs/retry.py` if missing |
| `python-tests` | Python tests | installable | pytest layout, modular vs e2e, HTTP mocks, no patch | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-tests/` → `.cursor/rules/python-tests/` |
| `python-freezegun` | Frozen time | installable | freezegun `freeze_time` — stopped UTC clock in tests, not `patch(datetime)` | https://github.com/spulec/freezegun | `harnesses/rules/python-freezegun/` → `.cursor/rules/python-freezegun/`. Package: `uv add --dev freezegun` |
| `python-polyfactory` | Polyfactory | installable | All generated test data through Polyfactory; ORM guidance disclosed in `FACTORIES_ORM.md` | https://github.com/litestar-org/polyfactory | `harnesses/rules/python-polyfactory/` → `.cursor/rules/python-polyfactory/`. Package: `uv add --dev polyfactory`; install with every automated-test bundle. Add `FACTORIES_ORM.md` only with `python-sqlalchemy` + `python-db-sessions` |
| `python-semver` | SemVer 2.0 (libraries) | installable | Semantic Versioning 2.0 for publishable libraries — public API, X.Y.Z bumps, pyproject version | https://semver.org/spec/v2.0.0.html | `harnesses/rules/python-semver/` → `.cursor/rules/python-semver/`. Optional; install when the repo is a library |

Templates: `python-tooling` → merge selected Ruff / Black / isort tables from
`PYPROJECT.toml` into repo-root `pyproject.toml`, and render `PRE_COMMIT.yaml` into
repo-root `.pre-commit-config.yaml` with package/test paths and optional hooks adapted;
copy the remaining templates only if missing: `python-architecture` → `BASE_SCHEMAS.md` into
`project/base/schemas.py`, `SETTINGS.md` into `project/settings.py`, `LOGGER.md` into
`project/logger.py`, and `STRUCTURES.md` into `project/libs/structures.py`;
`python-fsm` → render `harnesses/rules/python-libs/FSM.md` into `project/libs/fsm.py`;
`python-retry` → render `harnesses/rules/python-libs/RETRY.md` into `project/libs/retry.py`;
`python-tests` → `CONFTEST.md` into `tests/conftest.py` (HTTP core only);
when `python-sqlalchemy` and `python-db-sessions` are also approved →
`CONFTEST_DATABASE.md` into `tests/conftest.py`;
when `python-polyfactory` is approved → `FACTORIES.md` into `tests/factories.py`;
with `python-sqlalchemy` + `python-db-sessions`, also add `FACTORIES_ORM.md` to the rule
and merge its template.
After install, patch installed `python-tests.mdc` per catalog `COMPANION.md` for each
approved optional harness (do not copy `COMPANION.md` to the target).

### Adapters

| ID | Name | Kind | Summary | Upstream | Install from |
|---|---|---|---|---|---|
| `python-fastapi` | FastAPI HTTP | installable | FastAPI, SSE, ORJSON, URL versioning, AppError handlers, httpx, uvloop | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-fastapi/` → `.cursor/rules/python-fastapi/` |
| `python-base-client` | HTTP adapter helper | installable | Choose httpx `AsyncApi` or `SyncApi`; AppError mapping, retries, Session reuse | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-libs/python-base-client.mdc` → `.cursor/rules/python-libs/python-base-client.mdc`; render only the selected `python-libs/ASYNC_CLIENT.md` or `SYNC_CLIENT.md` to `project/infrastructure/base/http_client.py` |
| `python-sqlalchemy` | SQLAlchemy ORM | installable | ORM models, `Base` / `TimeMixin`, generic `ORMRepository` | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-sqlalchemy/` → `.cursor/rules/python-sqlalchemy/` |
| `sqlalchemy` | SQLAlchemy 2.x practices (skill) | installable | Low-level, architecture-neutral ORM models, 2.0 query API, loader strategies, session semantics, dialect rules (PostgreSQL, MySQL/MariaDB, SQLite, SQL Server, Oracle) | https://docs.sqlalchemy.org/ | Skill: `harnesses/skills/sqlalchemy/` → `.cursor/skills/sqlalchemy/` (copy the whole dir: `SKILL.md` + `references/`). Content follows the official SQLAlchemy documentation; skill from this repo. Pairs with `python-sqlalchemy` (structure) and `python-db-sessions` (sessions) but forces no architecture |
| `python-db-sessions` | Database sessions | installable | Async engine, `asession` / `atransaction`, DSN and optional Postgres | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-db-sessions/` → `.cursor/rules/python-db-sessions/` |
| `python-alembic` | Alembic migrations | installable | Async Alembic env, autogenerate from ORM models, versions outside `project/` | https://alembic.sqlalchemy.org/ | `harnesses/rules/python-alembic/` → `.cursor/rules/python-alembic/` |
| `python-sqladmin` | sqladmin panel | installable | Admin UI over SQLAlchemy models mounted on the FastAPI app; authenticated operators, explicit column lists | https://github.com/smithyhq/sqladmin | `harnesses/rules/python-libs/python-sqladmin.mdc` → `.cursor/rules/python-libs/python-sqladmin.mdc`. Package: `uv add sqladmin[auth]`. Only with the database bundle |
| `python-redis` | Redis cache | installable | Prefixed keys, `CacheRepository`, `redis_atransaction`, orjson | https://github.com/pavelmaksimov/python-harness | `harnesses/rules/python-redis/` → `.cursor/rules/python-redis/` |
| `python-fastapi-limiter` | Route rate limiting | installable | fastapi-limiter `RateLimiter` dependencies on routers/endpoints; Redis counters, 429 + `Retry-After` | https://github.com/long2ice/fastapi-limiter | `harnesses/rules/python-libs/python-fastapi-limiter.mdc` → `.cursor/rules/python-libs/python-fastapi-limiter.mdc`. Package: `uv add fastapi-limiter`. Install with `python-redis` (shared Redis client and Settings); FastAPI APIs only |
| `python-telegram` | Telegram bot | installable | python-telegram-bot polling, handlers, error decorators | https://docs.python-telegram-bot.org/ | `harnesses/rules/python-telegram/` → `.cursor/rules/python-telegram/` |
| `python-monitoring` | Prometheus metrics | installable | FastAPI `/prometheus`, action tracking, monitored httpx | https://pypi.org/project/llm_common/ | Rule: `harnesses/rules/python-monitoring/` → `.cursor/rules/python-monitoring/`. Tool from PyPI `llm_common` (`uv add llm_common prometheus_client`); skill/rule from this repo. Do not confuse with PyPI `pycommons`. |

Templates (copy only if missing): `python-base-client` → developer chooses
`harnesses/rules/python-libs/ASYNC_CLIENT.md` or `SYNC_CLIENT.md`; render only that
implementation into `project/infrastructure/base/http_client.py` (never combine them);
`python-sqlalchemy` → `BASE_MODELS.md` into `project/base/models.py` and, when multiple
repositories share the base, `BASE_REPOSITORIES.md` into `project/base/repositories.py`;
`python-db-sessions` → `DATABASE.md` into `project/infrastructure/adapters/database.py`;
`python-alembic` → `ENV.md` into
`alembic/env.py`; `python-redis` → adapter from `CACHE.md` into
`project/infrastructure/adapters/acache.py` and `CacheRepository` into
`project/base/repositories.py`; `python-telegram` → `TELEGRAM.md`
into `project/infrastructure/base/telegram.py` and `BOT.md` into
`project/infrastructure/apps/bot.py`; speech (`python-libs`) → `SPEECH.md` into
`project/infrastructure/adapters/speech.py` (only when the repo uses speech I/O).

### Enforcement

Hybrid: tool from upstream, skill from this repo.

| ID | Name | Kind | Summary | Upstream | Notes |
|---|---|---|---|---|---|
| `layers-linter` | layers-linter | installable | Import boundaries between layers and libraries | https://github.com/pavelmaksimov/layers-linter | Tool: `uvx layers-linter`. Skill: `harnesses/skills/layers-linter/` → `.cursor/skills/layers-linter/`. Template: sibling `layers.toml` → repo-root `layers.toml` (copy only if missing; substitute package name if not `project/`) |
| `domain-types-linter` | domain-types-linter | installable | Domain types in business-logic annotations | https://github.com/pavelmaksimov/domain-types-linter | Tool: `uvx --from domain-types-linter dt-linter`. Skill: `harnesses/skills/domain-types-linter/SKILL.md` → `.cursor/skills/domain-types-linter/SKILL.md` |
| `patch-linter` | patch-linter | installable | Forbid `unittest.mock.patch` and pytest `monkeypatch` in tests | https://github.com/pavelmaksimov/patch-linter | Tool: `uvx patch-linter`. Skill: `harnesses/skills/patch-linter/SKILL.md` → `.cursor/skills/patch-linter/SKILL.md` |
| `di-linter` | di-linter | installable | Optional. In-process construction and test patches | https://github.com/pavelmaksimov/di-linter | Tool: `uvx di-linter`. Skill: `harnesses/skills/di-linter/` → `.cursor/skills/di-linter/`. Template: sibling `di.toml` → repo-root `di.toml` (copy only if missing; substitute package name if not `project/`). If added, patch companion rules so they pair it with the other linters |
| `python-coverage` | Coverage gate (pytest-cov) | installable | Optional. Enforce branch coverage ≥ `fail_under` (default 95%), or diff mode: changed lines vs base branch at 100% (`diff-cover`) for legacy baselines; skill closes reported gaps with tests | https://github.com/pavelmaksimov/python-harness | Skill: `harnesses/skills/python-coverage/` → `.cursor/skills/python-coverage/`. Merge `[tool.coverage.*]` tables from sibling `PYPROJECT.md` into repo-root `pyproject.toml` (copy only missing tables/keys). Packages: `uv add --dev pytest-cov`; diff mode adds `uv add --dev diff-cover`. Offer when automated tests are selected; never auto-install |

Templates (copy only if missing): `layers-linter` → `layers.toml` into repo-root
`layers.toml`; `di-linter` → `di.toml` into repo-root `di.toml`. Substitute
`project` if the package name differs. `python-coverage` merges sibling
`PYPROJECT.md` `[tool.coverage.*]` into repo-root `pyproject.toml` (no
standalone file; substitute `project` if the package name differs).

## Install the setup skill globally

Then ask the agent to run `setup-python-harness` in any Python repository.

## License

[MIT](LICENSE)

Third-party skills keep their upstream licenses and attributions where applicable.
