"""
Brevo transactional email provider using the HTTPS API.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.email.providers.base import (
    EmailProviderConfigurationError,
    EmailProviderError,
    EmailSendResult,
    OutboundEmailMessage,
)


class BrevoEmailProvider:
    """Submit outbound messages through Brevo's HTTPS API."""

    name = "brevo"
    API_URL = "https://api.brevo.com/v3/smtp/email"

    def __init__(
        self,
        *,
        api_key: str | None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.timeout_seconds = timeout_seconds

        if not self.api_key:
            raise EmailProviderConfigurationError(
                "BREVO_API_KEY is required when EMAIL_PROVIDER=brevo.",
                code="brevo_api_key_missing",
            )

        if timeout_seconds <= 0:
            raise EmailProviderConfigurationError(
                "Brevo timeout must be greater than zero.",
                code="brevo_timeout_invalid",
            )

    def send(
        self,
        message: OutboundEmailMessage,
    ) -> EmailSendResult:
        payload: dict = {
            "sender": {
                "email": message.from_email,
            },
            "to": [
                {
                    "email": message.to_email,
                }
            ],
            "subject": message.subject,
            "textContent": message.body_text,
        }

        if message.from_name:
            payload["sender"]["name"] = message.from_name

        if message.to_name:
            payload["to"][0]["name"] = message.to_name

        if message.body_html:
            payload["htmlContent"] = message.body_html

        if message.reply_to_email:
            payload["replyTo"] = {
                "email": message.reply_to_email,
            }

        # Keep provider-controlled headers out of custom headers.
        protected_headers = {
            "from",
            "to",
            "subject",
            "date",
            "message-id",
            "reply-to",
            "content-type",
            "mime-version",
        }

        custom_headers = {
            name: value
            for name, value in message.headers.items()
            if name.strip().lower() not in protected_headers
        }

        if custom_headers:
            payload["headers"] = custom_headers

        if message.attachments:
            payload["attachment"] = [
                {
                    "name": attachment.filename,
                    "content": base64.b64encode(
                        attachment.content
                    ).decode("ascii"),
                }
                for attachment in message.attachments
            ]

        request = Request(
            self.API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "accept": "application/json",
                "api-key": self.api_key,
                "content-type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                status_code = response.status
                response_body = response.read()

        except HTTPError as exc:
            self._raise_http_error(exc)

        except (URLError, OSError, TimeoutError) as exc:
            raise EmailProviderError(
                "Brevo API transport failed.",
                retryable=True,
                code="brevo_transport_error",
                details={
                    "error_type": type(exc).__name__,
                },
            ) from exc

        if not 200 <= status_code < 300:
            raise EmailProviderError(
                "Brevo returned an unexpected HTTP status.",
                retryable=status_code == 408
                or status_code == 429
                or status_code >= 500,
                code="brevo_unexpected_status",
                details={
                    "http_status": status_code,
                },
            )

        response_message_id = None

        if response_body:
            try:
                response_data = json.loads(response_body)
            except (ValueError, UnicodeDecodeError):
                response_data = {}

            if isinstance(response_data, dict):
                response_message_id = response_data.get(
                    "messageId"
                )

        return EmailSendResult(
            provider=self.name,
            message_id=str(
                response_message_id or message.message_id or ""
            ),
            accepted_at=datetime.now(UTC),
            details={
                "delivery_mode": "https_api",
                "http_status": status_code,
                "attachment_count": len(message.attachments),
            },
        )

    @staticmethod
    def _raise_http_error(exc: HTTPError) -> None:
        status_code = exc.code

        if status_code in {401, 403}:
            raise EmailProviderConfigurationError(
                "Brevo API authentication or authorization failed.",
                code="brevo_authentication_failed",
                details={
                    "http_status": status_code,
                },
            ) from exc

        retryable = (
            status_code in {408, 425, 429}
            or status_code >= 500
        )

        raise EmailProviderError(
            "Brevo rejected the email request.",
            retryable=retryable,
            code="brevo_http_error",
            details={
                "http_status": status_code,
            },
        ) from exc
