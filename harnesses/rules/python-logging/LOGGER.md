# Logging setup module

Copy this module to `project/logger.py` when the package does not already define `setup_logging`.
Call it once at process start (`apps/api.py` / `main.py`, `apps/bot.py`). Levels come from
`Settings()` (`python-settings`). Named library loggers are included only when the matching
Settings field exists.

```python
import logging.config
from pathlib import Path

from project.settings import Constants, Settings

_DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

_LIBRARY_LOGGERS = (
    ("FASTAPI_LOG_LEVEL", ("uvicorn", "fastapi")),
    ("TELEGRAM_LOG_LEVEL", ("telegram", "telegram.ext", "apscheduler")),
    ("HTTP_REQUESTS_LOG_LEVEL", ("httpx", "httpcore")),
    ("SQLALCHEMY_LOG_LEVEL", ("sqlalchemy", "sqlalchemy.engine")),
    ("REDIS_LOG_LEVEL", ("redis",)),
)


def _named(level: str, handlers: list[str]) -> dict:
    return {"level": level, "handlers": handlers, "propagate": False}


def setup_logging() -> None:
    log_level = Settings().LOG_LEVEL
    log_format = getattr(Constants, "LOG_FORMAT", _DEFAULT_FORMAT)
    loggers: dict[str, dict] = {}

    for field, names in _LIBRARY_LOGGERS:
        level = getattr(Settings(), field, None)
        if not level:
            continue
        for name in names:
            loggers[name] = _named(level, ["console"])

    config = {
        "version": 1,
        "disable_existing_loggers": True,
        "formatters": {
            "default": {
                "format": log_format,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": loggers,
        "root": {"level": log_level, "handlers": ["console"], "propagate": False},
    }

    if getattr(Settings(), "WRITE_LOGS_TO_FILE", False):
        log_dir = Path(__file__).resolve().parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        config["handlers"]["file"] = {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "level": log_level,
            "formatter": "default",
            "filename": str(log_dir / "app.log"),
            "when": "midnight",
            "backupCount": 14,
            "encoding": "utf8",
        }

        for logger_config in config["loggers"].values():
            logger_config["handlers"].append("file")
        config["root"]["handlers"].append("file")

    logging.config.dictConfig(config)
```
