# SOURCES.md — materials the harness is built from

Single index of every external material used to author or refresh this catalog:
official docs, repos, PyPI pages, articles, blog posts, and examples.
Per-ID refresh maps (`harnesses/<type>/<id>/UPSTREAM.md`) are detail;
this file is the obligatory entry point and must link them when they exist.

Rules for working with this file live in `AGENTS.md` → section **Sources log**.

Format per row: `ID | What was taken | Links`. Keep links bare URLs, one per
line inside the cell or comma-separated. No secrets, tokens, or private URLs.

## Core

| ID | What was taken | Links |
|---|---|---|
| `conventional-commits` | Spec 1.0.0, message format | https://www.conventionalcommits.org/en/v1.0.0/ |
| `keep-a-changelog` | Spec 1.1.0, release-section format | https://keepachangelog.com/en/1.1.0/ |
| `python-tooling` | uv, Ruff, Black, isort, pre-commit conventions | https://github.com/pavelmaksimov/python-harness |
| `python-workflow` | Navigation / verification conventions of this repo | https://github.com/pavelmaksimov/python-harness |
| `python-libs` | FSM / retry / HTTP / speech helper design | https://github.com/pavelmaksimov/python-harness |
| `python-architecture` | Module layout, layers, DI, settings, logging, Entity domain model (identity, invariants, domain functions, ORM ↔ Entity mapping), thin readable use cases (delegating orchestration) | https://github.com/pavelmaksimov/python-harness, https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html, https://www.domainlanguage.com/wp-content/uploads/2016/05/DDD_Reference_2015-03.pdf, https://martinfowler.com/bliki/AnemicDomainModel.html, https://martinfowler.com/eaaCatalog/dataMapper.html, https://docs.python.org/3/library/dataclasses.html |
| `python-fsm` | StateMachine design of this repo | https://github.com/pavelmaksimov/python-harness |
| `python-retry` | Retry-helper design of this repo | https://github.com/pavelmaksimov/python-harness |
| `python-stdlib-first-review` | Suggest-mode review: itertools / functools / cachetools / collections / heapq / bisect / operator replacement patterns | https://docs.python.org/3/library/itertools.html, https://docs.python.org/3/library/functools.html, https://docs.python.org/3/library/collections.html, https://docs.python.org/3/library/heapq.html, https://docs.python.org/3/library/bisect.html, https://docs.python.org/3/library/operator.html, https://docs.python.org/3/library/keyword.html, https://pypi.org/project/cachetools/ · Detail map: `harnesses/skills/python-stdlib-first-review/UPSTREAM.md` |
| `python-tests` | pytest layout, no-patch conventions of this repo | https://github.com/pavelmaksimov/python-harness |
| `python-freezegun` | freezegun `freeze_time` usage | https://github.com/spulec/freezegun |
| `python-polyfactory` | Factory declaration, SQLAlchemyFactory, fields, custom types, model coverage | https://polyfactory.litestar.dev/latest/usage/index.html, https://polyfactory.litestar.dev/latest/usage/declaring_factories.html, https://polyfactory.litestar.dev/latest/usage/library_factories/sqlalchemy_factory.html, https://polyfactory.litestar.dev/latest/usage/configuration.html, https://polyfactory.litestar.dev/latest/usage/handling_custom_types.html, https://polyfactory.litestar.dev/latest/usage/model_coverage.html, https://polyfactory.litestar.dev/latest/usage/fields.html, https://polyfactory.litestar.dev/latest/usage/decorators.html, https://github.com/litestar-org/polyfactory · Detail map: `harnesses/rules/python-polyfactory/UPSTREAM.md` |
| `python-semver` | SemVer 2.0.0 spec; PEP 440 note | https://semver.org/spec/v2.0.0.html, https://packaging.python.org/en/latest/specifications/version-specifiers/ · Detail map: `harnesses/rules/python-semver/UPSTREAM.md` |

## Adapters

| ID | What was taken | Links |
|---|---|---|
| `python-fastapi` | FastAPI / SSE / ORJSON conventions of this repo | https://github.com/pavelmaksimov/python-harness |
| `python-jwt` | OAuth2 JWT tutorial flow | https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/ |
| `python-base-client` | Outbound HTTP adapter design of this repo | https://github.com/pavelmaksimov/python-harness |
| `python-sqlalchemy` | ORM structure of this repo | https://github.com/pavelmaksimov/python-harness |
| `sqlalchemy` | SQLAlchemy 2.x docs (models, queries, sessions, dialects) | https://docs.sqlalchemy.org/ |
| `python-db-sessions` | Session lifecycle design of this repo | https://github.com/pavelmaksimov/python-harness |
| `python-alembic` | Alembic env / autogenerate conventions | https://alembic.sqlalchemy.org/ |
| `python-sqladmin` | sqladmin panel usage | https://github.com/smithyhq/sqladmin |
| `python-redis` | Cache design of this repo | https://github.com/pavelmaksimov/python-harness |
| `python-fastapi-limiter` | fastapi-limiter `RateLimiter` usage | https://github.com/long2ice/fastapi-limiter |
| `python-telegram` | python-telegram-bot polling / handlers | https://docs.python-telegram-bot.org/ |
| `python-typer` | Typer explicit app, commands, options/arguments, callbacks, parameter types, testing (`CliRunner`), package scripts; sync commands only — async bridge via `asyncio.Runner`; usage exit code 2 | https://typer.tiangolo.com/, https://github.com/fastapi/typer, https://click.palletsprojects.com/ |
| `cli-design` | CLI system-type patterns adapted (not vendored): command trees, flag discipline, stdout/stderr contract, exit codes, config layering, output-as-API semver, anti-patterns | https://github.com/microsoft/amplifier-bundle-systems-design, https://github.com/microsoft/amplifier-bundle-systems-design/blob/main/skills/system-type-cli-tool/SKILL.md |
| `python-monitoring` | `llm_common` Prometheus helpers (not PyPI `pycommons`) | https://pypi.org/project/llm_common/ |
| `python-memory` | _Add rows here when the ID is catalogued in README_ |  |

## Enforcement

| ID | What was taken | Links |
|---|---|---|
| `layers-linter` | Import-boundary tool behavior | https://github.com/pavelmaksimov/layers-linter |
| `domain-types-linter` | Domain-type annotation rules | https://github.com/pavelmaksimov/domain-types-linter |
| `patch-linter` | No-patch / no-monkeypatch rule | https://github.com/pavelmaksimov/patch-linter |
| `di-linter` | DI construction rules | https://github.com/pavelmaksimov/di-linter |
| `dddlint` | Unique-name (`duplicate`) rule | https://github.com/benomahony/dddlint |
| `python-coverage` | Coverage-gate design of this repo | https://github.com/pavelmaksimov/python-harness |

## Setup skill

| ID | What was taken | Links |
|---|---|---|
| `setup-python-harness` | Install layout / Kind semantics of this repo | https://github.com/pavelmaksimov/python-harness |

## General / cross-cutting

_Articles, posts, and examples that influenced several IDs at once. Add rows here instead of duplicating links across tables._

| Topic | Links |
|---|---|
| amplifier systems-design bundle — sections in `python-retry` / `python-fsm` / `python-redis` (never vendored) | https://github.com/microsoft/amplifier-bundle-systems-design |
