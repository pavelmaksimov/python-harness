# Shared SQLAlchemy Base

Copy this module to `project/components/base/models.py` when the package does not already define
`Base` / `public_schema`. Domain models inherit `Base` and mix in `TimeMixin` (`python-sqlalchemy`).
Alembic uses `public_schema` or `Base.metadata` (`python-alembic`).

```python
import datetime as dt

from sqlalchemy import MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

public_schema = MetaData()


class Base(DeclarativeBase):
    metadata = public_schema


class TimeMixin:
    created_at: Mapped[dt.datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
```
