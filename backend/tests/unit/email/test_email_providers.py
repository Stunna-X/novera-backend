"""
Unit tests for email provider primitives.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.email.providers.base import (
    EmailAttachment,
    EmailProviderConfigurationError,
    OutboundEmailMessage,
    build_mime_message,
)
from app.email.providers.development import (
    DevelopmentEmailProvider,
)
from app.email.providers.smtp import SMTPEmailProvider


def build_message() -> OutboundEmailMessage:
    """
    Build a reusable outbound email payload.
    """

    return OutboundEmailMessage(
        from_email="no-reply@novera.local",
        from_name="Novera",
        reply_to_email="support@novera.local",
        to_email="customer@example.com",
        to_name="Customer",
        subject="Invoice INV-001",
        body_text="Please find your invoice attached.",
        body_html=(
            "<p>Please find your invoice attached.</p>"
        ),
        message_id=(
            "novera-test-message@novera.local"
        ),
        attachments=(
            EmailAttachment(
                filename="invoice.pdf",
                content=b"%PDF-1.4 test",
                content_type="application/pdf",
            ),
        ),
        headers={
            "X-Novera-Outbox-ID": "test-outbox-id",
        },
    )


def test_build_mime_message_contains_expected_content() -> None:
    """
    MIME output includes stable identity, bodies, and PDF.
    """

    mime_message = build_mime_message(
        build_message()
    )

    assert (
        str(mime_message["Message-ID"])
        == "<novera-test-message@novera.local>"
    )

    assert (
        str(mime_message["Subject"])
        == "Invoice INV-001"
    )

    assert (
        str(mime_message["X-Novera-Outbox-ID"])
        == "test-outbox-id"
    )

    attachments = list(
        mime_message.iter_attachments()
    )

    assert len(attachments) == 1
    assert attachments[0].get_filename() == "invoice.pdf"

    assert (
        attachments[0].get_content_type()
        == "application/pdf"
    )

    assert (
        attachments[0].get_payload(decode=True)
        == b"%PDF-1.4 test"
    )


def test_mime_builder_rejects_header_injection() -> None:
    """
    Newlines cannot be inserted into email headers.
    """

    message = OutboundEmailMessage(
        from_email="no-reply@novera.local",
        from_name="Novera",
        to_email="customer@example.com",
        to_name=None,
        subject="Invoice\r\nBcc: attacker@example.com",
        body_text="Test",
    )

    with pytest.raises(
        ValueError,
        match="cannot contain newlines",
    ):
        build_mime_message(message)


def test_development_provider_writes_and_deduplicates(
    tmp_path: Path,
) -> None:
    """
    A stable Message-ID produces one development email file.
    """

    provider = DevelopmentEmailProvider(
        output_directory=tmp_path,
    )

    first_result = provider.send(
        build_message()
    )

    second_result = provider.send(
        build_message()
    )

    generated_files = list(
        (tmp_path / "messages").glob("*.eml")
    )

    assert len(generated_files) == 1

    assert (
        first_result.message_id
        == second_result.message_id
    )

    assert (
        first_result.details["deduplicated"]
        is False
    )

    assert (
        second_result.details["deduplicated"]
        is True
    )


def test_smtp_provider_rejects_conflicting_tls_modes() -> None:
    """
    Implicit SSL and STARTTLS cannot both be active.
    """

    with pytest.raises(
        EmailProviderConfigurationError,
        match="cannot both be enabled",
    ):
        SMTPEmailProvider(
            host="smtp.example.com",
            port=465,
            username=None,
            password=None,
            use_starttls=True,
            use_ssl=True,
            timeout_seconds=30,
        )


def test_smtp_provider_requires_host() -> None:
    """
    SMTP cannot start without a configured server host.
    """

    with pytest.raises(
        EmailProviderConfigurationError,
        match="EMAIL_SMTP_HOST",
    ):
        SMTPEmailProvider(
            host=None,
            port=587,
            username=None,
            password=None,
            use_starttls=True,
            use_ssl=False,
            timeout_seconds=30,
        )