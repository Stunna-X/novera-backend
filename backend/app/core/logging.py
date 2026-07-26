"""Application logging configuration."""

from __future__ import annotations

import json
import logging
import logging.config
import sys
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings


class JsonLogFormatter(logging.Formatter):
    """Render one log record as a structured JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(
                record.exc_info
            )

        if record.stack_info:
            payload["stack"] = self.formatStack(
                record.stack_info
            )

        return json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )


def configure_logging(application_settings: Settings) -> None:
    """Configure deterministic console logging for the process."""

    formatter_name = (
        "json"
        if application_settings.json_logging_enabled
        else "console"
    )

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "console": {
                    "format": (
                        "%(asctime)s | %(levelname)s | "
                        "%(name)s | %(message)s"
                    ),
                },
                "json": {
                    "()": "app.core.logging.JsonLogFormatter",
                },
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                    "formatter": formatter_name,
                },
            },
            "root": {
                "handlers": ["default"],
                "level": application_settings.LOG_LEVEL,
            },
            "loggers": {
                "uvicorn": {
                    "handlers": ["default"],
                    "level": application_settings.LOG_LEVEL,
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["default"],
                    "level": application_settings.LOG_LEVEL,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["default"],
                    "level": application_settings.LOG_LEVEL,
                    "propagate": False,
                },
            },
        }
    )

    logging.captureWarnings(True)
