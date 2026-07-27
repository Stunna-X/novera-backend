"""
Goods receipt models.

Records supplier deliveries against issued purchase orders. Posted
receipts are immutable operational documents whose accepted quantities
are linked to inventory movements and purchase-order receipt progress.
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
        InventoryMovement,
    )
    from app.models.organization import Organization
    from app.models.purchase_order import (
        PurchaseOrder,
        PurchaseOrderLineItem,
    )
    from app.models.supplier import Supplier
    from app.models.user import User


class GoodsReceipt(BaseModel):
    """One organization-scoped supplier delivery document."""

    __tablename__ = "goods_receipts"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "goods_receipt_number",
            name="uq_goods_receipts_organization_number",
        ),
        CheckConstraint(
            "status IN ('draft', 'posted', 'cancelled')",
            name="status_valid",
        ),
        Index(
            "ix_goods_receipts_organization_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_goods_receipts_organization_purchase_order",
            "organization_id",
            "purchase_order_id",
        ),
        Index(
            "ix_goods_receipts_organization_supplier",
            "organization_id",
            "supplier_id",
        ),
        Index(
            "ix_goods_receipts_organization_location",
            "organization_id",
            "receiving_location_id",
        ),
        Index(
            "ix_goods_receipts_organization_received_at",
            "organization_id",
            "received_at",
        ),
        Index(
            "ix_goods_receipts_organization_active",
            "organization_id",
            "is_active",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    goods_receipt_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    receiving_location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",
        server_default=text("'draft'"),
        index=True,
    )

    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    supplier_delivery_note: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    carrier_name: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )

    vehicle_reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    posted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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
        lazy="joined",
    )

    purchase_order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder",
        lazy="joined",
    )

    supplier: Mapped["Supplier"] = relationship(
        "Supplier",
        lazy="joined",
    )

    receiving_location: Mapped["InventoryLocation"] = relationship(
        "InventoryLocation",
        lazy="joined",
    )

    created_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by_user_id],
        lazy="joined",
    )

    posted_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[posted_by_user_id],
        lazy="joined",
    )

    cancelled_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[cancelled_by_user_id],
        lazy="joined",
    )

    line_items: Mapped[list["GoodsReceiptLineItem"]] = relationship(
        "GoodsReceiptLineItem",
        back_populates="goods_receipt",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="GoodsReceiptLineItem.position",
        lazy="selectin",
    )

    @property
    def total_accepted_quantity(self) -> Decimal:
        return sum(
            (Decimal(line.quantity_accepted) for line in self.line_items),
            start=Decimal("0.000"),
        )

    @property
    def total_rejected_quantity(self) -> Decimal:
        return sum(
            (Decimal(line.quantity_rejected) for line in self.line_items),
            start=Decimal("0.000"),
        )

    @property
    def total_damaged_quantity(self) -> Decimal:
        return sum(
            (Decimal(line.quantity_damaged) for line in self.line_items),
            start=Decimal("0.000"),
        )

    @property
    def total_delivered_quantity(self) -> Decimal:
        return (
            self.total_accepted_quantity
            + self.total_rejected_quantity
            + self.total_damaged_quantity
        )

    def __repr__(self) -> str:
        return (
            f"<GoodsReceipt id={self.id} "
            f"number={self.goods_receipt_number!r} "
            f"status={self.status!r}>"
        )


class GoodsReceiptLineItem(BaseModel):
    """One purchase-order line recorded on a goods receipt."""

    __tablename__ = "goods_receipt_line_items"

    __table_args__ = (
        UniqueConstraint(
            "goods_receipt_id",
            "purchase_order_line_item_id",
            name="uq_goods_receipt_lines_purchase_order_line",
        ),
        UniqueConstraint(
            "goods_receipt_id",
            "position",
            name="uq_goods_receipt_lines_position",
        ),
        UniqueConstraint(
            "inventory_movement_id",
            name="uq_goods_receipt_lines_inventory_movement",
        ),
        CheckConstraint(
            "quantity_accepted >= 0",
            name="accepted_non_negative",
        ),
        CheckConstraint(
            "quantity_rejected >= 0",
            name="rejected_non_negative",
        ),
        CheckConstraint(
            "quantity_damaged >= 0",
            name="damaged_non_negative",
        ),
        CheckConstraint(
            "quantity_accepted + quantity_rejected + quantity_damaged > 0",
            name="delivered_quantity_positive",
        ),
        CheckConstraint(
            "unit_cost >= 0",
            name="unit_cost_non_negative",
        ),
        CheckConstraint(
            "char_length(currency) = 3",
            name="currency_length_valid",
        ),
        CheckConstraint(
            "position >= 0",
            name="position_non_negative",
        ),
        Index(
            "ix_goods_receipt_lines_receipt_order_line",
            "goods_receipt_id",
            "purchase_order_line_item_id",
        ),
        Index(
            "ix_goods_receipt_lines_receipt_inventory_item",
            "goods_receipt_id",
            "inventory_item_id",
        ),
    )

    goods_receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("goods_receipts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    purchase_order_line_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_order_line_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    inventory_movement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_movements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    quantity_accepted: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=3),
        nullable=False,
        default=Decimal("0.000"),
        server_default=text("0"),
    )

    quantity_rejected: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=3),
        nullable=False,
        default=Decimal("0.000"),
        server_default=text("0"),
    )

    quantity_damaged: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=3),
        nullable=False,
        default=Decimal("0.000"),
        server_default=text("0"),
    )

    unit_of_measure: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="each",
        server_default=text("'each'"),
    )

    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=4),
        nullable=False,
        default=Decimal("0.0000"),
        server_default=text("0"),
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="NGN",
        server_default=text("'NGN'"),
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    damage_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    goods_receipt: Mapped["GoodsReceipt"] = relationship(
        "GoodsReceipt",
        back_populates="line_items",
    )

    purchase_order_line_item: Mapped["PurchaseOrderLineItem"] = relationship(
        "PurchaseOrderLineItem",
        lazy="joined",
    )

    inventory_item: Mapped["InventoryItem | None"] = relationship(
        "InventoryItem",
        lazy="joined",
    )

    inventory_movement: Mapped["InventoryMovement | None"] = relationship(
        "InventoryMovement",
        lazy="joined",
    )

    @property
    def total_delivered_quantity(self) -> Decimal:
        return (
            Decimal(self.quantity_accepted)
            + Decimal(self.quantity_rejected)
            + Decimal(self.quantity_damaged)
        )

    def __repr__(self) -> str:
        return (
            f"<GoodsReceiptLineItem id={self.id} "
            f"goods_receipt_id={self.goods_receipt_id} "
            f"position={self.position}>"
        )
