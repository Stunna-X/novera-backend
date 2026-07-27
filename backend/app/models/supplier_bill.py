"""
Supplier bill and three-way matching models.

Supplier bills record vendor invoices against purchase orders. Matching
snapshots compare billed quantities and prices with ordered quantities,
accepted posted goods receipts, and purchase-order commercial terms.
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
    from app.models.organization import Organization
    from app.models.purchase_order import (
        PurchaseOrder,
        PurchaseOrderLineItem,
    )
    from app.models.supplier import Supplier
    from app.models.user import User


class SupplierBill(BaseModel):
    """One organization-scoped supplier invoice."""

    __tablename__ = "supplier_bills"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "supplier_bill_number",
            name="uq_supplier_bills_organization_number",
        ),
        UniqueConstraint(
            "organization_id",
            "supplier_id",
            "supplier_invoice_number",
            name="uq_supplier_bills_supplier_invoice",
        ),
        CheckConstraint(
            """
            status IN (
                'draft',
                'submitted',
                'matched',
                'exception',
                'approved',
                'voided'
            )
            """,
            name="status_valid",
        ),
        CheckConstraint(
            "match_status IN ('not_run', 'matched', 'exception')",
            name="match_status_valid",
        ),
        CheckConstraint(
            "char_length(currency) = 3",
            name="currency_length_valid",
        ),
        CheckConstraint(
            "quantity_tolerance_percent >= 0 AND "
            "quantity_tolerance_percent <= 100",
            name="quantity_tolerance_valid",
        ),
        CheckConstraint(
            "price_tolerance_percent >= 0 AND "
            "price_tolerance_percent <= 100",
            name="price_tolerance_valid",
        ),
        CheckConstraint(
            "subtotal >= 0",
            name="subtotal_non_negative",
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
            "ix_supplier_bills_organization_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_supplier_bills_organization_match_status",
            "organization_id",
            "match_status",
        ),
        Index(
            "ix_supplier_bills_organization_supplier",
            "organization_id",
            "supplier_id",
        ),
        Index(
            "ix_supplier_bills_organization_purchase_order",
            "organization_id",
            "purchase_order_id",
        ),
        Index(
            "ix_supplier_bills_organization_invoice_date",
            "organization_id",
            "invoice_date",
        ),
        Index(
            "ix_supplier_bills_organization_due_date",
            "organization_id",
            "due_date",
        ),
        Index(
            "ix_supplier_bills_organization_active",
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

    supplier_bill_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    supplier_invoice_number: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )

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

    invoice_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",
        server_default=text("'draft'"),
        index=True,
    )

    match_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="not_run",
        server_default=text("'not_run'"),
        index=True,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="NGN",
        server_default=text("'NGN'"),
        index=True,
    )

    quantity_tolerance_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=7, scale=4),
        nullable=False,
        default=Decimal("0.0000"),
        server_default=text("0"),
    )

    price_tolerance_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=7, scale=4),
        nullable=False,
        default=Decimal("0.0000"),
        server_default=text("0"),
    )

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

    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    matched_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
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

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    matched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    voided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    approval_override_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    void_reason: Mapped[str | None] = mapped_column(
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

    supplier: Mapped["Supplier"] = relationship(
        "Supplier",
        lazy="joined",
    )

    purchase_order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder",
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

    matched_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[matched_by_user_id],
        lazy="joined",
    )

    approved_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[approved_by_user_id],
        lazy="joined",
    )

    voided_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[voided_by_user_id],
        lazy="joined",
    )

    line_items: Mapped[list["SupplierBillLineItem"]] = relationship(
        "SupplierBillLineItem",
        back_populates="supplier_bill",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SupplierBillLineItem.position",
        lazy="selectin",
    )

    match_results: Mapped[list["SupplierBillMatchResult"]] = relationship(
        "SupplierBillMatchResult",
        back_populates="supplier_bill",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SupplierBillMatchResult.created_at",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<SupplierBill id={self.id} "
            f"number={self.supplier_bill_number!r} "
            f"status={self.status!r}>"
        )


class SupplierBillLineItem(BaseModel):
    """One purchase-order line billed by a supplier."""

    __tablename__ = "supplier_bill_line_items"

    __table_args__ = (
        UniqueConstraint(
            "supplier_bill_id",
            "purchase_order_line_item_id",
            name="uq_supplier_bill_lines_purchase_order_line",
        ),
        UniqueConstraint(
            "supplier_bill_id",
            "position",
            name="uq_supplier_bill_lines_position",
        ),
        CheckConstraint(
            "quantity_billed > 0",
            name="quantity_billed_positive",
        ),
        CheckConstraint(
            "unit_price >= 0",
            name="unit_price_non_negative",
        ),
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
        CheckConstraint(
            "position >= 0",
            name="position_non_negative",
        ),
        Index(
            "ix_supplier_bill_lines_bill_order_line",
            "supplier_bill_id",
            "purchase_order_line_item_id",
        ),
    )

    supplier_bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("supplier_bills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    purchase_order_line_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_order_line_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    quantity_billed: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=3),
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

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=4),
        nullable=False,
        default=Decimal("0.0000"),
        server_default=text("0"),
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
        default=Decimal("0.00"),
        server_default=text("0"),
    )

    tax_amount: Mapped[Decimal] = mapped_column(
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

    supplier_bill: Mapped["SupplierBill"] = relationship(
        "SupplierBill",
        back_populates="line_items",
    )

    purchase_order_line_item: Mapped["PurchaseOrderLineItem"] = relationship(
        "PurchaseOrderLineItem",
        lazy="joined",
    )

    match_result: Mapped["SupplierBillMatchResult | None"] = relationship(
        "SupplierBillMatchResult",
        back_populates="supplier_bill_line_item",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="joined",
    )


class SupplierBillMatchResult(BaseModel):
    """Persisted three-way match snapshot for one supplier-bill line."""

    __tablename__ = "supplier_bill_match_results"

    __table_args__ = (
        UniqueConstraint(
            "supplier_bill_line_item_id",
            name="uq_supplier_bill_match_results_line",
        ),
        CheckConstraint(
            "status IN ('matched', 'exception')",
            name="status_valid",
        ),
        CheckConstraint(
            "quantity_ordered >= 0",
            name="quantity_ordered_non_negative",
        ),
        CheckConstraint(
            "quantity_received >= 0",
            name="quantity_received_non_negative",
        ),
        CheckConstraint(
            "quantity_billed > 0",
            name="quantity_billed_positive",
        ),
        CheckConstraint(
            "purchase_order_unit_price >= 0",
            name="purchase_order_unit_price_non_negative",
        ),
        CheckConstraint(
            "supplier_bill_unit_price >= 0",
            name="supplier_bill_unit_price_non_negative",
        ),
        Index(
            "ix_supplier_bill_match_results_bill_status",
            "supplier_bill_id",
            "status",
        ),
    )

    supplier_bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("supplier_bills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    supplier_bill_line_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("supplier_bill_line_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    purchase_order_line_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_order_line_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    quantity_ordered: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=3),
        nullable=False,
    )

    quantity_received: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=3),
        nullable=False,
    )

    quantity_billed: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=3),
        nullable=False,
    )

    purchase_order_unit_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=4),
        nullable=False,
    )

    supplier_bill_unit_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=4),
        nullable=False,
    )

    quantity_variance: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=3),
        nullable=False,
    )

    unit_price_variance: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=4),
        nullable=False,
    )

    quantity_variance_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=9, scale=4),
        nullable=False,
    )

    unit_price_variance_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=9, scale=4),
        nullable=False,
    )

    quantity_within_tolerance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    price_within_tolerance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    reasons: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    evaluated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    supplier_bill: Mapped["SupplierBill"] = relationship(
        "SupplierBill",
        back_populates="match_results",
    )

    supplier_bill_line_item: Mapped["SupplierBillLineItem"] = relationship(
        "SupplierBillLineItem",
        back_populates="match_result",
    )

    purchase_order_line_item: Mapped["PurchaseOrderLineItem"] = relationship(
        "PurchaseOrderLineItem",
        lazy="joined",
    )

    evaluated_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[evaluated_by_user_id],
        lazy="joined",
    )
