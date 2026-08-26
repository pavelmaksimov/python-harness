# ORM test factories (Polyfactory)

Merge into `tests/factories.py` only when `python-sqlalchemy` and `python-db-sessions`
are installed. Persist through `atransaction()` so the test's `asession` transaction owns
the data. Flush only; the fixture rolls back.

Every ORM model gets a factory class. Call factories directly in tests:

| Need | Call |
|---|---|
| ORM instance in memory | `UserFactory.build(**overrides)` |
| ORM row in DB | `await UserFactory.create_async(**overrides)` |
| Several instances | `UserFactory.batch(n, **overrides)` |
| Several rows in DB | `await UserFactory.create_batch_async(n, **overrides)` |

```python
from typing import Any

from polyfactory.factories.sqlalchemy_factory import SQLAlchemyFactory, T

from project.components.users.models import User
from project.infrastructure.adapters.database import atransaction


class AtransactionPersistence:
    """Add and flush through the active test transaction."""

    async def save(self, data: Any) -> Any:
        async with atransaction() as session:
            session.add(data)
            await session.flush()
            await session.refresh(data)
        return data

    async def save_many(self, data: list[Any]) -> list[Any]:
        async with atransaction() as session:
            session.add_all(data)
            await session.flush()
            for item in data:
                await session.refresh(item)
        return data


class BaseSQLAlchemyFactory(SQLAlchemyFactory[T]):
    __is_base_factory__ = True
    __async_persistence__ = AtransactionPersistence
    __set_primary_key__ = False
    __set_relationships__ = False
    __set_association_proxy__ = False


class UserFactory(BaseSQLAlchemyFactory[User]): ...
```

Use the `asession` fixture in every test that calls `create_async` or
`create_batch_async`; `build()` and `batch()` stay in memory. Keep persistence async and
flush-only. Pass real FK ids and keep relationship generation disabled.

```python
from tests.factories import UserFactory


async def test_user_persisted(asession):
    user = await UserFactory.create_async(email="a@example.com")
    assert user.id is not None
```

## Foreign keys and async values

This stack stores FK ids or id arrays rather than `relationship()` graphs. Create related
rows first and pass their ids:

```python
async def test_order(asession):
    user = await UserFactory.create_async()
    order = await OrderFactory.create_async(user_id=user.id)
```

Resolve async lookups outside the factory. Do not open a session inside a field callable.

## Custom domain types

Put shared ORM providers on `BaseSQLAlchemyFactory`:

```python
from typing import Any

from project.datatypes import UserIdT


class BaseSQLAlchemyFactory(SQLAlchemyFactory[T]):
    # Base configuration and persistence from the template above.

    @classmethod
    def get_provider_map(cls) -> dict[Any, Any]:
        providers_map = super().get_provider_map()
        return {
            UserIdT: lambda: UserIdT(cls.__random__.randint(1, 10_000)),
            **providers_map,
        }
```

## Coverage

Build coverage in memory, then persist only the cases the test needs with `create_async`
while the `asession` fixture is active.
