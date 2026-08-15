"""
Purchase requisition models.

Stores organization-scoped purchase requests and their estimated
line items before conversion into purchase orders.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


if TYPE_CHECKING:
    from app.models.inventory import (
        InventoryItem,
        InventoryLocation,
    )
    from app.models.organization import Organization
    from app.models.supplier import Supplier
    from app.models.user import User
    from app.models.work_order import WorkOrder


class PurchaseRequisition(BaseModel):
    """One organization purchase request."""

    __tablename__ = "purchase_requisitions"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "requisition_number",
            name=(
                "uq_purchase_requisitions_organization_number"
            ),
        ),
        CheckConstraint(
            """
            status IN (
                'draft',
                'submitted',
                'approved',
                'rejected',
                'cancelled',
                'converted'
            )
            """,
            name="status_valid",
        ),
        CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name="priority_valid",
        ),
        CheckConstraint(
            "char_length(currency) = 3",
            name="currency_length_valid",
        ),
        CheckConstraint(
            "total_estimated_amount >= 0",
            name="total_non_negative",
        ),
        Index(
            "ix_purchase_requisitions_organization_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_purchase_requisitions_organization_priority",
            "organization_id",
            "priority",
        ),
        Index(
            "ix_purchase_requisitions_organization_supplier",
            "organization_id",
            "preferred_supplier_id",
        ),
        Index(
            "ix_purchase_requisitions_organization_work_order",
            "organization_id",
            "work_order_id",
        ),
        Index(
            "ix_purchase_requisitions_organization_delivery",
            "organization_id",
            "requested_delivery_date",
        ),
        Index(
            "ix_purchase_requisitions_organization_active",
            "organization_id",
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

    requisition_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",
        server_default=text("'draft'"),
        index=True,
    )

    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="normal",
        server_default=text("'normal'"),
        index=True,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="NGN",
        server_default=text("'NGN'"),
        index=True,
    )

    preferred_supplier_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "suppliers.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    work_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "work_orders.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    delivery_location_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "inventory_locations.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    requested_delivery_date: Mapped[
        date | None
    ] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    justification: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    total_estimated_amount: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=16,
            scale=2,
        ),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0"),
    )

    created_by_user_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    submitted_by_user_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    approved_by_user_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    rejected_by_user_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    cancelled_by_user_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
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
        index=True,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
    )

    preferred_supplier: Mapped[
        "Supplier | None"
    ] = relationship(
        "Supplier",
        foreign_keys=[preferred_supplier_id],
        lazy="joined",
    )

    work_order: Mapped["WorkOrder | None"] = relationship(
        "WorkOrder",
        foreign_keys=[work_order_id],
        lazy="joined",
    )

    delivery_location: Mapped[
        "InventoryLocation | None"
    ] = relationship(
        "InventoryLocation",
        foreign_keys=[delivery_location_id],
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

    line_items: Mapped[
        list["PurchaseRequisitionLineItem"]
    ] = relationship(
        "PurchaseRequisitionLineItem",
        back_populates="requisition",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PurchaseRequisitionLineItem.position",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<PurchaseRequisition id={self.id} "
            f"number={self.requisition_number!r} "
            f"status={self.status!r}>"
        )


class PurchaseRequisitionLineItem(BaseModel):
    """One estimated purchase requisition line."""

    __tablename__ = "purchase_requisition_line_items"

    __table_args__ = (
        UniqueConstraint(
            "requisition_id",
            "position",
            name=(
                "uq_purchase_requisition_lines_position"
            ),
        ),
        CheckConstraint(
            "quantity > 0",
            name="quantity_positive",
        ),
        CheckConstraint(
            "estimated_unit_cost >= 0",
            name="unit_cost_non_negative",
        ),
        CheckConstraint(
            "line_total >= 0",
            name="line_total_non_negative",
        ),
        CheckConstraint(
            "position >= 0",
            name="position_non_negative",
        ),
        Index(
            "ix_purchase_requisition_lines_requisition_item",
            "requisition_id",
            "inventory_item_id",
        ),
        Index(
            "ix_purchase_requisition_lines_requisition_supplier",
            "requisition_id",
            "preferred_supplier_id",
        ),
    )

    requisition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "purchase_requisitions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    inventory_item_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "inventory_items.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    preferred_supplier_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "suppliers.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=16,
            scale=3,
        ),
        nullable=False,
        default=Decimal("1.000"),
        server_default=text("1.000"),
    )

    unit_of_measure: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="each",
        server_default=text("'each'"),
    )

    estimated_unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=4,
        ),
        nullable=False,
        default=Decimal("0.0000"),
        server_default=text("0"),
    )

    line_total: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=16,
            scale=2,
        ),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0"),
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    requisition: Mapped["PurchaseRequisition"] = relationship(
        "PurchaseRequisition",
        back_populates="line_items",
    )

    inventory_item: Mapped[
        "InventoryItem | None"
    ] = relationship(
        "InventoryItem",
        foreign_keys=[inventory_item_id],
        lazy="joined",
    )

    preferred_supplier: Mapped[
        "Supplier | None"
    ] = relationship(
        "Supplier",
        foreign_keys=[preferred_supplier_id],
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<PurchaseRequisitionLineItem id={self.id} "
            f"requisition_id={self.requisition_id} "
            f"position={self.position}>"
        )
