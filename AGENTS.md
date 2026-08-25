# AGENTS.md — python-harness

Public catalog of the opinionated Python backend agent harness. English for
repo docs and skills unless the user asks otherwise.

The Python stack is owned here. Non-Python harnesses and general agent catalog
entries live in [agent-setup](https://github.com/pavelmaksimov/agent-setup).

## Sources of truth

- **Catalog:** `README.md` → section **Catalog**. Do not recreate `catalog.yaml`.
- **Catalog version:** root `VERSION` (semver). Mirror the same string in the
  README **Catalog version** line. Do not invent a second version format.
- **Bootstrap skill:** `skills/setup-python-harness/SKILL.md`.
- **Installable artifacts:** only under typed dirs in `harnesses/`.

When the catalog and a local copy disagree, fix the README and remove the stale
copy. Do not invent a second catalog format.

## Layout

```text
VERSION                           catalog semver (source of truth for version)
README.md                         human + agent catalog (+ mirrored version line)
AGENTS.md                         rules for working in this repo
skills/setup-python-harness/      bootstrap / recommend / install skill
.cursor/rules/<id>/               always-on rules for editing this repo (not catalog)
harnesses/
  skills/<id>/SKILL.md            installable skills
  rules/<id>/                     installable rules
  hooks/<id>/                     installable hooks
  agents/<id>/                    installable sub-agents
```

Empty typed dirs may keep a `.gitkeep`. Do not put installable content at
`harnesses/<id>/` without a type folder.

Always-on Cursor rules for agents editing this catalog live in `.cursor/rules/`
(for example `propose-conventional-commit`). Keep them in git so they apply
here. Do not copy them into `harnesses/` unless the user asks to add that ID
to the Python catalog.

## Catalog version

One shared version for the whole installable set (not per ID).

- Bump root `VERSION` and the README **Catalog version** line together when
  installable harnesses, the setup skill, or catalog install semantics change.
- Docs-only edits that do not change what gets copied may leave the version
  unchanged.
- On install, the setup skill stamps the target with
  `.cursor/python-harness-version` (or `~/.cursor/...` for personal install)
  containing the same single-line semver. That stamp is how a local snapshot
  is compared to this source.

## Kind

| Kind | Meaning |
|---|---|
| **installable** | This repo owns the artifact. Copy from `harnesses/<type>/<id>/`. |
| **reference** | Upstream owns the product. Link + notes only. |

Rules:

- Kind answers where the **product** is installed from, not whether a helper
  file happens to exist here.
- Never vendor upstream/reference skills, rules, hooks, or agents into
  `harnesses/`.
- Hybrid case (e.g. `layers-linter`, `domain-types-linter`, `patch-linter`,
  `di-linter`, `python-monitoring`): tool from upstream; skill or rule from this
  repo under the matching typed dir. State both in the README Notes column.

## Language stack bands

This catalog is one language stack, split into layered IDs:

- **core** — tooling, `python-development-rules`, structure, exceptions, settings, logging, DI, FSM, retry,
  tests, frozen clock, Polyfactory (language-wide); `python-semver` when the
  repo is a publishable library
- **adapters** — HTTP, persistence, cache, monitoring, Telegram (only if the
  repo uses them)
- **enforcement** — matching linter skills; take `layers-linter` and
  `domain-types-linter` with the stack, add `patch-linter` with automated tests,
  and use `di-linter` for optional strict DI enforcement

Do not collapse the stack into one catch-all rule ID or a comma-separated
library list after the table. Templates (`PYPROJECT.toml`, `PRE_COMMIT.yaml`, `SETTINGS.md`, `LOGGER.md`,
`STRUCTURES.md`, `BASE_MODELS.md`, `BASE_REPOSITORIES.md`, `BASE_SCHEMAS.md`,
`FSM.md`, `RETRY.md`,
`DATABASE.md`, `ENV.md`, `CACHE.md`, `CONFTEST.md`, `FACTORIES.md`, `BOT.md`,
`TELEGRAM.md`, `ASYNC_CLIENT.md`, `SYNC_CLIENT.md`) live in the rule dir they
belong to; mention the copy path on that band. Disclosed agent reference next
to a rule (e.g. Polyfactory `FIELDS.md`, `CUSTOM_TYPES.md`) is not an install
template unless the README copy list names it. Linter configs (`layers.toml`,
`di.toml`) live next to their skills and copy to the target repo root.

## Adding or changing catalog entries

1. Edit the matching band table in `README.md` (core / adapters / enforcement).
2. If Kind is **installable**, add files under the correct typed dir and set
   `Install from` as `source → target`.
3. If Kind is **reference**, add Upstream + Notes only — no `harnesses/` copy.
4. Keep IDs stable (`kebab-case`), summaries short, no secrets.
5. Update `skills/setup-python-harness/SKILL.md` when install layout or Kind
   semantics change. For every added or changed catalog ID, also update the
   **Deterministic onboarding** capability tree and derivation table when its
   requirement, dependency bundle, or non-inferable choice changes.
6. When the change affects installable content, the setup skill, or install
   semantics, bump root `VERSION` and the README **Catalog version** line
   together (semver).

Default Cursor install targets:

```text
harnesses/skills/<id>/  → .cursor/skills/<id>/
harnesses/rules/<id>/   → .cursor/rules/<id>/
harnesses/hooks/<id>/   → .cursor/hooks/<id>/
harnesses/agents/<id>/  → .cursor/agents/<id>/
```

After a successful installable copy, the setup skill also writes
`.cursor/python-harness-version` from root `VERSION`.
## Authoring installable rules

- One catalog ID per directory: `harnesses/rules/<id>/` with one or more `.mdc`
  files. That ID is one layer, not the whole stack.
- Frontmatter: `description`, and either `alwaysApply: true` or `globs`.
- Guidance needed outside its `globs` must have a trigger pointer in an
  `alwaysApply: true` base rule.
- English bodies. Default package root is `project/`; note in the README if the
  installer should substitute.
- One concern per `.mdc`. Name the layer (tooling, HTTP, persistence); leave
  version pins and Ruff selects to the target `pyproject.toml`.
- `python-tooling/PRE_COMMIT.yaml` renders to repo-root
  `.pre-commit-config.yaml`; adapt package/test paths and keep only hooks
  selected by the target workflow.
- Env config (`pydantic-settings`, `Settings().PARAM`) is its own core ID
  (`python-settings`). `python-di` owns Container and LazyService. Do not fold
  Settings into DI.
- DI examples call a single-use dependency through `Container()` inline; bind
  the dependency only when it is reused.
- Clock in tests (`freezegun` `freeze_time`) is its own core ID
  (`python-freezegun`). Do not fold it into `python-tests`.
- Test data factories (Polyfactory `build` / `create_async`) is its own core ID
  (`python-polyfactory`). Do not fold it into `python-tests`. Persist ORM rows
  through `asession` / `atransaction` (`python-db-sessions`), not a private
  sessionmaker.
- `python-sqlalchemy` owns ORM models, shared ORM bases, and generic repositories.
  `python-db-sessions` owns the engine, session/transaction lifecycle, and database
  Settings contract. Keep both concerns out of `python-structure`.
- Shared domain base modules live in `project/base/`. Infrastructure helpers live in
  `project/infrastructure/base/`: `http_client.py` is an adapter and `telegram.py` is presentation.
- `python-redis` keeps `CacheRepository` in `project/base/repositories.py`;
  `project/infrastructure/adapters/acache.py` owns only the Redis client and transactions.
- Library release versioning (SemVer 2.0) is its own core ID (`python-semver`).
  Install only when the target is a publishable library; do not fold it into
  `python-tooling` or service stacks.
- Optional enforcement (`di-linter`) and test companion harnesses
  (`python-freezegun`, `python-polyfactory`, adapter-driven DB/Redis test blocks)
  stay out of default `python-tests` body text. The base rule keeps a short
  pointer table to catalog IDs; detailed sections and conftest fragments are
  applied only when the user approves that ID at install time (`COMPANION.md`
  in the catalog `python-tests` rule dir — installer-only, not copied to target).
  When `di-linter` is added, patch companion rules so they mention it.
- No machine-local absolute paths, source-project product names, or secrets.
- When enriching an installable rule from a source template, map each spec into
  the matching catalog ID. Product metric prefixes belong in
  `python-monitoring`. Leave unmatched concerns (named third-party SaaS auth
  adapters) out until they have their own ID.
- Upstream doc maps for refreshing a rule live in that rule dir as `UPSTREAM.md`
  (local file → upstream URL). Use them only when updating this catalog.
  Do not mention `UPSTREAM.md` from `.mdc` bodies or other agent-facing siblings.

## Authoring installable skills

- One directory per skill: `harnesses/skills/<id>/SKILL.md`.
- Frontmatter: `name`, `description` (third person, what + when).
- Keep `SKILL.md` concise; put long reference in sibling files if needed.
- Prefer English skill bodies in this public repo.
- Linter config templates (`layers.toml`, `di.toml`) and skill examples use
  package root `project/` and `components/`, matching `python-structure`. Do not
  keep a parallel `domains/` layout.

## Bootstrap behaviour

When running or editing the setup skill:

1. Read the README catalog; present options by band (core, adapters,
   enforcement).
2. Ask only what cannot be inferred; get approval before copying files.
3. Derive harness bundles from approved capabilities, then install only the
   resulting approved **installable** paths; for hybrid/upstream tools,
   print install notes. Recommend `layers-linter`, `domain-types-linter`, and
   `patch-linter` when tests are selected. Add `python-freezegun` with every
   automated-test bundle; derive `python-polyfactory` from automated tests plus
   a database instead of asking about it separately. Offer `di-linter`
   as strict enforcement. Ask whether the target is a publishable library and
   add `python-semver` when it is. Ask whether the application is a FastAPI API,
   Telegram bot, both, or neither; a FastAPI API selects `python-fastapi`.
   Ask separately whether Prometheus monitoring is needed and select
   `python-monitoring` only when yes. Ask one yes/no question for a database and select
   `python-sqlalchemy`, `python-db-sessions`, and `python-alembic` together when
   yes. Ask separately whether Redis caching is used. For `python-base-client`,
   ask the developer to choose
   `ASYNC_CLIENT.md` (httpx async) or `SYNC_CLIENT.md` (httpx sync), then copy only that
   implementation to `http_client.py`. Install only when approved. After `python-tests`,
   patch the installed rule and merge conftest/factory templates per catalog
   `COMPANION.md` for each approved optional harness. If `di-linter` is approved,
   patch companion rules in the target so they name it next to the other linters.
   When `python-tooling` installs Ruff, Black, or isort, merge only the selected
   tools' tables from `PYPROJECT.toml` into the target `pyproject.toml`; adapt
   package paths, infer Ruff's minimum Python target from project metadata or
   consistent runtime / CI configuration, ask when ambiguous, and ask before
   changing existing tables.
   Render `PRE_COMMIT.yaml` into `.pre-commit-config.yaml`; adapt package/test
   paths, selected enforcement hooks, and requirements export hooks, and ask
   before changing an existing config.
4. Never overwrite existing target files without asking (except refreshing
   `.cursor/python-harness-version` after an approved installable copy).
5. Do not commit API keys, tokens, or machine-local absolute paths.
6. Compare target `.cursor/python-harness-version` to source `VERSION` when
   present; after install, stamp the target with the source version; report
   both versions and remind the user to re-run when they differ.
## Learn from mismatches

If the result is clearly not what the user needed (wrong Kind, wrong layout,
vendored upstream packs, catalog in the wrong file, etc.):

1. Fix the immediate mistake in the repo.
2. Update **this** `AGENTS.md` with a durable rule that would have prevented it.
3. Keep the new rule short, positive, and checkable — one instruction, not a
   post-mortem essay.
4. Prefer editing an existing section over adding a duplicate.
5. Do this in the same turn when the mismatch is acknowledged; do not wait to
   be asked to “remember” it unless the user declines.

Goal: the next agent session should not repeat the same disagreement.

## Safety and hygiene

- No credentials, tokens, or private URLs in the catalog or harnesses.
- No absolute `/home/...` paths in published files.
- Ignore IDE junk (`.idea/`); keep `.gitignore` current.
- Prefer the smallest change that keeps README, layout, and setup skill aligned.
- Do not turn this repo into an app, CLI installer binary, or package registry
  unless the user explicitly asks.
