# python-tests companion patches

Apply after copying harness rules to the target repo. Patch only IDs the user approved.
Skip every block for a harness that was not installed. Do not copy this file to the target.

Source: catalog `harnesses/rules/python-tests/`. Target: `.cursor/rules/python-tests/python-tests.mdc`
(and `tests/conftest.py` / `tests/factories.py` as noted).

## `python-polyfactory`

When approved, copy `python-polyfactory/FACTORIES.md` → `tests/factories.py` if missing (merge).

Patch `python-tests.mdc`:

1. After the first `Read tests/conftest.py` paragraph, add:

```markdown
Read `tests/factories.py` before adding data helpers.
```

2. In **What belongs where**, add a row after the `tests/conftest.py` row:

```markdown
| `tests/factories.py` | Polyfactory classes (`python-polyfactory`) — `build(**overrides)` in memory, `create_async` to persist when `python-sqlalchemy` is installed |
```

3. After `Duplicate literals in tests are fine.`, add:

```markdown
Prefer a factory class call in the test (`UserFactory.build(...)`, `python-polyfactory`) over a shared data fixture.
A new ORM model or request schema also gets a factory class in `tests/factories.py`.
```

4. In the layout tree, after `conftest.py`, add:

```markdown
  factories.py
```

5. After the patch-linter pairing line, add:

```markdown
Build test data with `python-polyfactory` (`build` / `create_async`), not `make_*` helpers.
```

## `python-freezegun`

When approved, install the rule dir only (no `python-tests.mdc` body patch required beyond the pointer table).

Patch `python-tests.mdc` — after the patch-linter pairing line, add:

```markdown
Freeze "now" with `python-freezegun` (`freeze_time`), not `patch(datetime)`.
```

## `python-sqlalchemy`

When approved, merge sibling `CONFTEST_DATABASE.md` into `tests/conftest.py` if missing (merge).

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

## `di-linter`

When approved, follow `di-linter/SKILL.md` — after the patch-linter pairing line in `python-tests.mdc`, add:

```markdown
Pair with `di-linter` (DI002).
```
