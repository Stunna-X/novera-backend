"""
Supplier payment and accounts-payable settlement models.

Payments are immutable financial records. Incorrect payments are reversed,
not deleted, so bill settlement and audit history remain reconstructable.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
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
    from app.models.supplier import Supplier
    from app.models.supplier_bill import SupplierBill
    from app.models.user import User


class SupplierPayment(BaseModel):
    """One posted or reversed payment made to a supplier."""

    __tablename__ = "supplier_payments"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "payment_number",
            name="uq_supplier_payments_organization_number",
        ),
        UniqueConstraint(
            "organization_id",
            "supplier_id",
            "reference_number",
            name="uq_supplier_payments_supplier_reference",
        ),
        CheckConstraint(
            "status IN ('posted', 'reversed')",
            name="status_valid",
        ),
        CheckConstraint(
            """
            payment_method IN (
                'bank_transfer',
                'cash',
                'card',
                'mobile_money',
                'cheque',
                'direct_debit',
                'other'
            )
            """,
            name="method_valid",
        ),
        CheckConstraint(
            "char_length(currency) = 3",
            name="currency_length_valid",
        ),
        CheckConstraint(
            "total_amount > 0",
            name="total_amount_positive",
        ),
        CheckConstraint(
            """
            (
                status = 'posted'
                AND reversed_at IS NULL
                AND reversal_reason IS NULL
            )
            OR
            (
                status = 'reversed'
                AND reversed_at IS NOT NULL
                AND reversal_reason IS NOT NULL
            )
            """,
            name="reversal_state_valid",
        ),
        Index(
            "ix_supplier_payments_organization_supplier",
            "organization_id",
            "supplier_id",
        ),
        Index(
            "ix_supplier_payments_organization_date",
            "organization_id",
            "payment_date",
        ),
        Index(
            "ix_supplier_payments_organization_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_supplier_payments_supplier_date",
            "supplier_id",
            "payment_date",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    payment_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
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
        default="bank_transfer",
        server_default=text("'bank_transfer'"),
        index=True,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="NGN",
        server_default=text("'NGN'"),
        index=True,
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2),
        nullable=False,
    )

    reference_number: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="posted",
        server_default=text("'posted'"),
        index=True,
    )

    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    reversed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
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

    organization: Mapped["Organization"] = relationship(
        "Organization",
        lazy="joined",
    )

    supplier: Mapped["Supplier"] = relationship(
        "Supplier",
        lazy="joined",
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

    allocations: Mapped[list["SupplierPaymentAllocation"]] = relationship(
        "SupplierPaymentAllocation",
        back_populates="supplier_payment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SupplierPaymentAllocation.position",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<SupplierPayment id={self.id} "
            f"number={self.payment_number!r} "
            f"status={self.status!r}>"
        )


class SupplierPaymentAllocation(BaseModel):
    """One amount allocated from a supplier payment to a supplier bill."""

    __tablename__ = "supplier_payment_allocations"

    __table_args__ = (
        UniqueConstraint(
            "supplier_payment_id",
            "supplier_bill_id",
            name="uq_supplier_payment_allocations_bill",
        ),
        UniqueConstraint(
            "supplier_payment_id",
            "position",
            name="uq_supplier_payment_allocations_position",
        ),
        CheckConstraint(
            "amount_allocated > 0",
            name="amount_positive",
        ),
        CheckConstraint(
            "position >= 0",
            name="position_non_negative",
        ),
        Index(
            "ix_supplier_payment_allocations_bill_payment",
            "supplier_bill_id",
            "supplier_payment_id",
        ),
    )

    supplier_payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("supplier_payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    supplier_bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("supplier_bills.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    amount_allocated: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2),
        nullable=False,
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

    supplier_payment: Mapped["SupplierPayment"] = relationship(
        "SupplierPayment",
        back_populates="allocations",
    )

    supplier_bill: Mapped["SupplierBill"] = relationship(
        "SupplierBill",
        lazy="joined",
    )
