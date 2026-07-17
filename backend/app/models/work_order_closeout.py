"""Work-order closeout model.

Stores completion reports, customer sign-off, invoice-readiness,
and closeout audit data for completed work orders.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
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


class WorkOrderCloseout(BaseModel):
    """Customer-facing closeout record for one work order."""

    __tablename__ = "work_order_closeouts"

    __table_args__ = (
        UniqueConstraint(
            "work_order_id",
            name="uq_work_order_closeouts_work_order_id",
        ),
        Index(
            "ix_work_order_closeouts_organization_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_work_order_closeouts_invoice_ready",
            "organization_id",
            "is_invoice_ready",
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

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    rejected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    invoice_ready_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="submitted",
        index=True,
    )

    completion_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    work_performed: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    materials_used: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    customer_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    internal_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    customer_name: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )

    customer_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    customer_phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    customer_title: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    customer_signature_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    customer_rating: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    customer_feedback: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    invoice_ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_invoice_ready: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
    )

    work_order: Mapped["WorkOrder"] = relationship(
        "WorkOrder",
    )

    created_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by_user_id],
    )

    submitted_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[submitted_by_user_id],
    )

    approved_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[approved_by_user_id],
    )

    rejected_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[rejected_by_user_id],
    )

    invoice_ready_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[invoice_ready_by_user_id],
    )

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""

        return (
            f"<WorkOrderCloseout "
            f"id={self.id} "
            f"work_order_id={self.work_order_id} "
            f"status={self.status!r}>"
        )
