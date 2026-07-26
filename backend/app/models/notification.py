"""
Notification model.

Stores organization-scoped user notifications for operational,
commercial, and financial events.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import BaseModel


if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class Notification(BaseModel):
    """
    One notification delivered to one user in one organization.
    """

    __tablename__ = "notifications"

    __table_args__ = (
        Index(
            "ix_notifications_organization_recipient",
            "organization_id",
            "recipient_user_id",
        ),
        Index(
            "ix_notifications_organization_unread",
            "organization_id",
            "recipient_user_id",
            "is_read",
        ),
        Index(
            "ix_notifications_organization_archived",
            "organization_id",
            "recipient_user_id",
            "is_archived",
        ),
        Index(
            "ix_notifications_organization_type",
            "organization_id",
            "notification_type",
        ),
        Index(
            "ix_notifications_entity",
            "entity_type",
            "entity_id",
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

    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    notification_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="info",
        server_default="info",
        index=True,
    )

    entity_type: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        index=True,
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    action_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )

    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
    )

    recipient: Mapped["User"] = relationship(
        "User",
        foreign_keys=[recipient_user_id],
        lazy="joined",
    )

    actor: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[actor_user_id],
        lazy="joined",
    )

    def __repr__(self) -> str:
        """
        Return a developer-friendly representation.
        """

        return (
            f"<Notification "
            f"id={self.id} "
            f"type={self.notification_type!r} "
            f"recipient_user_id={self.recipient_user_id}>"
        )
