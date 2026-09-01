---
name: sqlalchemy
description: SQLAlchemy 2.x best practices — modern Declarative ORM models, the 2.0 statement query API, loader strategies, session/transaction semantics, and dialect-specific rules for PostgreSQL, MySQL/MariaDB, SQLite, SQL Server, and Oracle. Use when writing or reviewing SQLAlchemy models, relationships, queries, sessions, transactions, or database-specific SQL.
---

# sqlalchemy

Low-level SQLAlchemy 2.x rules only. This skill does not decide project
architecture — repository pattern, unit-of-work wrappers, Pydantic, FastAPI,
sync vs async defaults are the target project's choices. Follow the project's
existing structure; apply only the SQLAlchemy mechanics below.

## Routing

1. Confirm the project targets SQLAlchemy 2.x stable APIs. In a legacy 1.4
   codebase, preserve its style unless migration is explicitly in scope.
2. Detect the operation and read the matching reference file (both may apply):
   - Define or change ORM models, relationships, constraints, indexes,
     defaults, or types → `references/orm-models.md`.
   - Write or review queries, repositories, sessions, or transactions →
     `references/queries.md`.
3. Detect the actual database dialect from the engine URL, settings, or
   Alembic configuration, then apply only that dialect's section in
   `references/databases.md`. Do not apply other dialects' rules.

## Invariants

- Generate SQLAlchemy 2.x APIs, never legacy `Query` / `declarative_base()` /
  `relationship(backref=...)` in new code.
- Parameterize all runtime values; never interpolate values into SQL strings.
- Never ignore the relationship loading strategy; avoid N+1 by design.
- One session per unit of work; never share a session across concurrent
  threads or asyncio tasks.
