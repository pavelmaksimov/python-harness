# Model coverage

Read when a test must hit every `Literal` / union variant with as few instances as
possible. Prefer ordinary `build` / `batch` for normal scenarios.

`Factory.coverage()` yields instances that walk the model's shape variants. The longest
variant set decides how many examples you get.

```python
from tests.factories import ProfileSchemaFactory


def test_profile_variants():
    profiles = list(ProfileSchemaFactory.coverage())
    colors = {p.favourite_color for p in profiles}
    assert colors == {"red", "green", "blue"}
```

Notes:

- Exhausted fields reuse earlier values while another field still has variants.
- Nested collections embed the sub-model's coverage examples (often length 1 per group).
- Recursive models raise `RecursionError`.
- `__min_collection_length__` / `__max_collection_length__` are ignored for coverage.
