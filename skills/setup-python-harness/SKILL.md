---
name: setup-python-harness
description: Recommends and installs the opinionated Python backend harness from pavelmaksimov/python-harness. Use when bootstrapping Python agent rules, linter skills, or stack bands in a new repository.
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
   `infrastructure/adapters/` — skip it when there are none), and
   `layers-linter` and `domain-types-linter` with the stack; add `patch-linter`
   when automated tests are selected.
   Offer `di-linter` as optional (Container/LazyInit, DI001/DI002). Recommend
   Ask whether Prometheus monitoring is needed; when yes, add
   `python-monitoring` (`uv add llm_common prometheus_client` — PyPI
   `llm_common`, not `pycommons`). Core includes
   `python-settings` (pydantic-settings, `Settings().PARAM`) as its own ID, not as
   part of `python-di`. Core includes `python-development-rules` for general Python
   conventions and configurable module log levels. Core includes `python-logging` (`dictConfig` /
   `setup_logging()`) as its own technology-neutral ID; call-site hygiene stays in
   `python-tooling`, and adapter rules own library-specific logger names and levels.
   Add `python-freezegun` (`freeze_time` in tests, `uv add --dev freezegun`) with
   every automated-test bundle. Add `python-polyfactory` (`uv add --dev polyfactory`)
   automatically when automated tests and a database are both selected;
   do not ask about it separately. Each remains its own core ID, not folded into
   `python-tests`. Add `python-semver` when the repo is (or will be)
   a publishable Python library with a declared public API (PyPI package, reusable SDK, shared
   lib); skip it for internal apps/services that are not versioned for external consumers.
   A database answer selects `python-sqlalchemy`, `python-db-sessions`, and
   `python-alembic` together. Persisted ORM factories use `atransaction()` /
   `asession()`, not a private sessionmaker.
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
   - `python-sqlalchemy` → `BASE_MODELS.md` into `project/components/base/models.py`; add
     `BASE_REPOSITORIES.md` only when multiple repositories share the base;
   - `python-db-sessions` → `DATABASE.md` into
     `project/infrastructure/adapters/database.py`;
   - `python-redis` → adapter code from `CACHE.md` into
     `project/infrastructure/adapters/acache.py` and `CacheRepository` into
     `project/components/base/repositories.py`;
   - `python-polyfactory` → `FACTORIES.md` into `tests/factories.py`;
   - `python-db-sessions` with `python-sqlalchemy` → `CONFTEST_DATABASE.md` into
     `tests/conftest.py`;
   - `python-redis` → Redis fixtures from `CACHE.md` into `tests/conftest.py`.
   For `python-base-client`, copy only the implementation selected by the user
   (`ASYNC_CLIENT.md` or `SYNC_CLIENT.md`) into
   `project/infrastructure/utils/base_client.py`; never merge both implementations.
   If `di-linter` is approved, after copying it, follow that skill's
   companion-rule patch so installed `python-structure` / `python-di` /
   `python-tests` name it next to the other linters. Skip the patch when
   `di-linter` was not approved.
   For `layers-linter` / `di-linter`, copy the sibling toml to the target repo
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
   is selected, and keep each `uv export` hook only when the target maintains
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
| 3 | Application type | What kind of application is it? **FastAPI API / Telegram bot / both / neither (worker, CLI, or library only)** |
| 4 | Test strategy | Will this project have automated tests? **yes / no** |
| 5 | Database | Will this project need a database? **yes / no** |
| 6 | Redis cache | Will this project use Redis as a cache? **yes / no** |
| 7 | Prometheus monitoring | Does this project need Prometheus monitoring? **yes / no** |
| 8 | Outbound HTTP | Will it call external HTTP APIs? **no / async `httpx.AsyncClient` / sync `httpx.Client`** |
| 9 | Enforcement | Use **standard enforcement** (`layers-linter`, `domain-types-linter`, and `patch-linter` when tests are selected) or **strict DI enforcement** (standard + `di-linter`)? |
| 10 | Tooling | If intent is ambiguous: add **detected tool tables only / Ruff + Black + isort / none**; ask for Ruff's minimum Python target only when it cannot be inferred. |

Ask stages 2–7 explicitly unless the user's request already contains the
answer. Repository evidence supplies a recommended answer, not a reason to
hide these product decisions.

Derive the install set mechanically from the answers:

| Requirement | Automatically selected harnesses and companions |
|---|---|
| Python project | Base core: `python-tooling`, `python-development-rules`, `python-structure`, `python-exceptions`, `python-settings`, `python-logging`, `python-di`, `python-fsm`, `python-retry`; plus `layers-linter` and `domain-types-linter` |
| Publishable library | `python-semver` |
| Automated tests | `python-tests` + `python-freezegun` + `patch-linter` |
| Database | `python-sqlalchemy` + `python-db-sessions` + `python-alembic` |
| Database + automated tests | `python-polyfactory`; merge its factory companion and database fixtures from `CONFTEST_DATABASE.md` |
| Redis cache | `python-redis`; when automated tests are selected, also merge Redis fixtures |
| FastAPI API | `python-fastapi` |
| Prometheus monitoring | `python-monitoring` and its upstream package notes |
| Outbound HTTP | `python-base-client` with exactly the chosen async or sync template |
| Telegram bot | `python-telegram` |
| Strict DI enforcement | `di-linter` and its companion-rule patches |

Do not ask whether to install an automatically derived harness. Show the
derivation (for example, `automated tests + database models → python-polyfactory`)
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
