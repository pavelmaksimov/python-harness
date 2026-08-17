# Alembic env.py

Copy this module to `alembic/env.py` when introducing Alembic (after `uv run alembic init -t async alembic`)
or when the existing `env.py` still uses sync `engine_from_config`. Requires `python-sqlalchemy` and
`python-settings` (`Settings().get_database_dsn()`). Leave `sqlalchemy.url` unset in `alembic.ini`.

If `project.components.base.models` is missing, import the repo's existing `Base` and use `Base.metadata`.

```python
import asyncio
import importlib
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from project.components.base import models as base_models
from project.settings import Settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _database_url() -> str:
    dsn = Settings().get_database_dsn()
    if not dsn:
        msg = "Database is not configured: set SQLALCHEMY_DATABASE_DSN or DB_* variables"
        raise RuntimeError(msg)
    return str(dsn)


def _connect_args() -> dict:
    schema = Settings().DB_SCHEMA
    if schema:
        return {"server_settings": {"search_path": schema}}
    return {}


def _import_component_models() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    components = repo_root / "project" / "components"
    if not components.is_dir():
        return
    for models_file in sorted(components.rglob("models.py")):
        module_name = ".".join(models_file.relative_to(repo_root).with_suffix("").parts)
        importlib.import_module(module_name)


_import_component_models()
target_metadata = getattr(base_models, "public_schema", base_models.Base.metadata)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(
        _database_url(),
        poolclass=pool.NullPool,
        connect_args=_connect_args(),
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```
