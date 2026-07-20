"""
Unit tests for email dispatcher calculations.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.email_dispatcher_service import (
    EmailDispatcherService,
)


def test_retry_delay_uses_exponential_backoff(
    monkeypatch,
) -> None:
    """
    Retry delay doubles after every failed attempt.
    """

    monkeypatch.setattr(
        settings,
        "EMAIL_OUTBOX_RETRY_BASE_SECONDS",
        10,
    )

    monkeypatch.setattr(
        settings,
        "EMAIL_OUTBOX_RETRY_MAX_SECONDS",
        1000,
    )

    assert (
        EmailDispatcherService
        ._retry_delay_seconds(attempts=1)
        == 10
    )

    assert (
        EmailDispatcherService
        ._retry_delay_seconds(attempts=2)
        == 20
    )

    assert (
        EmailDispatcherService
        ._retry_delay_seconds(attempts=3)
        == 40
    )


def test_retry_delay_respects_maximum(
    monkeypatch,
) -> None:
    """
    Exponential backoff never exceeds its configured cap.
    """

    monkeypatch.setattr(
        settings,
        "EMAIL_OUTBOX_RETRY_BASE_SECONDS",
        60,
    )

    monkeypatch.setattr(
        settings,
        "EMAIL_OUTBOX_RETRY_MAX_SECONDS",
        120,
    )

    assert (
        EmailDispatcherService
        ._retry_delay_seconds(attempts=10)
        == 120
    )