"""
Development email provider.

Writes complete RFC email messages to disk instead of sending
network email. A stable Message-ID produces a stable filename,
making repeated processing inspectable and locally idempotent.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from app.email.providers.base import (
    EmailProviderError,
    EmailSendResult,
    OutboundEmailMessage,
    build_mime_message,
)


class DevelopmentEmailProvider:
    """
    Save outbound messages as local `.eml` files.
    """

    name = "development"

    def __init__(
        self,
        *,
        output_directory: Path,
    ) -> None:
        self.output_directory = output_directory

    def send(
        self,
        message: OutboundEmailMessage,
    ) -> EmailSendResult:
        accepted_at = datetime.now(UTC)
        mime_message = build_mime_message(
            message
        )

        message_id = str(
            mime_message["Message-ID"]
        )

        message_hash = hashlib.sha256(
            message_id.encode("utf-8")
        ).hexdigest()

        message_directory = (
            self.output_directory
            / "messages"
        )

        message_path = (
            message_directory
            / f"{message_hash}.eml"
        )

        temporary_path = (
            message_directory
            / f"{message_hash}.tmp"
        )

        try:
            message_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            if message_path.exists():
                return EmailSendResult(
                    provider=self.name,
                    message_id=message_id,
                    accepted_at=accepted_at,
                    details={
                        "delivery_mode": (
                            "local_eml_file"
                        ),
                        "stored_path": str(
                            message_path.relative_to(
                                self.output_directory
                            )
                        ),
                        "attachment_count": len(
                            message.attachments
                        ),
                        "deduplicated": True,
                    },
                )

            temporary_path.write_bytes(
                mime_message.as_bytes()
            )

            temporary_path.replace(
                message_path
            )

        except OSError as exc:
            try:
                if temporary_path.exists():
                    temporary_path.unlink()
            except OSError:
                pass

            raise EmailProviderError(
                (
                    "Development email provider could not "
                    "write the message to disk."
                ),
                retryable=True,
                code="development_write_failed",
                details={
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            ) from exc

        return EmailSendResult(
            provider=self.name,
            message_id=message_id,
            accepted_at=accepted_at,
            details={
                "delivery_mode": "local_eml_file",
                "stored_path": str(
                    message_path.relative_to(
                        self.output_directory
                    )
                ),
                "attachment_count": len(
                    message.attachments
                ),
                "deduplicated": False,
            },
        )