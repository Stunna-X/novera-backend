"""Pydantic schemas for supplier payments and payable balances."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class SupplierPaymentMethod(StrEnum):
    """Supported supplier-payment methods."""

    BANK_TRANSFER = "bank_transfer"
    CASH = "cash"
    CARD = "card"
    MOBILE_MONEY = "mobile_money"
    CHEQUE = "cheque"
    DIRECT_DEBIT = "direct_debit"
    OTHER = "other"


class SupplierPaymentStatus(StrEnum):
    """Lifecycle states for immutable supplier payments."""

    POSTED = "posted"
    REVERSED = "reversed"


class SupplierBillSettlementStatus(StrEnum):
    """Computed accounts-payable settlement states."""

    UNPAID = "unpaid"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"


class SupplierPaymentAllocationCreate(BaseModel):
    """Allocate part of a payment to one approved supplier bill."""

    supplier_bill_id: uuid.UUID
    amount_allocated: Decimal = Field(
        gt=0,
        max_digits=16,
        decimal_places=2,
    )
    notes: str | None = Field(
        default=None,
        max_length=5000,
    )
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class SupplierPaymentCreate(BaseModel):
    """Post one supplier payment and its bill allocations."""

    payment_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    supplier_id: uuid.UUID
    payment_date: date = Field(default_factory=date.today)
    payment_method: SupplierPaymentMethod = Field(
        default=SupplierPaymentMethod.BANK_TRANSFER
    )
    currency: str = Field(default="NGN", min_length=3, max_length=3)
    total_amount: Decimal = Field(
        gt=0,
        max_digits=16,
        decimal_places=2,
    )
    reference_number: str | None = Field(
        default=None,
        max_length=150,
    )
    notes: str | None = Field(
        default=None,
        max_length=5000,
    )
    details: dict[str, Any] = Field(default_factory=dict)
    allocations: list[SupplierPaymentAllocationCreate] = Field(
        min_length=1,
        max_length=200,
    )

    @field_validator(
        "payment_number",
        "reference_number",
        "notes",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_allocations(self) -> Self:
        bill_ids = [
            allocation.supplier_bill_id
            for allocation in self.allocations
        ]
        if len(bill_ids) != len(set(bill_ids)):
            raise ValueError(
                "Each supplier bill may be allocated only once per payment."
            )

        allocated_total = sum(
            (
                allocation.amount_allocated
                for allocation in self.allocations
            ),
            Decimal("0.00"),
        )

        if allocated_total != self.total_amount:
            raise ValueError(
                "Allocation amounts must equal the payment total."
            )

        return self


class SupplierPaymentReverse(BaseModel):
    """Required explanation for reversing a supplier payment."""

    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError(
                "Reversal reason must contain at least three characters."
            )
        return normalized


class SupplierPaymentAllocationResponse(BaseModel):
    """One persisted bill allocation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    supplier_payment_id: uuid.UUID
    supplier_bill_id: uuid.UUID
    amount_allocated: Decimal
    position: int
    notes: str | None
    details: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SupplierPaymentResponse(BaseModel):
    """Complete supplier-payment response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    payment_number: str
    supplier_id: uuid.UUID
    payment_date: date
    payment_method: SupplierPaymentMethod
    currency: str
    total_amount: Decimal
    reference_number: str | None
    status: SupplierPaymentStatus
    recorded_by_user_id: uuid.UUID | None
    reversed_by_user_id: uuid.UUID | None
    reversed_at: datetime | None
    reversal_reason: str | None
    notes: str | None
    details: dict[str, Any]
    allocations: list[SupplierPaymentAllocationResponse]
    created_at: datetime
    updated_at: datetime


class SupplierPaymentListResponse(BaseModel):
    """Paginated supplier-payment collection."""

    items: list[SupplierPaymentResponse]
    total: int
    skip: int
    limit: int


class SupplierPayableBillResponse(BaseModel):
    """Computed settlement state for one approved supplier bill."""

    supplier_bill_id: uuid.UUID
    supplier_bill_number: str
    supplier_invoice_number: str
    supplier_id: uuid.UUID
    supplier_name: str
    invoice_date: date
    due_date: date | None
    currency: str
    total_amount: Decimal
    amount_paid: Decimal
    balance_due: Decimal
    settlement_status: SupplierBillSettlementStatus
    is_overdue: bool


class SupplierPayableListResponse(BaseModel):
    """Paginated approved-bill balance collection."""

    items: list[SupplierPayableBillResponse]
    total: int
    skip: int
    limit: int
