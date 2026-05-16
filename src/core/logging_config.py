import logging
import sys
from logging.config import dictConfig

from core.config import settings


class LevelColorFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[34m",
        "INFO": "\033[36m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[37;41m",
    }
    LOGGER_COLOR = "\033[90m"
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        record.levelname = (
            f"{self.COLORS.get(record.levelname, '')}{record.levelname}{self.RESET}"
        )
        record.name = f"{self.LOGGER_COLOR}{record.name}{self.RESET}"
        return super().format(record)


def configure_logging() -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "compact": {
                    "()": LevelColorFormatter,
                    "format": "%(levelname)s %(name)s: %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                    "formatter": "compact",
                },
            },
            "root": {"handlers": ["console"], "level": settings.LOG_LEVEL},
            "loggers": {
                "uvicorn": {
                    "handlers": ["console"],
                    "level": settings.LOG_LEVEL,
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["console"],
                    "level": settings.LOG_LEVEL,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["console"],
                    "level": settings.ACCEPT_LOG_LEVEL,
                    "propagate": False,
                },
            },
        }
    )
