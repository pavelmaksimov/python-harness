import logging.config

from project.settings import Constants, Settings

_DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def setup_logging() -> None:
    log_level = Settings().LOG_LEVEL
    log_format = getattr(Constants, "LOG_FORMAT", _DEFAULT_FORMAT)

    config = {
        "version": 1,
        "disable_existing_loggers": False,
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
        "loggers": {},
        "root": {"level": log_level, "handlers": ["console"], "propagate": False},
    }

    logging.config.dictConfig(config)
