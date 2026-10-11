"""
Authentication email service tests.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import quote

import pytest

import app.services.auth_email_service as auth_email_module
from app.email.providers.base import (
    EmailProviderError,
    OutboundEmailMessage,
)
from app.services.auth_email_service import AuthEmailService


@pytest.fixture
def provider() -> MagicMock:
    return MagicMock()


@pytest.fixture
def application_settings() -> SimpleNamespace:
    return SimpleNamespace(
        EMAIL_PROVIDER="development",
        FRONTEND_URL="https://novera.example/",
        EMAIL_FROM_EMAIL="no-reply@novera.example",
        EMAIL_FROM_NAME="Novera",
        EMAIL_REPLY_TO_EMAIL="support@novera.example",
    )


@pytest.fixture
def service(
    monkeypatch: pytest.MonkeyPatch,
    provider: MagicMock,
    application_settings: SimpleNamespace,
) -> AuthEmailService:
    monkeypatch.setattr(
        auth_email_module,
        "build_email_provider",
        lambda provider_name, *, application_settings: provider,
    )

    return AuthEmailService(
        application_settings=application_settings,
    )


def test_initializes_configured_provider(
    service: AuthEmailService,
    provider: MagicMock,
) -> None:
    assert service.provider is provider


def test_sends_password_reset_message_with_expected_headers_and_content(
    service: AuthEmailService,
    provider: MagicMock,
) -> None:
    service.send_password_reset_email(
        email="customer@example.com",
        first_name="Ada",
        token="raw-reset-token",
    )

    provider.send.assert_called_once()
    message = provider.send.call_args.args[0]

    assert isinstance(message, OutboundEmailMessage)
    assert message.from_email == "no-reply@novera.example"
    assert message.from_name == "Novera"
    assert message.to_email == "customer@example.com"
    assert message.to_name == "Ada"
    assert message.reply_to_email == "support@novera.example"
    assert message.subject == "Reset your Novera password"
    assert message.message_id.startswith("<password-reset-")
    assert message.message_id.endswith("@novera>")

    expected_url = (
        "https://novera.example/reset-password"
        "?token=raw-reset-token"
    )
    assert expected_url in message.body_text
    assert expected_url in message.body_html
    assert "expires in 1 hour" in message.body_text
    assert "can only be used once" in message.body_text
    assert "ignore this email" in message.body_text
    assert "<html" in message.body_html
    assert "Reset Password" in message.body_html


def test_escapes_first_name_in_html(
    service: AuthEmailService,
    provider: MagicMock,
) -> None:
    service.send_password_reset_email(
        email="customer@example.com",
        first_name='<img src=x onerror="alert(1)">',
        token="safe-token",
    )

    message = provider.send.call_args.args[0]

    assert '<img src=x onerror="alert(1)">' not in message.body_html
    assert '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;' in (
        message.body_html
    )
    assert '<img src=x onerror="alert(1)">' in message.body_text


def test_url_encodes_reset_token(
    service: AuthEmailService,
    provider: MagicMock,
) -> None:
    token = "part/one+two?three=four&five"

    service.send_password_reset_email(
        email="customer@example.com",
        first_name="Ada",
        token=token,
    )

    message = provider.send.call_args.args[0]
    expected_url = (
        "https://novera.example/reset-password?token="
        + quote(token, safe="")
    )

    assert expected_url in message.body_text
    assert expected_url in message.body_html
    assert "token=part/one+two?three=four&five" not in message.body_text


def test_propagates_provider_errors(
    service: AuthEmailService,
    provider: MagicMock,
) -> None:
    provider.send.side_effect = EmailProviderError(
        "SMTP unavailable",
        retryable=True,
    )

    with pytest.raises(
        EmailProviderError,
        match="SMTP unavailable",
    ):
        service.send_password_reset_email(
            email="customer@example.com",
            first_name="Ada",
            token="safe-token",
        )
