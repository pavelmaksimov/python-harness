# Task

Orders live in Postgres. What exists today is a hand-written table definition plus a
repository that opens its own engine and sessionmaker on every call, and an `Order`
entity that takes a database session as an argument.

Bring persistence in line with the project's conventions:

- the persistence type is an ORM model in `project/components/orders/models.py` with
  typed mapped columns, inheriting the shared declarative base and its timestamp mixin;
- the order payload column is JSON-capable (`JSONB` on Postgres), the status is a real
  enum column, and the foreign key to users carries a delete rule;
- identity columns use the project's domain types, and lookup/sort columns are indexed;
- the persistence type is named so that the domain name stays with the entity;
- the repository is the only place that knows about the ORM: it opens sessions through the
  shared adapter helpers, wraps writes in the project's transaction helper, and maps rows
  to and from the entity. Nothing outside the repository may see ORM objects, and the
  entity must not know that persistence exists;
- the schema is managed by migrations: the repository has ORM models but no migrations
  are wired up yet, and the migration environment must read the DSN from the project
  settings rather than a hardcoded URL.

`uv run python -c "import project"` must work.
