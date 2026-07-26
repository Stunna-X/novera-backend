"""
Email provider factory.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import Settings, settings
from app.email.providers.base import (
    EmailProvider,
    EmailProviderConfigurationError,
)
from app.email.providers.development import (
    DevelopmentEmailProvider,
)
from app.email.providers.smtp import SMTPEmailProvider


def build_email_provider(
    provider_name: str,
    *,
    application_settings: Settings = settings,
) -> EmailProvider:
    """
    Build the configured outbound email provider.
    """

    normalized_provider = (
        provider_name.strip().lower()
    )

    if normalized_provider == "development":
        return DevelopmentEmailProvider(
            output_directory=Path(
                application_settings
                .EMAIL_DEVELOPMENT_OUTBOX_DIR
            ),
        )

    if normalized_provider == "smtp":
        return SMTPEmailProvider(
            host=application_settings.EMAIL_SMTP_HOST,
            port=application_settings.EMAIL_SMTP_PORT,
            username=(
                application_settings.EMAIL_SMTP_USERNAME
            ),
            password=(
                application_settings.EMAIL_SMTP_PASSWORD
            ),
            use_starttls=(
                application_settings
                .EMAIL_SMTP_USE_STARTTLS
            ),
            use_ssl=(
                application_settings.EMAIL_SMTP_USE_SSL
            ),
            timeout_seconds=(
                application_settings
                .EMAIL_SMTP_TIMEOUT_SECONDS
            ),
        )

    if normalized_provider == "manual":
        raise EmailProviderConfigurationError(
            (
                "The manual provider cannot be processed by "
                "the automatic email worker."
            ),
            code="manual_provider_not_dispatchable",
        )

    if normalized_provider in {
        "sendgrid",
        "mailgun",
    }:
        raise EmailProviderConfigurationError(
            (
                f"The {normalized_provider} provider is declared "
                "but has not been configured yet."
            ),
            code="provider_not_implemented",
            details={
                "provider": normalized_provider,
            },
        )

    raise EmailProviderConfigurationError(
        f"Unsupported email provider: {provider_name!r}.",
        code="provider_unsupported",
        details={
            "provider": provider_name,
        },
    )