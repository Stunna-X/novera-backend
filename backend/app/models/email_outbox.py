"""
Email outbox model.

Stores outbound email jobs before they are sent by a real
provider worker. API requests enqueue messages; they do not
pretend that delivery has already happened.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


if TYPE_CHECKING:
    from app.models.document_delivery import DocumentDelivery
    from app.models.organization import Organization
    from app.models.user import User


class EmailOutbox(BaseModel):
    """
    One queued outbound email job.
    """

    __tablename__ = "email_outbox"

    __table_args__ = (
        UniqueConstraint(
            "document_delivery_id",
            name="uq_email_outbox_document_delivery",
        ),
        CheckConstraint(
            "provider IN ('development', 'smtp', 'sendgrid', 'mailgun', 'manual')",
            name="ck_email_outbox_provider_valid",
        ),
        CheckConstraint(
            """
            status IN (
                'queued',
                'sending',
                'sent',
                'failed',
                'cancelled'
            )
            """,
            name="ck_email_outbox_status_valid",
        ),
        CheckConstraint(
            "attempts >= 0",
            name="ck_email_outbox_attempts_non_negative",
        ),
        CheckConstraint(
            "max_attempts > 0",
            name="ck_email_outbox_max_attempts_positive",
        ),
        Index(
            "ix_email_outbox_organization_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_email_outbox_organization_created",
            "organization_id",
            "created_at",
        ),
        Index(
            "ix_email_outbox_delivery",
            "document_delivery_id",
        ),
        Index(
            "ix_email_outbox_next_attempt",
            "status",
            "next_attempt_at",
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

    document_delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "document_deliveries.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    queued_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    provider: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="development",
        server_default="development",
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )

    from_email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
    )

    from_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    reply_to_email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )

    to_email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        index=True,
    )

    to_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    body_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    body_html: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    attachment_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default="3",
    )

    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    provider_message_id: Mapped[str | None] = mapped_column(
        String(255),
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        lazy="joined",
    )

    document_delivery: Mapped["DocumentDelivery"] = relationship(
        "DocumentDelivery",
        lazy="joined",
    )

    queued_by: Mapped["User | None"] = relationship(
        "User",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<EmailOutbox "
            f"id={self.id} "
            f"to={self.to_email!r} "
            f"status={self.status!r} "
            f"provider={self.provider!r}>"
        )
