"""
Supplier returns, debit notes, and supplier-credit settlement models.

Accepted inventory returns create immutable outbound stock movements. Rejected
or damaged receipt quantities remain logistics-only returns because they were
never added to on-hand inventory. Acknowledged debit-note credits settle
approved supplier bills through the existing supplier-payment allocation
ledger.
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
    from app.models.goods_receipt import GoodsReceipt, GoodsReceiptLineItem
    from app.models.inventory import (
        InventoryItem,
        InventoryLocation,
        InventoryMovement,
    )
    from app.models.organization import Organization
    from app.models.purchase_order import PurchaseOrder
    from app.models.supplier import Supplier
    from app.models.supplier_bill import SupplierBillLineItem
    from app.models.supplier_payment import SupplierPayment
    from app.models.user import User


class SupplierReturn(BaseModel):
    """One organization-scoped shipment returned to a supplier."""

    __tablename__ = "supplier_returns"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "return_number",
            name="uq_supplier_returns_organization_number",
        ),
        CheckConstraint(
            "status IN ('draft', 'dispatched', 'completed', 'cancelled')",
            name="status_valid",
        ),
        CheckConstraint(
            """
            reason_code IN (
                'damaged',
                'defective',
                'wrong_item',
                'over_delivery',
                'quality_failure',
                'other'
            )
            """,
            name="reason_code_valid",
        ),
        CheckConstraint(
            """
            (
                status = 'draft'
                AND dispatched_at IS NULL
                AND completed_at IS NULL
                AND cancelled_at IS NULL
            )
            OR
            (
                status = 'dispatched'
                AND dispatched_at IS NOT NULL
                AND completed_at IS NULL
                AND cancelled_at IS NULL
            )
            OR
            (
                status = 'completed'
                AND dispatched_at IS NOT NULL
                AND completed_at IS NOT NULL
                AND cancelled_at IS NULL
            )
            OR
            (
                status = 'cancelled'
                AND cancelled_at IS NOT NULL
                AND cancellation_reason IS NOT NULL
                AND dispatched_at IS NULL
                AND completed_at IS NULL
            )
            """,
            name="lifecycle_state_valid",
        ),
        Index(
            "ix_supplier_returns_organization_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_supplier_returns_organization_supplier",
            "organization_id",
            "supplier_id",
        ),
        Index(
            "ix_supplier_returns_organization_receipt",
            "organization_id",
            "goods_receipt_id",
        ),
        Index(
            "ix_supplier_returns_organization_date",
            "organization_id",
            "return_date",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    return_number: Mapped[str] = mapped_column(String(50), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    goods_receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("goods_receipts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    return_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        server_default=text("'draft'"),
        index=True,
    )
    supplier_reference: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )
    carrier_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    dispatched_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    completed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
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
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    supplier: Mapped["Supplier"] = relationship("Supplier", lazy="joined")
    purchase_order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder",
        lazy="joined",
    )
    goods_receipt: Mapped["GoodsReceipt"] = relationship(
        "GoodsReceipt",
        lazy="joined",
    )
    source_location: Mapped["InventoryLocation"] = relationship(
        "InventoryLocation",
        lazy="joined",
    )
    created_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by_user_id],
        lazy="joined",
    )
    dispatched_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[dispatched_by_user_id],
        lazy="joined",
    )
    completed_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[completed_by_user_id],
        lazy="joined",
    )
    cancelled_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[cancelled_by_user_id],
        lazy="joined",
    )
    line_items: Mapped[list["SupplierReturnLineItem"]] = relationship(
        "SupplierReturnLineItem",
        back_populates="supplier_return",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SupplierReturnLineItem.position",
        lazy="selectin",
    )


class SupplierReturnLineItem(BaseModel):
    """One receipt quantity returned to a supplier."""

    __tablename__ = "supplier_return_line_items"

    __table_args__ = (
        UniqueConstraint(
            "supplier_return_id",
            "goods_receipt_line_item_id",
            "quantity_source",
            name="uq_supplier_return_lines_receipt_source",
        ),
        UniqueConstraint(
            "supplier_return_id",
            "position",
            name="uq_supplier_return_lines_position",
        ),
        UniqueConstraint(
            "inventory_movement_id",
            name="uq_supplier_return_lines_inventory_movement",
        ),
        CheckConstraint(
            "quantity_source IN ('accepted', 'rejected', 'damaged')",
            name="quantity_source_valid",
        ),
        CheckConstraint(
            "quantity_returned > 0",
            name="quantity_returned_positive",
        ),
        CheckConstraint("unit_cost >= 0", name="unit_cost_non_negative"),
        CheckConstraint(
            "char_length(currency) = 3",
            name="currency_length_valid",
        ),
        CheckConstraint("position >= 0", name="position_non_negative"),
        CheckConstraint(
            """
            (
                quantity_source = 'accepted'
                AND inventory_item_id IS NOT NULL
            )
            OR quantity_source IN ('rejected', 'damaged')
            """,
            name="accepted_inventory_item_required",
        ),
        Index(
            "ix_supplier_return_lines_receipt_source",
            "goods_receipt_line_item_id",
            "quantity_source",
        ),
    )

    supplier_return_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("supplier_returns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goods_receipt_line_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("goods_receipt_line_items.id", ondelete="RESTRICT"),
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
    quantity_source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity_returned: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=3),
        nullable=False,
    )
    unit_of_measure: Mapped[str] = mapped_column(String(40), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=4),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
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

    supplier_return: Mapped["SupplierReturn"] = relationship(
        "SupplierReturn",
        back_populates="line_items",
    )
    goods_receipt_line_item: Mapped["GoodsReceiptLineItem"] = relationship(
        "GoodsReceiptLineItem",
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


class SupplierDebitNote(BaseModel):
    """Buyer-issued debit note that becomes supplier credit when acknowledged."""

    __tablename__ = "supplier_debit_notes"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "debit_note_number",
            name="uq_supplier_debit_notes_organization_number",
        ),
        UniqueConstraint(
            "organization_id",
            "supplier_id",
            "supplier_credit_reference",
            name="uq_supplier_debit_notes_supplier_credit_reference",
        ),
        CheckConstraint(
            "status IN ('draft', 'issued', 'acknowledged', 'voided')",
            name="status_valid",
        ),
        CheckConstraint(
            "char_length(currency) = 3",
            name="currency_length_valid",
        ),
        CheckConstraint("subtotal >= 0", name="subtotal_non_negative"),
        CheckConstraint("tax_total >= 0", name="tax_total_non_negative"),
        CheckConstraint("total_amount >= 0", name="total_amount_non_negative"),
        CheckConstraint(
            """
            (
                status = 'draft'
                AND issued_at IS NULL
                AND acknowledged_at IS NULL
                AND voided_at IS NULL
            )
            OR
            (
                status = 'issued'
                AND issued_at IS NOT NULL
                AND acknowledged_at IS NULL
                AND voided_at IS NULL
            )
            OR
            (
                status = 'acknowledged'
                AND issued_at IS NOT NULL
                AND acknowledged_at IS NOT NULL
                AND supplier_credit_reference IS NOT NULL
                AND voided_at IS NULL
            )
            OR
            (
                status = 'voided'
                AND voided_at IS NOT NULL
                AND void_reason IS NOT NULL
            )
            """,
            name="lifecycle_state_valid",
        ),
        Index(
            "ix_supplier_debit_notes_organization_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_supplier_debit_notes_organization_supplier",
            "organization_id",
            "supplier_id",
        ),
        Index(
            "ix_supplier_debit_notes_organization_return",
            "organization_id",
            "supplier_return_id",
        ),
        Index(
            "ix_supplier_debit_notes_organization_date",
            "organization_id",
            "note_date",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    debit_note_number: Mapped[str] = mapped_column(String(50), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    supplier_return_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("supplier_returns.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    note_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20),
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
    supplier_credit_reference: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(
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
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    issued_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    acknowledged_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    voided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    voided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        lazy="joined",
    )
    supplier: Mapped["Supplier"] = relationship("Supplier", lazy="joined")
    supplier_return: Mapped["SupplierReturn | None"] = relationship(
        "SupplierReturn",
        lazy="joined",
    )
    purchase_order: Mapped["PurchaseOrder | None"] = relationship(
        "PurchaseOrder",
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
    acknowledged_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[acknowledged_by_user_id],
        lazy="joined",
    )
    voided_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[voided_by_user_id],
        lazy="joined",
    )
    line_items: Mapped[list["SupplierDebitNoteLineItem"]] = relationship(
        "SupplierDebitNoteLineItem",
        back_populates="supplier_debit_note",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SupplierDebitNoteLineItem.position",
        lazy="selectin",
    )
    settlements: Mapped[list["SupplierCreditSettlement"]] = relationship(
        "SupplierCreditSettlement",
        back_populates="supplier_debit_note",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SupplierCreditSettlement.position",
        lazy="selectin",
    )


class SupplierDebitNoteLineItem(BaseModel):
    """One commercial value line on a supplier debit note."""

    __tablename__ = "supplier_debit_note_line_items"

    __table_args__ = (
        UniqueConstraint(
            "supplier_debit_note_id",
            "position",
            name="uq_supplier_debit_note_lines_position",
        ),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        CheckConstraint(
            "tax_rate >= 0 AND tax_rate <= 100",
            name="tax_rate_valid",
        ),
        CheckConstraint(
            "line_subtotal >= 0",
            name="line_subtotal_non_negative",
        ),
        CheckConstraint(
            "tax_amount >= 0",
            name="tax_amount_non_negative",
        ),
        CheckConstraint(
            "line_total >= 0",
            name="line_total_non_negative",
        ),
        CheckConstraint("position >= 0", name="position_non_negative"),
    )

    supplier_debit_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("supplier_debit_notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supplier_return_line_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("supplier_return_line_items.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    supplier_bill_line_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("supplier_bill_line_items.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=3),
        nullable=False,
    )
    unit_of_measure: Mapped[str] = mapped_column(String(40), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=4),
        nullable=False,
    )
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(precision=7, scale=4),
        nullable=False,
        default=Decimal("0.0000"),
        server_default=text("0"),
    )
    line_subtotal: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2),
        nullable=False,
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2),
        nullable=False,
    )
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2),
        nullable=False,
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

    supplier_debit_note: Mapped["SupplierDebitNote"] = relationship(
        "SupplierDebitNote",
        back_populates="line_items",
    )
    supplier_return_line_item: Mapped[
        "SupplierReturnLineItem | None"
    ] = relationship(
        "SupplierReturnLineItem",
        lazy="joined",
    )
    supplier_bill_line_item: Mapped[
        "SupplierBillLineItem | None"
    ] = relationship(
        "SupplierBillLineItem",
        lazy="joined",
    )


class SupplierCreditSettlement(BaseModel):
    """
    Link one debit-note credit application to a supplier-payment record.

    The linked payment allocations are the source of truth for payable
    balances. Reversing that payment restores both bill balance and available
    debit-note credit.
    """

    __tablename__ = "supplier_credit_settlements"

    __table_args__ = (
        UniqueConstraint(
            "supplier_payment_id",
            name="uq_supplier_credit_settlements_payment",
        ),
        UniqueConstraint(
            "supplier_debit_note_id",
            "position",
            name="uq_supplier_credit_settlements_position",
        ),
        CheckConstraint(
            "amount_settled > 0",
            name="amount_settled_positive",
        ),
        CheckConstraint("position >= 0", name="position_non_negative"),
        Index(
            "ix_supplier_credit_settlements_organization_note",
            "organization_id",
            "supplier_debit_note_id",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supplier_debit_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("supplier_debit_notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supplier_payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("supplier_payments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount_settled: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        lazy="joined",
    )
    supplier_debit_note: Mapped["SupplierDebitNote"] = relationship(
        "SupplierDebitNote",
        back_populates="settlements",
    )
    supplier_payment: Mapped["SupplierPayment"] = relationship(
        "SupplierPayment",
        lazy="joined",
    )
    created_by: Mapped["User | None"] = relationship(
        "User",
        lazy="joined",
    )
