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
   (the **Catalog** section is the source of truth).
3. Present harnesses by band: **core**, **adapters**, **enforcement**. Recommend
   core for any Python repo, adapters that match the codebase (FastAPI,
   SQLAlchemy, Redis; Alembic when the repo already has `alembic/` or
   `alembic.ini`; Telegram when the repo uses python-telegram-bot, `apps/bot.py`,
   or component `handlers.py` — skip `python-telegram` when there is no Telegram
   bot; `python-base-client` when the repo has outbound HTTP adapters under
   `infrastructure/adapters/` — skip it when there are none), and
   `layers-linter` plus `domain-types-linter` with the stack. Offer `di-linter`
   as optional (Container/LazyInit, DI001/DI002). Recommend `python-monitoring`
   when the repo scrapes Prometheus, exposes `/prometheus`, or wants `llm_common`
   metrics (`uv add llm_common prometheus_client` — PyPI `llm_common`, not
   `pycommons`); skip it when the repo does not scrape Prometheus. Core includes
   `python-settings` (pydantic-settings, `Settings().PARAM`) as its own ID, not as
   part of `python-di`. Core includes `python-logging` (`dictConfig` /
   `setup_logging()`) as its own ID; call-site hygiene stays in `python-tooling`.
   Core includes `python-freezegun` (`freeze_time` in tests, `uv add --dev freezegun`) as its own
   ID, not as part of `python-tests`.
   Do not offer the stack as one catch-all ID.
4. Filter out entries that clearly do not fit the repo.
5. Ask the user only about choices that cannot be inferred:
   - which bands / adapters matter for this repo;
   - project-only or personal installation;
   - whether to add optional `di-linter`.
6. Recommend the smallest compatible set. For each item, state the benefit,
   install path or upstream link, and conflicts with already-present skills.
7. Get explicit approval for the final set.
8. For **installable** rows, copy `Install from` source → target (see below).
   Kind means this repo is the artifact source of truth. If `di-linter` is
   approved, after copying it, follow that skill's companion-rule patch so
   installed `python-structure` / `python-di` / `python-tests` name it next to
   the other linters. Skip the patch when `di-linter` was not approved.
   For `layers-linter` / `di-linter`, copy the sibling toml to the target repo
   root when missing (substitute `project` if the package name differs).
9. For hybrid rows, print the upstream URL and tool install notes; still copy
   the skill/rule from this catalog when Kind is installable.
10. Preserve existing files. If a target exists, show the conflict and ask
    whether to merge, replace, or skip it.
11. Report installed, referenced (manual), skipped, and unresolved items.
12. Remind the user that installed copies drift: periodically re-run this skill
    (or re-copy approved installable paths) from
    `https://github.com/pavelmaksimov/python-harness` so the target stays aligned
    with the catalog. Prefer replacing only the previously approved IDs unless
    the user wants a new selection.

The setup is complete when every approved installable file is installed or
explicitly skipped, every approved hybrid entry has tool install notes shown,
and the periodic-update reminder has been given.

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
  selected installable entries.
- Never copy or recreate upstream/reference packs into the catalog repo.
- Require approval before overwriting, deleting, or changing existing content.
- Do not copy credentials, local absolute paths, generated output, or source
  repository Git metadata.
- Remove the temporary clone after the result is reported.
