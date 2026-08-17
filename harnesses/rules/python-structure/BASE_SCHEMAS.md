# Shared FastAPI envelope

Copy this module to `project/components/base/schemas.py` when the package does not already define
`ApiResponseSchema`. Use it as `response_model` (`python-fastapi`). Domain payload types stay in
`project/components/{name}/schemas.py`.

```python
from pydantic import BaseModel


class ApiResponseSchema[T](BaseModel):
    data: T
```
