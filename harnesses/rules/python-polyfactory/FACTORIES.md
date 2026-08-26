# Test factories (Polyfactory)

Copy into `tests/factories.py` (merge with existing factories; do not overwrite without asking).
Call the class directly in the test.
Do not `@register_fixture` factories.

## Schemas (Pydantic)

```python
from polyfactory.factories.pydantic_factory import ModelFactory

from project.components.items.schemas import ItemSchema


class ItemSchemaFactory(ModelFactory[ItemSchema]): ...
```

`ItemSchemaFactory.build(title="x")` — in-memory payload, no database.

Field defaults (`Use`, `Require`, `PostGenerated`): sibling `FIELDS.md`.
Domain `NewType` providers: sibling `CUSTOM_TYPES.md`.
`Literal` / union exhaustiveness: sibling `COVERAGE.md`.
