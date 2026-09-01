# SQLAlchemy database-specific rules

Apply this file only for the database actually used by the project.
Do not introduce database-specific constructs merely because SQLAlchemy
supports them.

## PostgreSQL

### UPSERT

Use `sqlalchemy.dialects.postgresql.insert()` with:

- `on_conflict_do_update()`
- `on_conflict_do_nothing()`
- `Insert.excluded`

Specify the intended conflict target explicitly.
Python-side `Column.onupdate` values are not automatically applied by
`ON CONFLICT DO UPDATE`; include required update values explicitly.

### PostgreSQL types

PostgreSQL-specific types such as:

- `JSONB`
- `ARRAY`
- ranges / multiranges
- `INET` / `CIDR`
- PostgreSQL `ENUM`
- `HSTORE`

are appropriate when PostgreSQL is an intentional dependency.
Use portable SQLAlchemy `Uuid` instead of PostgreSQL-specific `UUID` when
cross-database compatibility is required.

### JSONB mutation tracking

SQLAlchemy does not automatically detect arbitrary in-place changes inside
JSON/JSONB values.
If code mutates JSON structures in place and expects ORM dirty tracking, use
the appropriate mutable extension or replace the full value explicitly.

### PostgreSQL indexes

Use PostgreSQL-specific index options only when required, including:

- partial indexes
- expression indexes
- covering indexes
- operator classes
- GIN/GiST/etc.
- storage parameters

`CREATE INDEX CONCURRENTLY` / `DROP INDEX CONCURRENTLY` must be executed outside
a normal transaction block using the appropriate autocommit behavior.
When upgrading older SQLAlchemy applications, verify expression indexes
involving JSONB against SQLAlchemy's current SQL rendering before assuming an
existing PostgreSQL expression index will still match generated queries.

### Schemas and search_path

Do not rely on an ambient or user-dependent PostgreSQL `search_path` for
application correctness.
Prefer explicit schema ownership and predictable search-path configuration,
especially when using reflection.

## MySQL / MariaDB

### Storage engine

Use a transactional storage engine such as InnoDB for tables that require
transactions and foreign keys.
Do not assume foreign-key semantics on non-transactional engines.

### Character encoding

Use `utf8mb4` for Unicode applications.
Do not choose legacy MySQL `utf8`/`utf8mb3` when full Unicode support is
required.

### Auto increment

Understand MySQL/MariaDB `AUTO_INCREMENT` semantics when designing primary
keys.
Do not assume sequence behavior identical to PostgreSQL or Oracle.

### UPSERT

Use the MySQL/MariaDB dialect-specific insert API with
`ON DUPLICATE KEY UPDATE`.
Do not implement MySQL UPSERT by writing PostgreSQL `ON CONFLICT` syntax or by
first performing a SELECT followed by INSERT/UPDATE when atomic database UPSERT
semantics are required.

### RETURNING

Do not assume MySQL and MariaDB have identical RETURNING support.
Check the exact server and driver capabilities before writing code that depends
on INSERT/UPDATE/DELETE RETURNING.

### Binary data

When storing binary values through drivers affected by MySQL character-set
handling, investigate driver `binary_prefix` support rather than converting
binary data into interpolated SQL literals.

## SQLite

### Foreign keys

SQLite foreign-key enforcement is not enabled automatically in typical
configurations.
If the application relies on foreign keys, enable:

```sql
PRAGMA foreign_keys = ON
```

for every database connection before using the schema.
Tests must run with the same foreign-key setting; otherwise they can silently
accept invalid data that production rejects.

### Integer primary keys

SQLite has special autoincrement behavior.
If SQLite ROWID/autoincrement semantics are required, the primary-key type must
compile to exactly `INTEGER`.
Do not enable explicit SQLite `AUTOINCREMENT` unless the application
specifically requires its stronger "never reuse a ROWID" behavior.

### UPSERT

Use `sqlalchemy.dialects.sqlite.insert()` with SQLite's `ON CONFLICT` APIs.
Python-side `Column.onupdate` values are not automatically invoked by
`ON CONFLICT DO UPDATE`; provide required update values explicitly.

### Transactions

SQLite transaction behavior depends on Python `sqlite3`/driver configuration.
Do not assume transactional DDL, SAVEPOINT behavior, or BEGIN semantics are
identical to PostgreSQL.
Configure transaction control deliberately and test the same configuration
used by the application.

### Foreign-key migrations

SQLite cannot perform every ALTER operation required for mutually dependent
foreign-key constraints.
Account for SQLite migration limitations instead of assuming
PostgreSQL-style `ALTER TABLE` capabilities.

## Microsoft SQL Server

### Pagination

SQL Server requires an `ORDER BY` for OFFSET-style pagination.
Every query using offset/limit pagination must therefore have deterministic
ordering.
Do not generate unordered pagination.

### Identity

Use SQL Server `IDENTITY` semantics for auto-generated integer keys where
appropriate.
Do not assume PostgreSQL sequence/SERIAL behavior.

### Composite primary keys and selectinload

SQL Server does not support the tuple-IN syntax required by SQLAlchemy
`selectinload()` for relationships whose target uses a composite primary key.
For that case, select another loading strategy such as `joinedload()` or
`subqueryload()` according to the query shape.

### Bulk inserts

With pyodbc, `fast_executemany=True` may substantially improve multi-row insert
performance where the statement does not depend on RETURNING/OUTPUT behavior.
Treat this as a measured performance optimization, not a universal default.

### Generated values and triggers

SQL Server trigger-generated values can interact with OUTPUT/RETURNING behavior.
If a table's trigger behavior is incompatible with implicit RETURNING, configure
that table appropriately instead of adding extra ad-hoc SELECTs throughout
application code.

## Oracle

### Generated primary keys

For modern Oracle versions, prefer Oracle `IDENTITY` where it fits the schema.
Use explicit `Sequence` when required by the target Oracle version or by the
application's sequence semantics.
Do not assume PostgreSQL `SERIAL` or MySQL `AUTO_INCREMENT` behavior.

### Version-sensitive SQL

Oracle SQL capabilities and generated SQL behavior can differ significantly
across supported server versions.
Before using pagination, identity features, RETURNING, or other
version-sensitive features, verify the minimum Oracle version supported by the
application.

### Identifiers

Keep identifier naming predictable.
Avoid unnecessary quoted mixed-case identifiers, and account for Oracle
identifier-length and casing rules when generating constraint and index names.

## Cross-database rule

Before introducing any of the following, identify the active database dialect:

- UPSERT
- database-specific JSON operators
- arrays
- ranges
- full-text search
- generated/identity columns
- partial indexes
- expression indexes
- concurrent index creation
- RETURNING-dependent logic
- dialect-specific locking
- dialect-specific types

Do not make a query appear portable when its semantics actually depend on one
database.
When portability is a project requirement, prefer SQLAlchemy's generic APIs and
types and isolate unavoidable dialect-specific behavior behind small, explicit
boundaries.
