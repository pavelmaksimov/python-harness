# Generic SQLAlchemy repository

Copy this module to `project/components/base/repositories.py` when multiple domain repositories
share the same model lookup behavior. Skip it when a generic base would have only one consumer.
Requires `python-db-sessions` for `asession` / `atransaction`.

Before copying, ensure `NotFoundError` exists in `project/exceptions.py`. If it is missing, create
the shared `NotFoundError(AppError)` defined by `python-exceptions`; its constructor takes
`object_name` and `id`. Do not define it in `repositories.py`.

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, ClassVar

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from project.components.base.models import Base
from project.exceptions import NotFoundError
from project.infrastructure.adapters.database import asession, atransaction, current_atransaction


class ORMRepository[T: Base]:
    _model: ClassVar[type[T]]

    get_session = staticmethod(asession)
    get_transaction = staticmethod(atransaction)
    get_current_transaction = staticmethod(current_atransaction)

    @classmethod
    async def get_or_none(cls, pk: object) -> T | None:
        async with cls.get_session() as session:
            return await session.get(cls._model, pk)

    @classmethod
    def new(cls, **kwargs: Any) -> T:
        return cls._model(**kwargs)

    @classmethod
    async def create(cls, **kwargs: Any) -> T:
        instance = cls.new(**kwargs)
        await cls.save(instance)
        return instance

    @classmethod
    async def save(cls, instance: T) -> None:
        async with cls.get_transaction() as session:
            session.add(instance)

    @classmethod
    async def get(cls, pk: object) -> T:
        item = await cls.get_or_none(pk)
        if item is None:
            raise NotFoundError(cls._model.__name__, pk)
        return item

    @classmethod
    async def all(cls) -> list[T]:
        async with cls.get_session() as session:
            return list((await session.scalars(select(cls._model))).all())

    @classmethod
    def update_fields(cls, instance: T, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(instance, key, value)

    @classmethod
    async def update_fields_and_save(cls, instance: T, **kwargs: Any) -> None:
        async with cls.get_current_transaction() as session:
            cls.update_fields(instance, **kwargs)
            session.add(instance)

    @classmethod
    async def delete_by_id(cls, pk: object) -> None:
        async with cls.get_current_transaction() as session:
            await session.execute(delete(cls._model).where(cls._model.id == pk))
```

Add shared methods only after at least two repositories need the same operation. Domain-specific
queries stay in the domain repository.
