"""
Document delivery schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


DocumentType = Literal["invoice", "quote"]
DeliveryChannel = Literal["email", "manual"]
DeliveryStatus = Literal["recorded", "queued", "sent", "failed"]


class DocumentDeliverySendRequest(BaseModel):
    """
    Request body for recording document delivery.
    """

    recipient_email: EmailStr
    recipient_name: str | None = Field(
        default=None,
        max_length=200,
    )
    subject: str | None = Field(
        default=None,
        max_length=255,
    )
    message: str | None = Field(
        default=None,
        max_length=5000,
    )
    include_pdf: bool = True

    @field_validator(
        "recipient_name",
        "subject",
        "message",
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


class DocumentDeliveryResponse(BaseModel):
    """
    One document delivery response.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    organization_id: uuid.UUID

    document_type: DocumentType
    document_id: uuid.UUID
    document_number: str

    recipient_email: str
    recipient_name: str | None

    subject: str
    message: str | None

    delivery_channel: DeliveryChannel
    delivery_status: DeliveryStatus
    provider: str

    pdf_filename: str | None
    sent_at: datetime | None

    sent_by_user_id: uuid.UUID | None
    sent_by_first_name: str | None = None
    sent_by_last_name: str | None = None
    sent_by_email: str | None = None

    details: dict

    is_active: bool
    created_at: datetime
    updated_at: datetime


class DocumentDeliveryListResponse(BaseModel):
    """
    Paginated document delivery response.
    """

    items: list[DocumentDeliveryResponse]
    total: int
    skip: int
    limit: int
