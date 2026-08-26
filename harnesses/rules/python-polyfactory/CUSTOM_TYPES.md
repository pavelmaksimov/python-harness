# Custom types in factories

Read when `build` fails on a domain `NewType`, a custom value object,
or another type Polyfactory does not know — or when several factories need the same
provider. Prefer one provider on the shared base factory in `tests/factories.py`.

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

For a shared Pydantic `ModelFactory` base, override `get_provider_map` with the same
merge order: local providers first, then `**super().get_provider_map()`.

If a custom base adds new `__…__` config attributes, extend `__config_keys__` so
concrete factories inherit them.
