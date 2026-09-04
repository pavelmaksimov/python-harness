---
name: setup-python-harness
description: MUST USE for bootstrapping Python agent rules, linter skills, or stack bands in a repository. Recommends and installs the opinionated Python backend harness from pavelmaksimov/python-harness.
---

# Set up Python harness

Use `https://github.com/pavelmaksimov/python-harness` as the catalog and source.

For non-Python harnesses (standards, agent behavior, reference tooling), use
[agent-setup](https://github.com/pavelmaksimov/agent-setup) /
`setup-agent-harnesses` instead.

## Workflow

1. Inspect the target repository's languages, tools, existing agent files, and
   development workflow. If the repo is not Python, stop and point the user to
   `agent-setup` instead of installing from this catalog.
2. Clone the source repository into a temporary directory and read `README.md`
   (the **Catalog** section is the source of truth) and root `VERSION`
   (catalog semver; also shown as **Catalog version** in the README).
3. If the target already has `.cursor/python-harness-version` (or
   `~/.cursor/python-harness-version` for a personal install), compare it to
   the cloned `VERSION`. Report **installed** vs **source** versions up front
   (missing stamp = unknown / pre-version install).
4. Present harnesses by band: **core**, **adapters**, **enforcement**. Recommend
   core for any Python repo, adapters that match the codebase (FastAPI,
   SQLAlchemy ORM, database sessions, Alembic, Redis; Telegram when the repo uses
   python-telegram-bot, `apps/bot.py`,
   or component `handlers.py` — skip `python-telegram` when there is no Telegram
   bot; `python-base-client` when the repo has outbound HTTP adapters under
   `infrastructure/adapters/` — skip it when there are none; the `python-libs`
   speech adapter (`SPEECH.md`) when the repo uses transcription or speech
   synthesis; an admin panel when `project/infrastructure/apps/admin.py` or
   sqladmin imports exist (`python-sqladmin`, SQLAlchemy models only);
   `python-fastapi-limiter` when
   routes declare `RateLimiter` dependencies; `python-jwt` when routes
   authenticate users (`OAuth2PasswordBearer`, `Depends(get_current_user)`, or
   `project/libs/security.py`) — FastAPI APIs with a database only; a Typer CLI
   (`python-typer`, with the `cli-design` skill) when
   `project/infrastructure/apps/cli.py`, `components/*/cli.py`, a `typer`
   dependency, or a `[project.scripts]` entry exists), and
   `layers-linter` and `domain-types-linter` with the stack; add `patch-linter`
   when automated tests are selected. Offer `python-coverage` as **optional**
   when automated tests are selected (never auto-derive it): full mode gates
   total branch coverage at `fail_under` 95%; diff mode (`diff-cover` over
   changed lines) fits legacy baselines that cannot reach the threshold soon.
   On approval, merge sibling `PYPROJECT.md` `[tool.coverage.*]` tables into
   repo-root `pyproject.toml`, add `uv add --dev pytest-cov` (plus
   `uv add --dev diff-cover` in diff mode),
   and apply the companion patches from the catalog `COMPANION.md`
   (`python-tests` pointer row + `python-workflow` "Coverage gate after a
   task" section). Without approval, install nothing and patch nothing.
   Offer `di-linter` as optional (Container/LazyInit, DI001/DI002).
   Offer `dddlint` as optional unique-name enforcement (one name, one
   definition; `duplicate` rule only — keep `forbidden` / `synonyms` empty
   and `enforce_canonical: false`; copy sibling `dddlint.yaml` to the repo
   root when missing).
   Ask whether Prometheus monitoring is needed; when yes, add
   `python-monitoring` (`uv add llm_common prometheus_client` — PyPI
   `llm_common`, not `pycommons`). Core includes the `conventional-commits` skill by default and
   `python-workflow` for repository navigation before
   analysis, post-task verification through subagents (linters, autotests, coverage when
   installed), preserving reusable researched solutions, and proposing a Conventional Commit
   message when a changed task did not create its commit. Offer `keep-a-changelog` as optional;
   when installed, the workflow records notable completed changes and updates the current entry
   when a task is refined. Libraries use versioned release sections; projects without library
   versions use ISO-date sections. Core also includes `python-libs` for the always-on
   helper index and disclosed implementations. Core also includes `python-stdlib-first-review`
   (copy the whole skill dir): on-demand Suggest-mode review that replaces
   hand-rolled loops and caches with itertools, functools, cachetools,
   collections, heapq, bisect, and operator. Core `python-architecture` is one rule dir with seven
   sibling rule files: `python-architecture.mdc` (module layout),
   `python-entity.mdc` (rich Entity domain model — identity, invariants, behavior; the
   `domain` layer replaces the former Service layer and `service.py`),
   `python-exceptions.mdc`
   (AppError), `python-settings.mdc` (pydantic-settings, `Settings().PARAM`),
   `python-logging.mdc` (`dictConfig` / `setup_logging()`), `python-di.mdc` (Container,
   LazyInit), and `python-development-rules.mdc` (general conventions, configurable module
   log levels). Copy only the `.mdc` files; catalog-only `MIGRATION.md` is never copied or
   read during a normal install — on an explicit `Service → Entity migration` request,
   read `harnesses/rules/python-architecture/MIGRATION.md` from the catalog and agree a
   separate migration plan. Domain annotations follow the `domain-types-linter` skill. Call-site hygiene stays
   in `python-tooling`, and adapter rules own
   library-specific logger names and levels.
   Add `python-freezegun` (`freeze_time` in tests, `uv add --dev freezegun`) and
   `python-polyfactory` (`uv add --dev polyfactory`) with every automated-test
   bundle; do not ask about either separately. Each remains its own core ID, not folded into
   `python-tests`. Add `python-semver` when the repo is (or will be)
   a publishable Python library with a declared public API (PyPI package, reusable SDK, shared
   lib); skip it for internal apps/services that are not versioned for external consumers.
   A database answer selects `python-sqlalchemy`, the `sqlalchemy` best-practices
   skill (copy the whole skill dir with `references/`), `python-db-sessions`,
   and `python-alembic` together. Only that ORM bundle adds `FACTORIES_ORM.md` to the
   Polyfactory rule and merges its template; persisted factories use `atransaction()` / `asession()`.
   Do not offer the stack as one catch-all ID.
5. Filter out entries that clearly do not fit the repo. Classify every catalog
   ID as **install**, **skip**, or **ask**, with one evidence-based reason.
6. Run the deterministic onboarding below. Traverse its capability tree in
   order, then derive harness bundles from the combined answers. Do not ask
   separately about a harness whose selection follows from an earlier answer.
7. Render the preflight plan: detected facts, proposed IDs, exact source →
   target writes, dependency/tool notes, companion merges, and existing-file
   conflicts. Resolve every **ask** item and conflict before proceeding.
8. Get one explicit approval for that exact plan. A changed answer requires a
   refreshed plan and approval; approval of a band or ID alone is not approval
   to overwrite an existing target.
9. For **installable** rows, copy `Install from` source → target (see below).
   Kind means this repo is the artifact source of truth. After copying
   `python-tests`, patch the installed `python-tests.mdc` and merge conftest /
   factory templates only for harnesses the user approved — follow sibling
   `COMPANION.md` in the catalog `python-tests` rule dir (catalog-only; do not
   copy it to the target). Skip every companion block for a harness that was not
   approved. Typical merges:
   - `python-fsm` → render `harnesses/rules/python-libs/FSM.md` into
     `project/libs/fsm.py`;
   - `python-retry` → render `harnesses/rules/python-libs/RETRY.md` into
     `project/libs/retry.py`;
   - `python-sqlalchemy` → `BASE_MODELS.md` into `project/base/models.py`; add
     `BASE_REPOSITORIES.md` only when multiple repositories share the base;
   - `python-db-sessions` → `DATABASE.md` into
     `project/infrastructure/adapters/database.py`;
   - `python-redis` → adapter code from `CACHE.md` into
     `project/infrastructure/adapters/acache.py` and `CacheRepository` into
     `project/base/repositories.py`;
   - `python-polyfactory` → install the single `python-polyfactory.mdc` rule and merge
     `FACTORIES.md` into `tests/factories.py`; omit `FACTORIES_ORM.md` without ORM;
   - `python-polyfactory` with `python-sqlalchemy` + `python-db-sessions` → install
     `FACTORIES_ORM.md` beside the rule and merge its template into `tests/factories.py`;
   - `python-db-sessions` with `python-sqlalchemy` → `CONFTEST_DATABASE.md` into
     `tests/conftest.py`;
   - `python-redis` → Redis fixtures from `CACHE.md` into `tests/conftest.py`;
   - `python-typer` → render `harnesses/rules/python-typer/CLI_HELPERS.md` into
     `project/infrastructure/base/cli.py` and `CLI_APP.md` into
     `project/infrastructure/apps/cli.py` (copy only if missing);
   - `python-sqladmin` / `python-fastapi-limiter` → no
     templates; ensure repo-root `layers.toml` carries the `admin` layer (sqladmin
     only) and the matching `sqladmin` / `fastapi_limiter` lib entries
     (substitute `project` if the package name differs);
   - `python-jwt` → render `harnesses/rules/python-libs/SECURITY.md` into
     `project/libs/security.py`; ensure repo-root `layers.toml` carries the
     `jwt` / `pwdlib` lib entries (substitute `project` if the package name differs).
   For `python-base-client`, render only the implementation selected by the user from
   `harnesses/rules/python-libs/` (`ASYNC_CLIENT.md` or `SYNC_CLIENT.md`) into
   `project/infrastructure/base/http_client.py`; never merge both implementations.
   If `di-linter` is approved, after copying it, follow that skill's
   companion-rule patch so installed `python-architecture` /
   `python-tests` name it next to the other linters. Skip the patch when
   `di-linter` was not approved.
   For `layers-linter` / `di-linter` / `dddlint`, copy the sibling config
   (`layers.toml` / `di.toml` / `dddlint.yaml`) to the target repo
   root when missing (substitute `project` if the package name differs).
   When `python-tooling` is approved and Ruff, Black, or isort is being installed,
   read sibling `PYPROJECT.toml` and merge only the selected tools' `[tool.*]`
   tables into the target `pyproject.toml`. Adapt package paths. Set Ruff's
   `target-version` to the repository's minimum supported Python version: infer
   it from existing project metadata or consistent runtime / CI configuration;
   ask the developer when it is absent or ambiguous. Preserve existing tool
   tables; show conflicts and ask whether to merge, replace, or skip them.
   Also render sibling `PRE_COMMIT.yaml` into repo-root
   `.pre-commit-config.yaml`: adapt package and test paths, omit test paths when
   automated tests are not selected, omit the layers hook unless `layers-linter`
   is selected, omit the `dddlint` hook unless `dddlint` is selected, and keep
   each `uv export` hook only when the target maintains
   that requirements file or the user approves creating it. Treat an existing
   pre-commit config as a merge / replace / skip conflict.
10. For hybrid rows, print the upstream URL and tool install notes; still copy
    the skill/rule from this catalog when Kind is installable.
11. Preserve existing files. If a target exists, show the conflict and ask
    whether to merge, replace, or skip it. The version stamp file may be
    overwritten without asking when at least one approved installable path
    was copied or replaced in this run.
12. After any successful installable copy/replace in this run, write the
    cloned catalog `VERSION` contents (trimmed) to
    `.cursor/python-harness-version` (or `~/.cursor/python-harness-version`
    for personal install). Do not invent a second stamp format.
13. Report installed, referenced (manual), skipped, and unresolved items.
    Include **installed catalog version** (stamp just written or unchanged)
    and **source catalog version** from the clone.
14. Remind the user that installed copies drift: re-run this skill (or
    re-copy approved installable paths) from
    `https://github.com/pavelmaksimov/python-harness` when the local stamp
    differs from source `VERSION`. Prefer replacing only the previously
    approved IDs unless the user wants a new selection.

The setup is complete when every approved installable file is installed or
explicitly skipped, every approved hybrid entry has tool install notes shown,
the version stamp is written after a successful installable copy (or already
matched when nothing was copied), and the periodic-update reminder has been
given.

## Deterministic onboarding

Before the first question, show this compact preflight in order:

1. **Target:** repository path, project/personal scope if known, installed and
   source catalog versions.
2. **Detected:** package root, minimum Python version, configured tooling,
   framework/adapters, test signals, library/service status, and existing
   harness files. Mark each fact as detected or unknown and cite its source
   file or path.
3. **Selection:** every catalog ID under **install**, **skip**, or **ask**, with
   a one-line reason. Never silently omit an ID.

This is a capability tree, not a checklist of harness IDs. Ask unresolved
top-level stages first, in order, and ask a branch question only when its
parent capability is selected. Combine independent unresolved questions into
one numbered batch when the interface allows it. Add detected evidence to the
wording and skip any question with one unambiguous repository-derived answer.

| Stage | Requirement | Concrete question and options |
|---:|---|---|
| 1 | Install scope | Install into this repository (`.cursor/`, recommended) or personally (`~/.cursor/`)? |
| 2 | Library | Is this project a publishable library? **yes / no** |
| 3 | Application type | What kind of application is it? **FastAPI API / Telegram bot / CLI (Typer) / a combination / neither (worker or library only)** |
| 4 | Test strategy | Will this project have automated tests? **yes / no** |
| 5 | Coverage gate | Only when stage 4 = yes: enforce a coverage gate with `python-coverage`? **full mode (branch ≥95%) / diff mode — changed lines only, for a legacy baseline / no** |
| 6 | Database | Will this project need a database? **yes / no** |
| 7 | Redis cache | Will this project use Redis as a cache? **yes / no** |
| 8 | Admin panel | Only when stage 3 selects a FastAPI API and stage 6 = yes: does the service need an operator admin panel (`python-sqladmin`, SQLAlchemy models only)? **yes / no** |
| 9 | Rate limiting | Only when stage 3 selects a FastAPI API: rate-limit inbound routes with `python-fastapi-limiter`? **yes / no** — yes installs it with `python-redis` even when the cache itself is not used |
| 10 | User authentication | Only when stage 3 selects a FastAPI API and stage 6 = yes: authenticate users with JWT access tokens (`python-jwt`, PyJWT + pwdlib Argon2; designs the `User` model fields)? **yes / no** |
| 11 | Prometheus monitoring | Does this project need Prometheus monitoring? **yes / no** |
| 12 | Speech I/O | Does this project need speech processing? **none / STT / TTS / both** |
| 13 | Outbound HTTP | Will it call external HTTP APIs? **no / async `httpx.AsyncClient` / sync `httpx.Client`** |
| 14 | Enforcement | Beyond **standard enforcement** (`layers-linter`, `domain-types-linter`, and `patch-linter` when tests are selected), add **strict DI** (`di-linter`, DI001/DI002) and/or **unique names** (`dddlint`, one name = one definition)? **none / di-linter / dddlint / both** |
| 15 | Tooling | If intent is ambiguous: add **detected tool tables only / Ruff + Black + isort / none**; ask for Ruff's minimum Python target only when it cannot be inferred. |
| 16 | Changelog | Maintain notable post-task changes with `keep-a-changelog`? **yes / no** |

Ask stages 2–12 and 16 explicitly unless the user's request already contains
the answer. Repository evidence supplies a recommended answer, not a reason to
hide these product decisions. Stage 5 is asked only after stage 4 = yes; its
"no" answer installs nothing coverage-related. Stages 8–10 are asked only
when stage 3 selects a FastAPI API; stages 8 and 10 additionally require
stage 6 = yes.
Stage 16 is an independent
optional choice and never auto-installs a skill.

Derive the install set mechanically from the answers:

| Requirement | Automatically selected harnesses and companions |
|---|---|
| Python project | Base core: `conventional-commits`, `python-tooling`, `python-workflow`, `python-libs`, `python-architecture` (seven sibling rule files: structure, entity, exceptions, settings, logging, DI, development rules), `python-fsm`, `python-retry`, `python-stdlib-first-review` (whole skill dir); plus `layers-linter` and `domain-types-linter` |
| Publishable library | `python-semver` |
| Automated tests | `python-tests` + `python-freezegun` + `python-polyfactory` + `patch-linter`; merge `FACTORIES.md` into `tests/factories.py` |
| Coverage gate approved (stage 5) | `python-coverage`; merge `[tool.coverage.*]` from `python-coverage/PYPROJECT.md` into repo-root `pyproject.toml`; package notes `uv add --dev pytest-cov`, plus `uv add --dev diff-cover` in diff mode; companion patches per catalog `COMPANION.md` (pointer row in `python-tests.mdc` + "Coverage gate after a task" in `.cursor/rules/python-workflow/`) |
| Database | `python-sqlalchemy` + `sqlalchemy` skill (whole dir incl. `references/`) + `python-db-sessions` + `python-alembic` |
| Database + automated tests | Add and merge `FACTORIES_ORM.md`; merge database fixtures from `CONFTEST_DATABASE.md` |
| Admin panel approved (stage 8) | `python-sqladmin`; requires the Database bundle; no templates |
| Redis cache | `python-redis`; when automated tests are selected, also merge Redis fixtures |
| Rate limiting (stage 9) | `python-fastapi-limiter` + `python-redis` (shared Redis client and `REDIS_*` Settings), even when the cache itself is not used; no templates |
| User authentication (stage 10) | `python-jwt`; requires the Database bundle; render `python-libs/SECURITY.md` into `project/libs/security.py`; packages `uv add pyjwt "pwdlib[argon2]"` |
| FastAPI API | `python-fastapi` |
| Prometheus monitoring | `python-monitoring` and its upstream package notes |
| STT, TTS, or both | `python-libs` speech template `python-libs/SPEECH.md`; install only the selected provider/media dependencies |
| Outbound HTTP | `python-base-client` with exactly the chosen async or sync template |
| Telegram bot | `python-telegram` |
| CLI (stage 3) | `python-typer`; render `python-typer/CLI_HELPERS.md` into `project/infrastructure/base/cli.py` and `CLI_APP.md` into `project/infrastructure/apps/cli.py`; add the `cli-design` skill for on-demand interface design and review |
| Strict DI enforcement | `di-linter` and its companion-rule patches |
| Unique-name enforcement (stage 14) | `dddlint`; copy sibling `dddlint.yaml` to repo-root `dddlint.yaml` when missing |
| Changelog approved (stage 16) | `keep-a-changelog`; use versioned-library mode when stage 2 = yes, otherwise dated-project mode |

Do not ask whether to install an automatically derived harness. Show the
derivation (for example, `automated tests → python-polyfactory`)
in the preflight plan; the final plan approval approves those derived IDs too.
Use **revise** when the user wants an exception to a derived bundle.

After the answers, show the exact write plan grouped as **copy**, **merge**,
**replace**, **manual upstream step**, and **skip**. For each existing target,
ask one concrete conflict question: **merge / replace / skip**; ask separately
per conflicting `pyproject.toml` tool table. Then ask: “Apply this exact plan?”
with **yes / revise**. Write nothing to the target before this approval.

## Catalog version

One shared semver for the whole catalog (not per ID):

| Location | Role |
|---|---|
| Source root `VERSION` | Latest catalog release |
| Target `.cursor/python-harness-version` | Version last installed in that project |
| Target `~/.cursor/python-harness-version` | Same for a personal install |

Keep the stamp as a single line matching `VERSION`. Compare it to the clone
before recommending updates.

## How to read the README catalog

Each band section has a table with:

| Column | Meaning |
|---|---|
| ID | Stable id used in recommendations |
| Kind | `installable` or `reference` |
| Upstream | Canonical project / spec URL |
| Install from / Notes | Copy mapping `source → target`, or manual install notes |

Installable artifacts are grouped by type under `harnesses/`:

```text
harnesses/skills/<id>/   → .cursor/skills/<id>/
harnesses/rules/<id>/    → .cursor/rules/<id>/
harnesses/hooks/<id>/    → .cursor/hooks/<id>/   # or project hooks layout
harnesses/agents/<id>/   → .cursor/agents/<id>/  # sub-agents
```

Default for an installable **skill** with id `<id>`:

```text
harnesses/skills/<id>/SKILL.md → .cursor/skills/<id>/SKILL.md
```

If the table shows an explicit `source → target`, use that. For personal
install, replace `.cursor/` with `~/.cursor/` (or the Claude / Codex
equivalent).

Resolve relative source paths from the cloned catalog root and targets from
the target repository root (or home for personal installs).

## Safety

- Keep the target repository's conventions authoritative.
- Install only files under `harnesses/{skills,rules,hooks,agents}/` for
  selected installable entries (plus the version stamp path above).
- Never copy or recreate upstream/reference packs into the catalog repo.
- Require approval before overwriting, deleting, or changing existing content
  (except refreshing `python-harness-version` after an approved installable
  copy in the same run).
- Do not copy credentials, local absolute paths, generated output, or source
  repository Git metadata.
- Remove the temporary clone after the result is reported.
