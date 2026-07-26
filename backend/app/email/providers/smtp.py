"""
SMTP email provider.
"""

from __future__ import annotations

import smtplib
import ssl
from datetime import UTC, datetime
from typing import Any

from app.email.providers.base import (
    EmailProviderConfigurationError,
    EmailProviderError,
    EmailSendResult,
    OutboundEmailMessage,
    build_mime_message,
)


class SMTPEmailProvider:
    """
    Submit outbound messages through an SMTP server.
    """

    name = "smtp"

    def __init__(
        self,
        *,
        host: str | None,
        port: int,
        username: str | None,
        password: str | None,
        use_starttls: bool,
        use_ssl: bool,
        timeout_seconds: float,
    ) -> None:
        self.host = (host or "").strip()
        self.port = port
        self.username = (
            username.strip()
            if username
            else None
        )
        self.password = password
        self.use_starttls = use_starttls
        self.use_ssl = use_ssl
        self.timeout_seconds = timeout_seconds

        self._validate_configuration()

    def send(
        self,
        message: OutboundEmailMessage,
    ) -> EmailSendResult:
        mime_message = build_mime_message(message)

        message_id = str(
            mime_message["Message-ID"]
        )

        ssl_context = ssl.create_default_context()

        try:
            if self.use_ssl:
                client: smtplib.SMTP = (
                    smtplib.SMTP_SSL(
                        host=self.host,
                        port=self.port,
                        timeout=self.timeout_seconds,
                        context=ssl_context,
                    )
                )
            else:
                client = smtplib.SMTP(
                    host=self.host,
                    port=self.port,
                    timeout=self.timeout_seconds,
                )

            with client:
                client.ehlo()

                if self.use_starttls:
                    client.starttls(
                        context=ssl_context,
                    )
                    client.ehlo()

                if self.username:
                    client.login(
                        self.username,
                        self.password or "",
                    )

                refused_recipients = (
                    client.send_message(
                        mime_message,
                        from_addr=message.from_email,
                        to_addrs=[message.to_email],
                    )
                )

                if refused_recipients:
                    self._raise_refused_recipient(
                        refused_recipients
                    )

        except EmailProviderError:
            raise

        except smtplib.SMTPRecipientsRefused as exc:
            self._raise_refused_recipient(
                exc.recipients
            )

        except smtplib.SMTPAuthenticationError as exc:
            raise EmailProviderConfigurationError(
                "SMTP authentication failed.",
                code="smtp_authentication_failed",
                details={
                    "smtp_code": exc.smtp_code,
                    "smtp_error": self._decode_error(
                        exc.smtp_error
                    ),
                },
            ) from exc

        except smtplib.SMTPResponseException as exc:
            retryable = 400 <= exc.smtp_code < 500

            raise EmailProviderError(
                (
                    "SMTP server rejected the email request "
                    f"with status {exc.smtp_code}."
                ),
                retryable=retryable,
                code="smtp_response_error",
                details={
                    "smtp_code": exc.smtp_code,
                    "smtp_error": self._decode_error(
                        exc.smtp_error
                    ),
                },
            ) from exc

        except (
            smtplib.SMTPException,
            OSError,
            TimeoutError,
        ) as exc:
            raise EmailProviderError(
                "SMTP delivery attempt failed.",
                retryable=True,
                code="smtp_transport_error",
                details={
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            ) from exc

        return EmailSendResult(
            provider=self.name,
            message_id=message_id,
            accepted_at=datetime.now(UTC),
            details={
                "delivery_mode": "smtp",
                "smtp_host": self.host,
                "smtp_port": self.port,
                "starttls": self.use_starttls,
                "ssl": self.use_ssl,
                "attachment_count": len(
                    message.attachments
                ),
            },
        )

    def _validate_configuration(
        self,
    ) -> None:
        if not self.host:
            raise EmailProviderConfigurationError(
                (
                    "EMAIL_SMTP_HOST is required when "
                    "EMAIL_PROVIDER is smtp."
                ),
                code="smtp_host_missing",
            )

        if self.use_ssl and self.use_starttls:
            raise EmailProviderConfigurationError(
                (
                    "EMAIL_SMTP_USE_SSL and "
                    "EMAIL_SMTP_USE_STARTTLS cannot both "
                    "be enabled."
                ),
                code="smtp_tls_configuration_invalid",
            )

        if self.username and self.password is None:
            raise EmailProviderConfigurationError(
                (
                    "EMAIL_SMTP_PASSWORD is required when "
                    "EMAIL_SMTP_USERNAME is configured."
                ),
                code="smtp_password_missing",
            )

    def _raise_refused_recipient(
        self,
        refused_recipients: dict[
            str,
            tuple[int, bytes | str],
        ],
    ) -> None:
        recipient_details: dict[str, Any] = {}

        retryable = False

        for recipient, response in (
            refused_recipients.items()
        ):
            smtp_code, smtp_error = response

            recipient_details[recipient] = {
                "smtp_code": smtp_code,
                "smtp_error": self._decode_error(
                    smtp_error
                ),
            }

            if 400 <= smtp_code < 500:
                retryable = True

        raise EmailProviderError(
            "SMTP server refused the recipient address.",
            retryable=retryable,
            code="smtp_recipient_refused",
            details={
                "recipients": recipient_details,
            },
        )

    @staticmethod
    def _decode_error(
        value: bytes | str,
    ) -> str:
        if isinstance(value, bytes):
            return value.decode(
                "utf-8",
                errors="replace",
            )

        return str(value)