# Test factories (Polyfactory)

Copy into `tests/factories.py` (merge with existing factories; do not overwrite without asking).
Call the class in the test: `UserFactory.build(...)` / `await UserFactory.create_async(...)`.
Do not `@register_fixture` factories.

## Schemas (Pydantic)

```python
from polyfactory.factories.pydantic_factory import ModelFactory

from project.components.items.schemas import ItemSchema


class ItemSchemaFactory(ModelFactory[ItemSchema]): ...
```

`ItemSchemaFactory.build(title="x")` — in-memory payload, no database.

## ORM (when `python-sqlalchemy` and `python-db-sessions` are installed)

Persist through `atransaction()` so the session is the same one `asession()` /
the `asession` fixture already opened. Flush only: the test fixture rolls back.

```python
from typing import Any

from polyfactory.factories.sqlalchemy_factory import SQLAlchemyFactory, T

from project.components.users.models import User
from project.infrastructure.adapters.database import atransaction


class AtransactionPersistence:
    """Add + flush via atransaction(); refresh so DB defaults and PKs are loaded."""

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
    # Domain NewTypes: extend get_provider_map — see sibling CUSTOM_TYPES.md


class UserFactory(BaseSQLAlchemyFactory[User]): ...
```

```python
from tests.factories import ItemSchemaFactory, UserFactory


def test_user():
    user = UserFactory.build(email="b@example.com")
    payload = ItemSchemaFactory.build(title="x")


async def test_user_persisted(asession):
    user = await UserFactory.create_async(email="a@example.com")
```

Field defaults (`Use`, `Require`, `PostGenerated`): sibling `FIELDS.md`.
Domain `NewType` providers: sibling `CUSTOM_TYPES.md`.
`Literal` / union exhaustiveness: sibling `COVERAGE.md`.
