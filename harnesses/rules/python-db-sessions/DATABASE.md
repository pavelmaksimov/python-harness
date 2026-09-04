# Database session adapter

Copy this module to `project/infrastructure/adapters/database.py` when the package does not
already define `asession` / `atransaction`. Repositories import these helpers; entities and use
cases do not open sessions.

`Settings` must expose `SQLALCHEMY_DATABASE_DSN`, `DB_SCHEMA`, and the SQLAlchemy pool settings
(see below).

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


@lru_cache  # process-wide pool; cache_clear() after a DSN override
def aengine_factory() -> AsyncEngine:
    dsn = Settings().SQLALCHEMY_DATABASE_DSN
    if not dsn:
        msg = "Database is not configured: set SQLALCHEMY_DATABASE_DSN or DB_* variables"
        raise RuntimeError(msg)

    connect_args: dict = {}
    schema = Settings().DB_SCHEMA
    if schema:
        connect_args["server_settings"] = {"search_path": schema}

    return create_async_engine(
        str(dsn),
        pool_pre_ping=Settings().SQLALCHEMY_DATABASE_PRE_PING,
        pool_size=Settings().SQLALCHEMY_POOL_SIZE,
        max_overflow=Settings().SQLALCHEMY_MAX_OVERFLOW,
        connect_args=connect_args,
    )


@lru_cache  # stays bound to the cached engine; not a session cache
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

Add these fields and methods to `SettingsValidator` if missing (`python-architecture/python-settings.mdc`).
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
    SQLALCHEMY_DATABASE_PRE_PING: bool = False
    SQLALCHEMY_POOL_SIZE: int = 5
    SQLALCHEMY_MAX_OVERFLOW: int = 10

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
        return bool(self.SQLALCHEMY_DATABASE_DSN)
```

`ContextVar` reuse is sequential within one asyncio task. Do not spawn concurrent database work
inside an active `asession()` / `atransaction()` context; each concurrent task needs its own
session lifecycle.

## Test fixtures

Copy `init_database` and `asession` from the `python-tests` rule (`CONFTEST_DATABASE.md`) into
`tests/conftest.py`.
After a DSN override, `cache_clear()` the factories. Nested transaction + rollback isolates rows.
Persist test rows with `create_async` (`python-polyfactory`) while this `asession` fixture is active.
