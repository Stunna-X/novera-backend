"""
Work-order activity model.

Stores an immutable operational timeline for each work order.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
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
    from app.models.work_order import WorkOrder


class WorkOrderActivity(BaseModel):
    """
    Immutable activity entry for a work order.
    """

    __tablename__ = "work_order_activities"

    __table_args__ = (
        Index(
            "ix_work_order_activities_organization_work_order",
            "organization_id",
            "work_order_id",
        ),
        Index(
            "ix_work_order_activities_work_order_created",
            "work_order_id",
            "created_at",
        ),
        Index(
            "ix_work_order_activities_organization_type",
            "organization_id",
            "activity_type",
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

    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "work_orders.id",
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

    activity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    summary: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    from_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    to_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
    )

    work_order: Mapped["WorkOrder"] = relationship(
        "WorkOrder",
        back_populates="activities",
    )

    actor: Mapped["User | None"] = relationship(
        "User",
        lazy="joined",
    )

    def __repr__(self) -> str:
        """
        Return a developer-friendly representation.
        """

        return (
            f"<WorkOrderActivity "
            f"id={self.id} "
            f"work_order_id={self.work_order_id} "
            f"activity_type={self.activity_type!r}>"
        )