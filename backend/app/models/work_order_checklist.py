"""
Work-order checklist model.

Stores operational checklist items attached to work orders.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel
from app.enums.work_order_checklist import WorkOrderChecklistStatus

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.work_order import WorkOrder


class WorkOrderChecklistItem(BaseModel):
    """
    One operational checklist item belonging to a work order.
    """

    __tablename__ = "work_order_checklist_items"

    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "work_orders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=WorkOrderChecklistStatus.PENDING.value,
        server_default=WorkOrderChecklistStatus.PENDING.value,
        index=True,
    )

    is_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    completion_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    completed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    skipped_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    skipped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    work_order: Mapped["WorkOrder"] = relationship(
        "WorkOrder",
        back_populates="checklist_items",
    )

    completed_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[completed_by_user_id],
    )

    skipped_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[skipped_by_user_id],
    )

    __table_args__ = (
        CheckConstraint(
            "position >= 0",
            name="ck_work_order_checklist_position_non_negative",
        ),
        CheckConstraint(
            "status IN ('pending', 'completed', 'skipped')",
            name="ck_work_order_checklist_status_valid",
        ),
        UniqueConstraint(
            "work_order_id",
            "position",
            name="uq_work_order_checklist_position",
        ),
        Index(
            "ix_work_order_checklist_work_order_active_position",
            "work_order_id",
            "is_active",
            "position",
        ),
    )