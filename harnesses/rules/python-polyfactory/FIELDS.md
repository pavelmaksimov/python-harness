# Factory fields

Read when customizing how a factory fills attributes — defaults, `Use` / `Ignore` /
`Require`, values derived from other fields, nested factories, or an FK taken from a
row already created in the test. Call the factory class in the test (`UserFactory.build`);
do not register factory fixtures.

Hardcoded class attributes become fixed defaults. Prefer a callable, `Use`, or a
classmethod so each build can still vary.

## Use / callable / classmethod

```python
from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory

from project.components.items.schemas import ItemSchema


class ItemSchemaFactory(ModelFactory[ItemSchema]):
    title = Use(ModelFactory.__random__.choice, ["alpha", "beta"])

    @classmethod
    def slug(cls) -> str:
        return cls.__faker__.slug()
```

Use `cls.__random__` / `cls.__faker__`, not the global `random` module, so
`__random_seed__` stays consistent.

Nested list of related objects:

```python
pets = Use(PetFactory.batch, size=2)
```

## Ignore / Require

```python
from polyfactory import Ignore, Require

class UserFactory(BaseSQLAlchemyFactory[User]):
    password_hash = Ignore()          # leave unset / None
    email = Require()                  # build(email=...) required
```

## PostGenerated / `@post_generated`

Only when one field must follow another already generated field (ranges, derived slugs).
Prefer `@post_generated` when the logic needs `cls.__faker__` / `cls.__random__`.

```python
from datetime import datetime, timedelta

from polyfactory.decorators import post_generated


class WindowFactory(ModelFactory[WindowSchema]):
    @post_generated
    @classmethod
    def ends_at(cls, starts_at: datetime) -> datetime:
        return starts_at + cls.__faker__.time_delta("+3d")
```

Parameters after `cls` must match other field names. Plain `PostGenerated(fn)` receives
`(name, values, *args, **kwargs)` where `values` is the map of already generated fields.

## Nested factory as a field

```python
class OrderFactory(ModelFactory[OrderSchema]):
    item = ItemSchemaFactory  # build(item={"title": "x"}) overrides the nested build
```

This stack stores FK ids / id arrays, not `relationship()` graphs. Prefer passing ids:

```python
async def test_order(asession):
    user = await UserFactory.create_async()
    order = await OrderFactory.create_async(user_id=user.id)
```

Resolve async lookups **outside** the factory, then pass the value into `build` /
`create_async`. Do not open a session inside a field callable.
