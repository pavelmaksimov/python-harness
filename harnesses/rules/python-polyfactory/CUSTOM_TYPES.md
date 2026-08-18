# Custom types in factories

Read when `build` / `create_async` fails on a domain `NewType`, a custom value object,
or another type Polyfactory does not know — or when several factories need the same
provider. Prefer one provider on the shared base factory in `tests/factories.py`.

## Provider on the base factory

```python
from typing import Any

from project.datatypes import UserIdT


class BaseSQLAlchemyFactory(SQLAlchemyFactory[T]):
    __is_base_factory__ = True
    __async_persistence__ = AtransactionPersistence
    __set_primary_key__ = False
    __set_relationships__ = False
    __set_association_proxy__ = False

    @classmethod
    def get_provider_map(cls) -> dict[Any, Any]:
        providers_map = super().get_provider_map()
        return {
            UserIdT: lambda: UserIdT(cls.__random__.randint(1, 10_000)),
            **providers_map,
        }
```

Same pattern on a Pydantic `ModelFactory` base if schemas share domain types.

## One-off on a single factory

```python
class PersonFactory(ModelFactory[PersonSchema]):
    @classmethod
    def get_provider_map(cls) -> dict[Any, Any]:
        providers_map = super().get_provider_map()
        return {
            CustomSecret: lambda: CustomSecret("test-secret"),
            **providers_map,
        }
```

## Process-wide provider

```python
from polyfactory.factories.base import BaseFactory

BaseFactory.add_provider(CustomSecret, lambda: CustomSecret("test-secret"))
```

Use only when every factory in the process should see the type. Prefer the base-factory
`get_provider_map` in `tests/factories.py` so test data stays local to tests.

If a custom base adds new `__…__` config attributes, extend `__config_keys__` so
concrete factories inherit them.
