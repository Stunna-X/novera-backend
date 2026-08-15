"""
Purchase order models.

Stores organization-scoped supplier orders, commercial totals,
receipt progress, and the source purchase requisition when present.
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
    from app.models.purchase_requisition import (
        PurchaseRequisition,
        PurchaseRequisitionLineItem,
    )
    from app.models.supplier import Supplier
    from app.models.user import User


class PurchaseOrder(BaseModel):
    """One organization purchase order."""

    __tablename__ = "purchase_orders"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "purchase_order_number",
            name="uq_purchase_orders_organization_number",
        ),
        UniqueConstraint(
            "organization_id",
            "source_requisition_id",
            name="uq_purchase_orders_organization_requisition",
        ),
        CheckConstraint(
            """
            status IN (
                'draft',
                'issued',
                'acknowledged',
                'partially_received',
                'received',
                'cancelled',
                'closed'
            )
            """,
            name="status_valid",
        ),
        CheckConstraint(
            "char_length(currency) = 3",
            name="currency_length_valid",
        ),
        CheckConstraint(
            "payment_terms_days >= 0 AND payment_terms_days <= 3650",
            name="payment_terms_days_valid",
        ),
        CheckConstraint(
            "subtotal >= 0",
            name="subtotal_non_negative",
        ),
        CheckConstraint(
            "discount_total >= 0",
            name="discount_total_non_negative",
        ),
        CheckConstraint(
            "tax_total >= 0",
            name="tax_total_non_negative",
        ),
        CheckConstraint(
            "total_amount >= 0",
            name="total_amount_non_negative",
        ),
        Index(
            "ix_purchase_orders_organization_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_purchase_orders_organization_supplier",
            "organization_id",
            "supplier_id",
        ),
        Index(
            "ix_purchase_orders_organization_expected_delivery",
            "organization_id",
            "expected_delivery_date",
        ),
        Index(
            "ix_purchase_orders_organization_source_requisition",
            "organization_id",
            "source_requisition_id",
        ),
        Index(
            "ix_purchase_orders_organization_active",
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

    purchase_order_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    source_requisition_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "purchase_requisitions.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "suppliers.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",
        server_default=text("'draft'"),
        index=True,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="NGN",
        server_default=text("'NGN'"),
        index=True,
    )

    issue_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    expected_delivery_date: Mapped[
        date | None
    ] = mapped_column(
        Date,
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

    delivery_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    payment_terms_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    supplier_reference: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    supplier_name: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
    )

    supplier_email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )

    supplier_phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    supplier_tax_id: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0"),
    )

    discount_total: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0"),
    )

    tax_total: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0"),
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0"),
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    terms_and_conditions: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
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

    issued_by_user_id: Mapped[
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

    acknowledged_by_user_id: Mapped[
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

    closed_by_user_id: Mapped[
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

    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    acknowledged_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancellation_reason: Mapped[
        str | None
    ] = mapped_column(
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

    source_requisition: Mapped[
        "PurchaseRequisition | None"
    ] = relationship(
        "PurchaseRequisition",
        foreign_keys=[source_requisition_id],
        lazy="joined",
    )

    supplier: Mapped["Supplier"] = relationship(
        "Supplier",
        foreign_keys=[supplier_id],
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

    issued_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[issued_by_user_id],
        lazy="joined",
    )

    acknowledged_by: Mapped[
        "User | None"
    ] = relationship(
        "User",
        foreign_keys=[acknowledged_by_user_id],
        lazy="joined",
    )

    cancelled_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[cancelled_by_user_id],
        lazy="joined",
    )

    closed_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[closed_by_user_id],
        lazy="joined",
    )

    line_items: Mapped[
        list["PurchaseOrderLineItem"]
    ] = relationship(
        "PurchaseOrderLineItem",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PurchaseOrderLineItem.position",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<PurchaseOrder id={self.id} "
            f"number={self.purchase_order_number!r} "
            f"status={self.status!r}>"
        )


class PurchaseOrderLineItem(BaseModel):
    """One commercial purchase order line."""

    __tablename__ = "purchase_order_line_items"

    __table_args__ = (
        UniqueConstraint(
            "purchase_order_id",
            "position",
            name="uq_purchase_order_lines_position",
        ),
        UniqueConstraint(
            "purchase_order_id",
            "source_requisition_line_id",
            name="uq_purchase_order_lines_requisition_line",
        ),
        CheckConstraint(
            "quantity_ordered > 0",
            name="quantity_ordered_positive",
        ),
        CheckConstraint(
            "quantity_received >= 0",
            name="quantity_received_non_negative",
        ),
        CheckConstraint(
            "quantity_received <= quantity_ordered",
            name="quantity_received_within_ordered",
        ),
        CheckConstraint(
            "unit_price >= 0",
            name="unit_price_non_negative",
        ),
        CheckConstraint(
            "discount_amount >= 0",
            name="discount_amount_non_negative",
        ),
        CheckConstraint(
            "tax_rate >= 0 AND tax_rate <= 100",
            name="tax_rate_valid",
        ),
        CheckConstraint(
            "tax_amount >= 0",
            name="tax_amount_non_negative",
        ),
        CheckConstraint(
            "line_subtotal >= 0",
            name="line_subtotal_non_negative",
        ),
        CheckConstraint(
            "line_total >= 0",
            name="line_total_non_negative",
        ),
        CheckConstraint(
            "discount_amount <= line_subtotal",
            name="discount_within_subtotal",
        ),
        CheckConstraint(
            "position >= 0",
            name="position_non_negative",
        ),
        Index(
            "ix_purchase_order_lines_order_item",
            "purchase_order_id",
            "inventory_item_id",
        ),
        Index(
            "ix_purchase_order_lines_order_receipt_progress",
            "purchase_order_id",
            "quantity_received",
        ),
    )

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "purchase_orders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    source_requisition_line_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "purchase_requisition_line_items.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
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

    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    quantity_ordered: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=3),
        nullable=False,
        default=Decimal("1.000"),
        server_default=text("1.000"),
    )

    quantity_received: Mapped[Decimal] = mapped_column(
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

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=4),
        nullable=False,
        default=Decimal("0.0000"),
        server_default=text("0"),
    )

    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0"),
    )

    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(precision=7, scale=4),
        nullable=False,
        default=Decimal("0.0000"),
        server_default=text("0"),
    )

    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0"),
    )

    line_subtotal: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0"),
    )

    line_total: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2),
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

    purchase_order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder",
        back_populates="line_items",
    )

    source_requisition_line: Mapped[
        "PurchaseRequisitionLineItem | None"
    ] = relationship(
        "PurchaseRequisitionLineItem",
        foreign_keys=[source_requisition_line_id],
        lazy="joined",
    )

    inventory_item: Mapped[
        "InventoryItem | None"
    ] = relationship(
        "InventoryItem",
        foreign_keys=[inventory_item_id],
        lazy="joined",
    )

    @property
    def outstanding_quantity(self) -> Decimal:
        """Return quantity not yet received."""

        return self.quantity_ordered - self.quantity_received

    @property
    def is_fully_received(self) -> bool:
        """Return whether the ordered quantity is fully received."""

        return self.quantity_received >= self.quantity_ordered

    def __repr__(self) -> str:
        return (
            f"<PurchaseOrderLineItem id={self.id} "
            f"purchase_order_id={self.purchase_order_id} "
            f"position={self.position}>"
        )
