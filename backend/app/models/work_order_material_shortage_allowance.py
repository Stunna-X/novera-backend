"""
Work-order material shortage allowance model.

Represents operational authorization to proceed with a material
shortage without changing the underlying physical inventory truth.

An allowance is an authorization record only. Inventory balances,
reservations, and procurement remain independent sources of truth.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.work_order import WorkOrder
    from app.models.work_order_material import WorkOrderMaterialRequirement


class WorkOrderMaterialShortageAllowance(BaseModel):
    """
    Operational authorization for a material shortage on a work order.

    The allowance does not create, reserve, consume, or otherwise modify
    physical inventory. It records the authorized quantity that allows
    the work order to proceed despite an outstanding material shortage.
    """

    __tablename__ = "work_order_material_shortage_allowances"

    __table_args__ = (
        UniqueConstraint(
            "work_order_material_requirement_id",
            name="uq_work_order_material_shortage_allowances_requirement",
        ),
        CheckConstraint(
            "requested_quantity > 0",
            name="requested_quantity_positive",
        ),
        CheckConstraint(
            "approved_quantity >= 0",
            name="approved_quantity_non_negative",
        ),
        CheckConstraint(
            "approved_quantity <= requested_quantity",
            name="approved_quantity_not_greater_than_requested",
        ),
        CheckConstraint(
            "status IN ("
            "'draft', "
            "'submitted', "
            "'approved', "
            "'rejected', "
            "'cancelled'"
            ")",
            name="valid_status",
        ),
        Index(
            "ix_shortage_allowance_org_work_order",
            "organization_id",
            "work_order_id",
        ),
        Index(
            "ix_shortage_allowance_work_order_status",
            "work_order_id",
            "status",
        ),
        Index(
            "ix_shortage_allowance_requirement_status",
            "work_order_material_requirement_id",
            "status",
        ),
        Index(
            "ix_shortage_allowance_org_active",
            "organization_id",
            "is_active",
        ),
        Index(
            "ix_shortage_allowance_work_order",
            "work_order_id",
        ),
        Index(
            "ix_shortage_allowance_created_by",
            "created_by_user_id",
        ),
        Index(
            "ix_shortage_allowance_submitted_by",
            "submitted_by_user_id",
        ),
        Index(
            "ix_shortage_allowance_approved_by",
            "approved_by_user_id",
        ),
        Index(
            "ix_shortage_allowance_rejected_by",
            "rejected_by_user_id",
        ),
        Index(
            "ix_shortage_allowance_cancelled_by",
            "cancelled_by_user_id",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
        ),
        nullable=False,

    )

    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "work_orders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    work_order_material_requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "work_order_material_requirements.id",
            ondelete="CASCADE",
        ),
        nullable=False,

    )

    requested_quantity: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=16,
            scale=3,
        ),
        nullable=False,
    )

    approved_quantity: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=16,
            scale=3,
        ),
        nullable=False,
        default=Decimal("0"),
        server_default=text("0"),
    )

    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="draft",
        server_default=text("'draft'"),
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    rejected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
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

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    cancellation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        lazy="joined",
    )

    work_order: Mapped["WorkOrder"] = relationship(
        "WorkOrder",
        lazy="joined",
    )

    work_order_material_requirement: Mapped[
        "WorkOrderMaterialRequirement"
    ] = relationship(
        "WorkOrderMaterialRequirement",
        lazy="joined",
    )

    created_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by_user_id],
        lazy="joined",
    )

    submitted_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[submitted_by_user_id],
        lazy="joined",
    )

    approved_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[approved_by_user_id],
        lazy="joined",
    )

    rejected_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[rejected_by_user_id],
        lazy="joined",
    )

    cancelled_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[cancelled_by_user_id],
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            "<WorkOrderMaterialShortageAllowance "
            f"id={self.id} "
            f"work_order_id={self.work_order_id} "
            f"requirement_id={self.work_order_material_requirement_id} "
            f"status={self.status}>"
        )
