# Database session adapter

Copy this module to `project/infrastructure/adapters/database.py` when the package does not
already define `asession` / `atransaction`. Repositories import these helpers; services and use
cases do not open sessions.

`Settings` must expose `get_database_dsn()`, `DB_SCHEMA`, and `DATABASE_PRE_PING` (see below).

```python
import contextvars
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from project.settings import Settings

asession_storage: contextvars.ContextVar[AsyncSession | None] = contextvars.ContextVar(
    "current_session",
    default=None,
)


def database_dsn() -> str:
    dsn = Settings().get_database_dsn()
    if not dsn:
        msg = "Database is not configured: set SQLALCHEMY_DATABASE_DSN or DB_* variables"
        raise RuntimeError(msg)
    return str(dsn)


def _engine_connect_args() -> dict:
    connect_args: dict = {}
    schema = Settings().DB_SCHEMA
    if schema:
        connect_args["server_settings"] = {"search_path": schema}
    return connect_args


@lru_cache
def aengine_factory() -> AsyncEngine:
    return create_async_engine(
        database_dsn(),
        pool_pre_ping=Settings().DATABASE_PRE_PING,
        connect_args=_engine_connect_args(),
    )


@lru_cache
def async_sessionmaker_factory():
    return async_sessionmaker(aengine_factory(), autoflush=False, expire_on_commit=False)


async def create_all_tables(metadata) -> None:
    """Create ORM tables; used in tests and e2e setup."""
    engine = aengine_factory()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all, checkfirst=True)


@asynccontextmanager
async def asession():
    """Reuse the current ContextVar session, otherwise open one and clean it up on exit."""
    current_session = asession_storage.get()

    if current_session:
        yield current_session
    else:
        async_session = async_sessionmaker_factory()
        async with async_session() as session:
            token = asession_storage.set(session)
            try:
                yield session
            finally:
                asession_storage.reset(token)


@asynccontextmanager
async def atransaction():
    """Begin a transaction, or a savepoint when already inside one."""
    current_session = asession_storage.get()

    if current_session:
        if current_session.in_transaction():
            async with current_session.begin_nested():
                yield current_session
        else:
            async with current_session.begin():
                yield current_session
    else:
        async with asession() as session, session.begin():
            yield session


@asynccontextmanager
async def current_atransaction():
    """Join the open transaction, or begin one if none is active."""
    current_session = asession_storage.get()

    if current_session:
        if current_session.in_transaction():
            yield current_session
        else:
            async with current_session.begin():
                yield current_session
    else:
        async with asession() as session, session.begin():
            yield session
```

## Settings contract

Add these fields and methods to `SettingsValidator` if missing (`python-settings`).
`SQLALCHEMY_DATABASE_DSN` wins; otherwise assemble from `DB_*`.

```python
from urllib.parse import quote_plus

from pydantic import PostgresDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings

class SettingsValidator(BaseSettings):
    DB_HOST: str | None = None
    DB_PORT: int = 5432
    DB_NAME: str | None = None
    DB_SCHEMA: str | None = None
    DB_USER: str | None = None
    DB_PASSWORD: SecretStr | None = None
    SQLALCHEMY_DATABASE_DSN: PostgresDsn | None = None
    DATABASE_PRE_PING: bool = False
    E2E_TEST_POSTGRES_DSN: str | None = None

    @model_validator(mode="after")
    def build_sqlalchemy_database_dsn(self) -> "SettingsValidator":
        if self.SQLALCHEMY_DATABASE_DSN:
            return self
        if self.DB_HOST and self.DB_NAME and self.DB_USER and self.DB_PASSWORD:
            password = quote_plus(self.DB_PASSWORD.get_secret_value())
            object.__setattr__(
                self,
                "SQLALCHEMY_DATABASE_DSN",
                f"postgresql+asyncpg://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}",
            )
        return self

    def database_is_configured(self) -> bool:
        return bool(self.SQLALCHEMY_DATABASE_DSN or self.E2E_TEST_POSTGRES_DSN)

    def get_database_dsn(self) -> PostgresDsn | str | None:
        if self.SQLALCHEMY_DATABASE_DSN:
            return self.SQLALCHEMY_DATABASE_DSN
        return self.E2E_TEST_POSTGRES_DSN
```

## Repository usage

```python
from project.infrastructure.adapters.database import asession, atransaction

async def save(instance) -> None:
    async with atransaction() as session:
        session.add(instance)

async def get(pk):
    async with asession() as session:
        return await session.get(Model, pk)
```

## Test fixtures

Copy `init_database` and `asession` from the `python-tests` rule (`CONFTEST.md`) into `tests/conftest.py`.
After a DSN override, `cache_clear()` the factories. Nested transaction + rollback isolates rows.
