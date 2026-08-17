# Settings module

Copy this module to `project/settings.py` when the package does not already define
`Settings` / `SettingsValidator`. Requires `LazyInit` from `project/libs/structures.py`
(`python-di` → `STRUCTURES.md`). Keep `env.example` in sync with required fields.
Logging: `LOG_LEVEL`, optional `WRITE_LOGS_TO_FILE`, and `Constants.LOG_FORMAT` (`python-logging`).
Add per-library `*_LOG_LEVEL` fields only for libraries the repo uses.

```python
from enum import Enum
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from project.libs.structures import LazyInit


class Envs(Enum):
    PROD = "PROD"
    STAGE = "STAGE"
    AUTOTEST = "AUTOTEST"
    LOCAL = "LOCAL"


class Constants:
    LOG_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


class SettingsValidator(BaseSettings):
    ENV: Envs = Envs.LOCAL
    LOG_LEVEL: str = "INFO"
    WRITE_LOGS_TO_FILE: bool = False

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        extra="allow",
    )

    def is_local(self) -> bool:
        return self.ENV == Envs.LOCAL

    def is_autotest(self) -> bool:
        return self.ENV == Envs.AUTOTEST


Settings = LazyInit(SettingsValidator)
```
