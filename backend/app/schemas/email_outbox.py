"""
Email outbox schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


EmailProvider = Literal[
    "development",
    "smtp",
    "sendgrid",
    "mailgun",
    "manual",
]

EmailOutboxStatus = Literal[
    "queued",
    "sending",
    "sent",
    "failed",
    "cancelled",
]


class EmailOutboxMarkSentRequest(BaseModel):
    """
    Payload for marking a queued email as sent after a real
    provider confirms delivery acceptance.
    """

    provider_message_id: str | None = Field(
        default=None,
        max_length=255,
    )
    note: str | None = Field(
        default=None,
        max_length=2000,
    )

    @field_validator(
        "provider_message_id",
        "note",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned = value.strip()

        return cleaned or None


class EmailOutboxMarkFailedRequest(BaseModel):
    """
    Payload for marking an email as failed.
    """

    reason: str = Field(
        min_length=3,
        max_length=5000,
    )
    retryable: bool = True

    @field_validator("reason")
    @classmethod
    def normalize_reason(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip()

        if len(cleaned) < 3:
            raise ValueError(
                "Failure reason must contain at least 3 characters."
            )

        return cleaned


class EmailOutboxRetryRequest(BaseModel):
    """
    Payload for re-queueing a failed email.
    """

    note: str | None = Field(
        default=None,
        max_length=2000,
    )

    @field_validator("note")
    @classmethod
    def normalize_note(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned = value.strip()

        return cleaned or None


class EmailOutboxResponse(BaseModel):
    """
    One email outbox response.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    organization_id: uuid.UUID
    document_delivery_id: uuid.UUID

    queued_by_user_id: uuid.UUID | None
    queued_by_first_name: str | None = None
    queued_by_last_name: str | None = None
    queued_by_email: str | None = None

    provider: EmailProvider
    status: EmailOutboxStatus

    from_email: str
    from_name: str | None
    reply_to_email: str | None

    to_email: str
    to_name: str | None

    subject: str
    body_text: str
    body_html: str | None
    attachment_filename: str | None

    attempts: int
    max_attempts: int
    next_attempt_at: datetime | None

    queued_at: datetime
    sent_at: datetime | None
    failed_at: datetime | None

    last_error: str | None
    provider_message_id: str | None

    details: dict[str, Any]

    is_active: bool
    created_at: datetime
    updated_at: datetime


class EmailOutboxListResponse(BaseModel):
    """
    Paginated email outbox response.
    """

    items: list[EmailOutboxResponse]
    total: int
    skip: int
    limit: int
