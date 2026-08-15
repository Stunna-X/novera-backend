"""
Work-order material requirement model.

Stores the planned inventory demand for a work order independently
from stock reservations and procurement documents.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


if TYPE_CHECKING:
    from app.models.inventory import InventoryItem
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.work_order import WorkOrder


class WorkOrderMaterialRequirement(BaseModel):
    """
    One inventory item and quantity required by a work order.

    The requirement is a planning record. Inventory reservations
    remain the source of truth for stock that has actually been
    secured for the job.
    """

    __tablename__ = "work_order_material_requirements"

    __table_args__ = (
        UniqueConstraint(
            "work_order_id",
            "inventory_item_id",
            name="uq_work_order_material_requirements_item",
        ),
        CheckConstraint(
            "required_quantity > 0",
            name="required_quantity_positive",
        ),
        CheckConstraint(
            "position >= 0",
            name="position_non_negative",
        ),
        Index(
            "ix_work_order_material_requirements_org_work_order",
            "organization_id",
            "work_order_id",
        ),
        Index(
            "ix_work_order_material_requirements_work_order_position",
            "work_order_id",
            "position",
        ),
        Index(
            "ix_work_order_material_requirements_organization_item",
            "organization_id",
            "inventory_item_id",
        ),
        Index(
            "ix_work_order_material_requirements_work_order_active",
            "work_order_id",
            "is_active",
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

    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "inventory_items.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    required_quantity: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=16,
            scale=3,
        ),
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
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

    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
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
        server_default=text("'{}'::jsonb"),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
        index=True,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        lazy="joined",
    )

    work_order: Mapped["WorkOrder"] = relationship(
        "WorkOrder",
        lazy="joined",
    )

    inventory_item: Mapped["InventoryItem"] = relationship(
        "InventoryItem",
        lazy="joined",
    )

    created_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by_user_id],
        lazy="joined",
    )

    updated_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[updated_by_user_id],
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            "<WorkOrderMaterialRequirement "
            f"id={self.id} "
            f"work_order_id={self.work_order_id} "
            f"inventory_item_id={self.inventory_item_id}>"
        )
