"""
Document delivery model.

Tracks customer-facing document delivery attempts for invoices,
quotes, PDFs, and future email-provider integrations.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class DocumentDelivery(BaseModel):
    """
    One tracked delivery event for a customer-facing document.
    """

    __tablename__ = "document_deliveries"

    __table_args__ = (
        CheckConstraint(
            "document_type IN ('invoice', 'quote')",
            name="ck_document_deliveries_document_type_valid",
        ),
        CheckConstraint(
            "delivery_channel IN ('email', 'manual')",
            name="ck_document_deliveries_channel_valid",
        ),
        CheckConstraint(
            """
            delivery_status IN (
                'recorded',
                'queued',
                'sent',
                'failed'
            )
            """,
            name="ck_document_deliveries_status_valid",
        ),
        Index(
            "ix_document_deliveries_organization_created",
            "organization_id",
            "created_at",
        ),
        Index(
            "ix_document_deliveries_organization_type",
            "organization_id",
            "document_type",
        ),
        Index(
            "ix_document_deliveries_document",
            "document_type",
            "document_id",
        ),
        Index(
            "ix_document_deliveries_status",
            "organization_id",
            "delivery_status",
        ),
        Index(
            "ix_document_deliveries_recipient_email",
            "recipient_email",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    document_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    document_number: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        index=True,
    )

    recipient_email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        index=True,
    )

    recipient_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    delivery_channel: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="email",
        server_default="email",
        index=True,
    )

    delivery_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="recorded",
        server_default="recorded",
        index=True,
    )

    provider: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="manual",
        server_default="manual",
    )

    pdf_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    sent_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        lazy="joined",
    )

    sent_by: Mapped["User | None"] = relationship(
        "User",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentDelivery "
            f"id={self.id} "
            f"document_type={self.document_type!r} "
            f"document_number={self.document_number!r} "
            f"status={self.delivery_status!r}>"
        )
