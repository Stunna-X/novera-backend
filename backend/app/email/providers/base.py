"""
Provider-independent outbound email primitives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.headerregistry import Address
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import format_datetime, make_msgid
from typing import Any, Mapping, Protocol


@dataclass(
    frozen=True,
    slots=True,
)
class EmailAttachment:
    """
    One in-memory email attachment.
    """

    filename: str
    content: bytes
    content_type: str = "application/octet-stream"


@dataclass(
    frozen=True,
    slots=True,
)
class OutboundEmailMessage:
    """
    Provider-independent outbound email payload.
    """

    from_email: str
    from_name: str | None

    to_email: str
    to_name: str | None

    subject: str
    body_text: str
    body_html: str | None = None

    reply_to_email: str | None = None
    message_id: str | None = None

    attachments: tuple[EmailAttachment, ...] = ()
    headers: Mapping[str, str] = field(
        default_factory=dict,
    )


@dataclass(
    frozen=True,
    slots=True,
)
class EmailSendResult:
    """
    Successful provider acceptance result.

    Provider acceptance does not prove that the recipient
    opened or ultimately received the message.
    """

    provider: str
    message_id: str
    accepted_at: datetime
    details: dict[str, Any] = field(
        default_factory=dict,
    )


class EmailProviderError(RuntimeError):
    """
    Provider failure with retryability metadata.
    """

    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)

        self.retryable = retryable
        self.code = code
        self.details = details or {}


class EmailProviderConfigurationError(
    EmailProviderError
):
    """
    Non-retryable provider configuration failure.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_configuration_error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            retryable=False,
            code=code,
            details=details,
        )


class EmailProvider(Protocol):
    """
    Interface implemented by outbound email providers.
    """

    name: str

    def send(
        self,
        message: OutboundEmailMessage,
    ) -> EmailSendResult:
        """
        Submit one outbound email.
        """


def build_mime_message(
    message: OutboundEmailMessage,
) -> EmailMessage:
    """
    Convert a provider-independent payload into a MIME message.
    """

    mime_message = EmailMessage(
        policy=SMTP,
    )

    mime_message["From"] = _format_address(
        email_address=message.from_email,
        display_name=message.from_name,
    )

    mime_message["To"] = _format_address(
        email_address=message.to_email,
        display_name=message.to_name,
    )

    mime_message["Subject"] = _safe_header_value(
        message.subject
    )

    mime_message["Date"] = format_datetime(
        datetime.now(UTC)
    )

    mime_message["Message-ID"] = (
        _normalize_message_id(message.message_id)
        if message.message_id
        else make_msgid()
    )

    if message.reply_to_email:
        mime_message["Reply-To"] = (
            message.reply_to_email
        )

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

    for header_name, header_value in (
        message.headers.items()
    ):
        normalized_name = header_name.strip().lower()

        if normalized_name in protected_headers:
            continue

        mime_message[header_name] = (
            _safe_header_value(header_value)
        )

    mime_message.set_content(
        message.body_text,
        subtype="plain",
        charset="utf-8",
    )

    if message.body_html:
        mime_message.add_alternative(
            message.body_html,
            subtype="html",
            charset="utf-8",
        )

    for attachment in message.attachments:
        maintype, separator, subtype = (
            attachment.content_type.partition("/")
        )

        if not separator:
            maintype = "application"
            subtype = "octet-stream"

        mime_message.add_attachment(
            attachment.content,
            maintype=maintype,
            subtype=subtype,
            filename=attachment.filename,
        )

    return mime_message


def _format_address(
    *,
    email_address: str,
    display_name: str | None,
) -> str:
    """
    Safely format one email address with an optional name.
    """

    return str(
        Address(
            display_name=display_name or "",
            addr_spec=email_address,
        )
    )


def _normalize_message_id(
    value: str,
) -> str:
    """
    Normalize a stable RFC Message-ID value.
    """

    cleaned = _safe_header_value(value).strip()

    if not cleaned:
        return make_msgid()

    if not cleaned.startswith("<"):
        cleaned = f"<{cleaned}"

    if not cleaned.endswith(">"):
        cleaned = f"{cleaned}>"

    return cleaned


def _safe_header_value(
    value: str,
) -> str:
    """
    Prevent newline-based header injection.
    """

    cleaned = str(value).strip()

    if "\r" in cleaned or "\n" in cleaned:
        raise ValueError(
            "Email header values cannot contain newlines."
        )

    return cleaned