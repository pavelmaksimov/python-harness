# Settings module

Copy this module to `project/settings.py` when the package does not already define
`Settings` / `SettingsValidator`. Requires `LazyInit` from `project/libs/structures.py`
(`python-di.mdc` → sibling `STRUCTURES.md`). Keep `env.example` in sync with required fields.
Logging: `LOG_LEVEL` and `Constants.LOG_FORMAT` (`python-logging.mdc`). Follow
`python-development-rules.mdc` for technology-specific `*_LOG_LEVEL` fields.

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
