# SQLAlchemy ORM query rules

Use the SQLAlchemy 2.x statement API.

## Query API

- Use `select()`, `insert()`, `update()`, and `delete()`.
- Do not introduce `session.query()` in new code.
- Preserve legacy `Query` code only when maintaining an existing legacy
  subsystem and migration is outside the task scope.

Prefer:

- `session.scalars(stmt)` when the statement returns one ORM entity or one
  scalar value per row.
- `session.execute(stmt)` when rows contain multiple entities, expressions,
  tuples, or mappings.
- `scalar_one()` / `scalar_one_or_none()` when exactly one scalar result is
  expected.
- `one()` / `one_or_none()` when query cardinality is an invariant that should
  be checked.
- `Session.get(Model, primary_key)` for direct primary-key lookup.

## Parameterization

- Never build SQL by interpolating user or runtime values into SQL strings.
- Use SQLAlchemy expressions such as:

```python
User.email == email
```

or named bound parameters with `text()` when textual SQL is genuinely
necessary.
- Treat identifiers such as table names, column names, sort expressions, and
  raw SQL fragments separately from data parameters. Never pass untrusted
  identifiers directly into SQL.

## Filtering and joining

- Build predicates with mapped attributes rather than manually constructed SQL
  strings.
- Prefer relationship-aware joins such as `.join(User.orders)` where the
  relationship already represents the desired join.
- Use explicit join conditions when the relationship is absent or the required
  SQL semantics differ.
- Avoid adding JOINs solely to load related objects; use loader options for
  that purpose.

## Relationship loading and N+1

Never ignore the relationship loading strategy.

General defaults:

- For one-to-many and many-to-many collections, prefer `selectinload()` when
  appropriate.
- For many-to-one and other scalar relationships, `joinedload()` is often
  appropriate.
- Use `raiseload()` in query boundaries or tests when accidental lazy loading
  should be treated as a bug.
- If `joinedload()` loads a collection, call `Result.unique()` before consuming
  ORM entities.
- Do not combine joined eager loading with row locking casually; joined tables
  may also be affected by locking depending on the database.

Choose loader strategies per access pattern. Do not solve N+1 by globally
eager-loading every relationship.

## Async queries

With `AsyncSession`:

- Use a separate `AsyncSession` for each concurrent task.
- Never share a single `AsyncSession` among concurrent asyncio tasks.
- Avoid implicit relationship lazy loading.
- Prefer explicit loader options in the query.
- Keep the transaction/session lifetime explicit.

## Transactions and session lifecycle

A `Session` / `AsyncSession` represents a mutable transaction and must have a
clear owner.

- Keep one session per unit of work/request/task as appropriate to the
  application.
- Do not share a session across concurrent threads or asyncio tasks.
- Let the application/service layer define transaction boundaries unless a
  lower-level function explicitly owns the entire unit of work.
- Query/repository helpers should not call `commit()` merely because they
  performed an insert or update.
- Use `flush()` when SQL must be issued before the transaction boundary.
- If `flush()` fails, roll back the transaction before trying to reuse the
  session.
- Use `session.begin()` / `async with session.begin()` when an explicit
  transaction block improves ownership and failure semantics.

## Existence checks and primary-key lookups

- If only existence is required, express an EXISTS query rather than loading
  full ORM objects.
- For direct primary-key lookup, use `Session.get()` rather than constructing
  a general SELECT.

## Result size

Never assume a result set is small.

- Select only the entities or columns the caller needs.
- Apply a bounded `limit()` for APIs that return collections unless unbounded
  behavior is explicitly required.
- Pagination must have deterministic ordering.
- For very large result sets, consider `yield_per` / streaming iteration.
- Do not call `.all()` after configuring `yield_per`; doing so defeats streaming.
- Be aware that `yield_per` is incompatible with some eager-loading strategies,
  especially joined/subquery eager loading of collections and `Result.unique()`.

## Bulk and set-based operations

For many-row writes, prefer SQLAlchemy 2.x ORM-enabled DML:

- `Session.execute(insert(Model), values)`
- `update(Model).where(...).values(...)`
- `delete(Model).where(...)`

- Do not introduce legacy `bulk_insert_mappings()`, `bulk_save_objects()`,
  etc. unless maintaining legacy code with a specific reason.
- Use normal ORM unit-of-work operations when object-level cascades,
  relationship bookkeeping, or per-object behavior is required. Use set-based
  DML when intentionally operating at SQL-set level.

## UPSERT

UPSERT syntax is database-specific.

- Do not invent a generic cross-database UPSERT abstraction unless the project
  already provides one.
- Use the target dialect's supported insert construct and account for its exact
  semantics.
- Never assume Python-side `Column.onupdate` behavior will be applied
  automatically by an UPSERT statement.

## Query review checklist

For every non-trivial query, check:

1. Is it using SQLAlchemy 2.x APIs?
2. Are all runtime values parameterized?
3. Could it create an N+1 pattern?
4. Is the loader strategy appropriate?
5. Are unnecessary ORM entities or columns being loaded?
6. Is cardinality expressed explicitly with `one`, `one_or_none`, etc. where
   useful?
7. Does pagination have deterministic ordering?
8. Could the result become large enough to require streaming or chunking?
9. Does the query rely on database-specific SQL?
10. Does it unexpectedly commit a transaction?
11. Is an `AsyncSession` being shared between concurrent tasks?
12. Would a direct PK lookup be simpler with `Session.get()`?
