# python-tests companion patches

Apply after copying harness rules to the target repo. Patch only IDs the user approved.
Skip every block for a harness that was not installed. Do not copy this file to the target.

Source: catalog `harnesses/rules/python-tests/`. Targets: `.cursor/rules/python-tests/python-tests.mdc`
and, for the `python-coverage` block only, `.cursor/rules/python-workflow/python-workflow.mdc`
(plus `tests/conftest.py` / `tests/factories.py` as noted).

## `python-polyfactory`

Copy `python-polyfactory/FACTORIES.md` → `tests/factories.py` if missing (merge).
Factory rules stay in the separately installed `python-polyfactory.mdc`; do not duplicate them
in `python-tests.mdc`.

When `python-sqlalchemy` and `python-db-sessions` are approved, also copy
`FACTORIES_ORM.md` beside the Polyfactory rule and merge its template into
`tests/factories.py`.

## `python-freezegun`

When approved, install the rule dir only (no `python-tests.mdc` body patch required beyond the pointer table).

Patch `python-tests.mdc` — after the patch-linter pairing line, add:

```markdown
Freeze "now" with `python-freezegun` (`freeze_time`), not `patch(datetime)`.
```

## `python-db-sessions`

When `python-db-sessions` and `python-sqlalchemy` are approved, merge sibling
`CONFTEST_DATABASE.md` into `tests/conftest.py` if missing (merge).

Patch `python-tests.mdc`:

1. In the **Modular** bullet, after `No real network, credentials, or live SaaS.`, add:

```markdown
 Testcontainers Postgres via `asession` is allowed here.
```

2. Append before **Optional harnesses**:

```markdown
## Database tests

Session-scoped Testcontainers Postgres; per-test `asession` with a nested transaction and rollback
(see `CONFTEST_DATABASE.md`). Put row data in the test (or a factory `create_async` while `asession`
is active — `python-polyfactory` when installed), not in the DB fixture. After a DSN change, call
`cache_clear()` on the engine and sessionmaker factories.
```

## `python-redis`

When approved, merge the **Test fixtures** block from `python-redis/CACHE.md` into
`tests/conftest.py` if missing (merge).

Patch `python-tests.mdc`:

1. In the **Modular** bullet, after `No real network, credentials, or live SaaS.`, add:

```markdown
 Testcontainers Redis via `python-redis` is allowed here.
```

2. Append before **Optional harnesses** (after **Database tests** when that section exists):

```markdown
## Cache tests

Session-scoped Testcontainers Redis; `flushdb` per test (fixtures in `python-redis` / `CACHE.md`).
After a host override, `redis_client.cache_clear()`.
```

## `python-coverage`

Optional harness — apply this whole block only when the user approves it.
When not approved: no pointer-table row in `python-tests.mdc`, no workflow
patch, no config merge.

When approved:

1. Install the skill dir (`SKILL.md` → `.cursor/skills/python-coverage/`). The
   sibling `PYPROJECT.md` stays catalog-side: merge its `[tool.coverage.*]`
   tables into repo-root `pyproject.toml` if missing (merge; ask before
   replacing existing tables). Add `uv add --dev pytest-cov`; add
   `uv add --dev diff-cover` only when the user picks diff mode (legacy
   baseline); no diff-cover config table exists — the skill passes CLI flags.
2. Patch `python-tests.mdc` — add the pointer-table row only.
3. Append to `.cursor/rules/python-workflow/python-workflow.mdc`:

```markdown
## Coverage gate after a task

After finishing a task that changed Python modules under `project/`, run the
coverage skill before reporting completion:

1. Run `.cursor/skills/python-coverage/` (`python-coverage`): pytest with
   coverage on the modular suite, gated per its mode (`fail_under`, or
   `diff-cover` over changed lines).
2. If the gate fails, close the reported gaps with tests first — the skill's
   workflow defines how.

Do not report the task complete while the coverage gate fails or while lines
changed by this task remain uncovered. If the skill is not installed, skip
this step.
```

Without approval nothing is appended to `python-workflow.mdc` — the rule stays
as shipped.

## `di-linter`

When approved, follow `di-linter/SKILL.md` — after the patch-linter pairing line in `python-tests.mdc`, add:

```markdown
Pair with `di-linter` (DI002).
```
