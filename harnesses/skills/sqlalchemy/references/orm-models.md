# SQLAlchemy ORM model rules

Target SQLAlchemy 2.x stable APIs. This follows the modern Declarative API:
`DeclarativeBase`, `Mapped[...]`, `mapped_column()`, typed relationships.

## Declarative style

- Use `DeclarativeBase`, `Mapped[T]`, `mapped_column()`, and typed
  `relationship()`.
- Do not introduce legacy `declarative_base()`, untyped declarative mappings,
  or `Column()`-only ORM declarations in new code unless required by an
  existing codebase.
- Every mapped entity must have an explicit primary key.
- Keep Python type annotations consistent with database nullability:
  - `Mapped[str]` normally means NOT NULL.
  - `Mapped[str | None]` normally means nullable.
  - Use `nullable=` explicitly when Python optionality and database nullability
    intentionally differ.

## Relationships

- Define bidirectional relationships explicitly with `back_populates`.
- Do not introduce `relationship(backref=...)` in new code.
- Configure relationship cardinality from the actual domain model rather than
  for convenience.
- A pure many-to-many association table should normally have a primary key or
  unique constraint across the two foreign keys so duplicate associations
  cannot be inserted.
- If an association contains additional business fields, map it as an
  association object rather than treating it as a plain `secondary` table.
- Use `delete-orphan` only when the related object is truly owned by exactly one
  parent.
- Keep ORM cascade behavior and database `ON DELETE` behavior consistent.
- When relying on database-side `ON DELETE CASCADE`, consider
  `passive_deletes=True` so the ORM does not unnecessarily load child
  collections before deletion.

## Constraints and indexes

Encode invariants in the database where possible:

- `ForeignKey` / `ForeignKeyConstraint`
- `UniqueConstraint`
- `CheckConstraint`
- `Index`

- Prefer explicit `Index(...)` for composite, partial, expression, named,
  covering, or database-specific indexes.
- Prefer explicit `UniqueConstraint(...)` for composite or named uniqueness
  constraints.
- Use a consistent `MetaData.naming_convention` when the project uses
  migrations.
- Do not create indexes automatically for every foreign key or frequently
  mentioned column. Indexes should correspond to actual lookup, join,
  filtering, ordering, or uniqueness requirements.

## Defaults and generated values

Distinguish clearly between:

- Python-side defaults: `default=`
- Python-side update defaults: `onupdate=`
- Database-side defaults: `server_default=`
- Database-generated values such as identity, sequences, triggers, and
  computed columns

If the database is responsible for generating a value, model it as a
server-generated value instead of reproducing the behavior only in Python.
Do not assume that Python-side `default` or `onupdate` hooks execute during
dialect-specific UPSERT operations.

## Types

- Prefer SQLAlchemy's portable types when portability matters.
- Use `Uuid` for portable UUID storage.
- Use dialect-specific types such as PostgreSQL `JSONB`, `ARRAY`, ranges,
  network types, etc. only when the application is intentionally tied to that
  database or gains a concrete benefit from them.
- Choose string lengths, numeric precision, timezone behavior, enum
  representation, and JSON semantics deliberately rather than relying on
  accidental defaults.

## Model responsibilities

ORM models should describe persistence structure and domain relationships.

- Avoid hiding database I/O behind ordinary Python properties or methods where
  the caller cannot see that a query will occur.
- Do not add a relationship merely because it makes one query convenient.
  Relationships should represent stable domain associations.

## Async ORM

When using `AsyncSession`:

- Do not depend on implicit lazy-loading I/O.
- Load relationships explicitly with an appropriate loader strategy.
- Consider `lazy="raise"` for relationships where accidental lazy loading
  should fail immediately.
- `AsyncAttrs` may be used when explicit awaitable attribute loading is
  intentionally part of the project's design.
- Prefer `expire_on_commit=False` for typical async application sessions
  where objects must remain usable after commit.
- Avoid cascade `"all"` as a blind default; list required cascade behavior
  explicitly.

## Review checklist

Before accepting a new or changed ORM model, verify:

1. Primary keys and foreign keys express the real schema.
2. Python optionality matches database nullability.
3. Uniqueness and other invariants are enforced at the database layer where
   appropriate.
4. Bidirectional relationships use `back_populates`.
5. Cascade and `ON DELETE` semantics agree.
6. Many-to-many tables cannot accidentally contain duplicate links.
7. Indexes correspond to expected query patterns.
8. Server-generated values are modeled as server-generated.
9. Database-specific types/features are intentional.
10. The model does not introduce hidden database I/O.
