# Test factories (Polyfactory)

Copy into `tests/factories.py` (merge with existing factories; do not overwrite without asking).
Call the class directly in the test.
Do not `@register_fixture` factories.

## Pydantic models

```python
from polyfactory.factories.pydantic_factory import ModelFactory

from project.components.items.schemas import ItemSchema


class ItemSchemaFactory(ModelFactory[ItemSchema]): ...
```

`ItemSchemaFactory.build(title="x")` — in-memory payload, no database.

## Dataclasses

```python
from dataclasses import dataclass

from polyfactory.factories import DataclassFactory


@dataclass
class Item:
    title: str


class ItemFactory(DataclassFactory[Item]): ...
```

`ItemFactory.build(title="x")` returns an `Item` instance.

## TypedDicts

```python
from typing import TypedDict

from polyfactory.factories import TypedDictFactory


class ItemPayload(TypedDict):
    title: str


class ItemPayloadFactory(TypedDictFactory[ItemPayload]): ...
```

`ItemPayloadFactory.build(title="x")` returns an `ItemPayload` dictionary.

Field defaults (`Use`, `Require`, `PostGenerated`): sibling `FIELDS.md`.
Domain `NewType` providers: sibling `CUSTOM_TYPES.md`.
`Literal` / union exhaustiveness: sibling `COVERAGE.md`.
