"""Logging configuration regression tests."""

from __future__ import annotations

import json
import logging

from app.core.config import Settings
from app.core.logging import (
    JsonLogFormatter,
    configure_logging,
)


DATABASE_URL = (
    "postgresql+psycopg2://postgres:postgres@localhost:5432/novera"
)


def make_settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        DATABASE_URL=DATABASE_URL,
        SECRET_KEY="a" * 48,
        EMAIL_PROVIDER="manual",
        CORS_ORIGINS=["https://app.novera.example"],
        **overrides,
    )


def test_json_formatter_emits_structured_record() -> None:
    formatter = JsonLogFormatter()

    record = logging.LogRecord(
        name="novera.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Service started",
        args=(),
        exc_info=None,
    )

    payload = json.loads(
        formatter.format(record)
    )

    assert payload["level"] == "INFO"
    assert payload["logger"] == "novera.test"
    assert payload["message"] == "Service started"
    assert "timestamp" in payload


def test_development_logging_uses_console_formatter() -> None:
    settings = make_settings(
        APP_ENV="development",
        LOG_JSON=False,
    )

    configure_logging(settings)

    handler = logging.getLogger().handlers[0]

    assert not isinstance(
        handler.formatter,
        JsonLogFormatter,
    )


def test_production_logging_uses_json_formatter() -> None:
    settings = make_settings(
        APP_ENV="production",
        LOG_JSON=False,
    )

    configure_logging(settings)

    handler = logging.getLogger().handlers[0]

    assert isinstance(
        handler.formatter,
        JsonLogFormatter,
    )
