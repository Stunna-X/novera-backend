"""
Invoice models.

Stores organization-scoped work-order invoices, invoice line
items, and customer payment records.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import BaseModel
from app.enums.invoice import (
    InvoiceLineSource,
    InvoicePaymentMethod,
    InvoiceStatus,
)


if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.work_order import WorkOrder
    from app.models.work_order_expense import WorkOrderExpense


class Invoice(BaseModel):
    """
    One customer invoice generated from a work order.

    Each invoice belongs to exactly one currency. Expenses
    denominated in different currencies must be placed on
    separate invoices.
    """

    __tablename__ = "invoices"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "invoice_number",
            name="uq_invoices_organization_number",
        ),
        CheckConstraint(
            """
            status IN (
                'draft',
                'issued',
                'partially_paid',
                'paid',
                'void'
            )
            """,
            name="ck_invoices_status_valid",
        ),
        CheckConstraint(
            "char_length(currency) = 3",
            name="ck_invoices_currency_length",
        ),
        CheckConstraint(
            "subtotal >= 0",
            name="ck_invoices_subtotal_non_negative",
        ),
        CheckConstraint(
            "discount_amount >= 0",
            name="ck_invoices_discount_non_negative",
        ),
        CheckConstraint(
            "tax_amount >= 0",
            name="ck_invoices_tax_non_negative",
        ),
        CheckConstraint(
            "total_amount >= 0",
            name="ck_invoices_total_non_negative",
        ),
        CheckConstraint(
            "amount_paid >= 0",
            name="ck_invoices_paid_non_negative",
        ),
        CheckConstraint(
            "balance_due >= 0",
            name="ck_invoices_balance_non_negative",
        ),
        CheckConstraint(
            """
            due_date IS NULL
            OR due_date >= invoice_date
            """,
            name="ck_invoices_due_date_valid",
        ),
        Index(
            "ix_invoices_organization_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_invoices_organization_customer",
            "organization_id",
            "customer_id",
        ),
        Index(
            "ix_invoices_organization_work_order",
            "organization_id",
            "work_order_id",
        ),
        Index(
            "ix_invoices_organization_currency",
            "organization_id",
            "currency",
        ),
        Index(
            "ix_invoices_organization_due_date",
            "organization_id",
            "due_date",
        ),
        Index(
            "ix_invoices_organization_active",
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

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "customers.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "work_orders.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
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

    voided_by_user_id: Mapped[
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

    invoice_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="NGN",
        server_default="NGN",
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=InvoiceStatus.DRAFT.value,
        server_default=InvoiceStatus.DRAFT.value,
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

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    balance_due: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    customer_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    customer_email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )

    customer_phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    billing_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    terms: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    voided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    void_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        lazy="joined",
    )

    customer: Mapped["Customer"] = relationship(
        "Customer",
        lazy="joined",
    )

    work_order: Mapped["WorkOrder"] = relationship(
        "WorkOrder",
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

    voided_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[voided_by_user_id],
        lazy="joined",
    )

    line_items: Mapped[
        list["InvoiceLineItem"]
    ] = relationship(
        "InvoiceLineItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by=(
            "InvoiceLineItem.position, "
            "InvoiceLineItem.created_at"
        ),
    )

    payments: Mapped[
        list["InvoicePayment"]
    ] = relationship(
        "InvoicePayment",
        back_populates="invoice",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by=(
            "InvoicePayment.payment_date, "
            "InvoicePayment.created_at"
        ),
    )

    def __repr__(self) -> str:
        """
        Return a developer-friendly representation.
        """

        return (
            f"<Invoice "
            f"id={self.id} "
            f"number={self.invoice_number!r} "
            f"currency={self.currency!r} "
            f"status={self.status!r} "
            f"total={self.total_amount}>"
        )


class InvoiceLineItem(BaseModel):
    """
    One charge displayed on an invoice.

    A line may be created manually or generated from an
    approved billable work-order expense.
    """

    __tablename__ = "invoice_line_items"

    __table_args__ = (
        UniqueConstraint(
            "invoice_id",
            "position",
            name="uq_invoice_line_items_invoice_position",
        ),
        UniqueConstraint(
            "invoice_id",
            "work_order_expense_id",
            name="uq_invoice_line_items_invoice_expense",
        ),
        CheckConstraint(
            """
            source_type IN (
                'manual',
                'expense'
            )
            """,
            name="ck_invoice_line_items_source_valid",
        ),
        CheckConstraint(
            "quantity > 0",
            name="ck_invoice_line_items_quantity_positive",
        ),
        CheckConstraint(
            "unit_price >= 0",
            name="ck_invoice_line_items_unit_price_non_negative",
        ),
        CheckConstraint(
            "line_total >= 0",
            name="ck_invoice_line_items_total_non_negative",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_invoice_line_items_position_non_negative",
        ),
        CheckConstraint(
            """
            (
                source_type = 'manual'
                AND work_order_expense_id IS NULL
            )
            OR
            (
                source_type = 'expense'
                AND work_order_expense_id IS NOT NULL
            )
            """,
            name="ck_invoice_line_items_source_expense_match",
        ),
        Index(
            "ix_invoice_line_items_invoice_active",
            "invoice_id",
            "is_active",
        ),
        Index(
            "ix_invoice_line_items_expense",
            "work_order_expense_id",
        ),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "invoices.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    work_order_expense_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "work_order_expenses.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=InvoiceLineSource.MANUAL.value,
        server_default=InvoiceLineSource.MANUAL.value,
        index=True,
    )

    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=3,
        ),
        nullable=False,
        default=Decimal("1.000"),
        server_default="1.000",
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=False,
    )

    line_total: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    invoice: Mapped["Invoice"] = relationship(
        "Invoice",
        back_populates="line_items",
    )

    work_order_expense: Mapped[
        "WorkOrderExpense | None"
    ] = relationship(
        "WorkOrderExpense",
        lazy="joined",
    )

    def __repr__(self) -> str:
        """
        Return a developer-friendly representation.
        """

        return (
            f"<InvoiceLineItem "
            f"id={self.id} "
            f"invoice_id={self.invoice_id} "
            f"source_type={self.source_type!r} "
            f"total={self.line_total}>"
        )


class InvoicePayment(BaseModel):
    """
    One payment recorded against an issued invoice.

    Payments are not physically deleted. An incorrect payment
    is reversed so that the financial audit trail is retained.
    """

    __tablename__ = "invoice_payments"

    __table_args__ = (
        CheckConstraint(
            """
            payment_method IN (
                'cash',
                'bank_transfer',
                'card',
                'mobile_money',
                'cheque',
                'other'
            )
            """,
            name="ck_invoice_payments_method_valid",
        ),
        CheckConstraint(
            "amount > 0",
            name="ck_invoice_payments_amount_positive",
        ),
        CheckConstraint(
            "char_length(currency) = 3",
            name="ck_invoice_payments_currency_length",
        ),
        Index(
            "ix_invoice_payments_invoice_date",
            "invoice_id",
            "payment_date",
        ),
        Index(
            "ix_invoice_payments_invoice_reversed",
            "invoice_id",
            "is_reversed",
        ),
        Index(
            "ix_invoice_payments_reference",
            "reference_number",
        ),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "invoices.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    recorded_by_user_id: Mapped[
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

    reversed_by_user_id: Mapped[
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

    amount: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        index=True,
    )

    payment_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    payment_method: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=InvoicePaymentMethod.BANK_TRANSFER.value,
        server_default=(
            InvoicePaymentMethod.BANK_TRANSFER.value
        ),
        index=True,
    )

    reference_number: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_reversed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )

    reversed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    reversal_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    invoice: Mapped["Invoice"] = relationship(
        "Invoice",
        back_populates="payments",
    )

    recorded_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[recorded_by_user_id],
        lazy="joined",
    )

    reversed_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[reversed_by_user_id],
        lazy="joined",
    )

    def __repr__(self) -> str:
        """
        Return a developer-friendly representation.
        """

        return (
            f"<InvoicePayment "
            f"id={self.id} "
            f"invoice_id={self.invoice_id} "
            f"amount={self.amount} "
            f"currency={self.currency!r} "
            f"is_reversed={self.is_reversed}>"
        )