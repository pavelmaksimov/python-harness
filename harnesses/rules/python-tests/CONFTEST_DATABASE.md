# Database conftest fixtures

Merge into `tests/conftest.py` when `python-db-sessions` is installed (do not overwrite without asking).
Requires `python-db-sessions` (`DATABASE.md` in the adapter) and `python-sqlalchemy` for ORM
metadata. For ORM rows in tests, add `python-polyfactory` with the ORM block in
`tests/factories.py`.

Add these imports to the existing conftest imports:

```python
import pytest_asyncio
from sqlalchemy import create_engine
from testcontainers.postgres import PostgresContainer

from project.base.models import Base
from project.infrastructure.adapters import database
```

Append after the HTTP mock section:

```python
# --- Database (Testcontainers) -----------------------------------------------


@pytest.fixture(scope="session")
def init_database(setup):
    with PostgresContainer("postgres:17.2") as postgres:
        async_dsn = postgres.get_connection_url(driver="asyncpg")
        sync_dsn = async_dsn.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        with Settings.local(SQLALCHEMY_DATABASE_DSN=async_dsn, DB_SCHEMA=None):
            sync_engine = create_engine(sync_dsn)
            try:
                Base.metadata.create_all(bind=sync_engine, checkfirst=True)
            finally:
                sync_engine.dispose()
            yield
            database.aengine_factory.cache_clear()
            database.async_sessionmaker_factory.cache_clear()


@pytest_asyncio.fixture
async def asession(init_database):
    database.aengine_factory.cache_clear()
    database.async_sessionmaker_factory.cache_clear()
    async with database.asession() as session:
        async with session.begin() as transaction:
            async with session.begin_nested():
                yield session
            await transaction.rollback()
```

## Usage

```python
from tests.factories import UserFactory

async def test_repo(asession):
    # asession is already in a nested transaction; data rolls back after the test
    user = await UserFactory.create_async(email="a@example.com")
    ...
```

After a DSN change, call `cache_clear()` on the engine and sessionmaker factories.
