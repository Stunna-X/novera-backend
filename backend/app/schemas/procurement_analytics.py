"""Response schemas for procurement reporting and spend analytics."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class ProcurementSettlementStatus(StrEnum):
    """Computed supplier-bill settlement states."""

    UNPAID = "unpaid"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"


class ProcurementCurrencyAmount(BaseModel):
    """One non-negative amount grouped by ISO currency code."""

    currency: str = Field(min_length=3, max_length=3)
    amount: Decimal = Field(ge=0)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class ProcurementOverviewResponse(BaseModel):
    """High-level procurement and accounts-payable summary."""

    organization_id: uuid.UUID
    generated_at: datetime
    as_of_date: date
    open_requisitions: int = Field(ge=0)
    active_purchase_orders: int = Field(ge=0)
    posted_goods_receipts: int = Field(ge=0)
    bills_awaiting_approval: int = Field(ge=0)
    match_exception_count: int = Field(ge=0)
    overdue_bill_count: int = Field(ge=0)
    open_commitments: list[ProcurementCurrencyAmount]
    outstanding_payables: list[ProcurementCurrencyAmount]
    payments_in_period: list[ProcurementCurrencyAmount]


class ProcurementDateRangeResponse(BaseModel):
    """Shared organization and reporting-range metadata."""

    organization_id: uuid.UUID
    generated_at: datetime
    date_from: date
    date_to: date

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to.")
        return self


class SupplierSpendItem(BaseModel):
    """Spend, payments, and payable balance for one supplier/currency."""

    supplier_id: uuid.UUID
    supplier_code: str
    supplier_name: str
    currency: str = Field(min_length=3, max_length=3)
    bill_count: int = Field(ge=0)
    payment_count: int = Field(ge=0)
    billed_amount: Decimal = Field(ge=0)
    paid_amount: Decimal = Field(ge=0)
    outstanding_amount: Decimal = Field(ge=0)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class SupplierSpendResponse(ProcurementDateRangeResponse):
    """Supplier spend grouped by supplier and currency."""

    items: list[SupplierSpendItem]


class PurchaseOrderCommitmentItem(BaseModel):
    """Open financial commitment for one purchase order."""

    purchase_order_id: uuid.UUID
    purchase_order_number: str
    supplier_id: uuid.UUID
    supplier_name: str
    status: str
    issue_date: date | None
    expected_delivery_date: date | None
    currency: str = Field(min_length=3, max_length=3)
    ordered_amount: Decimal = Field(ge=0)
    billed_amount: Decimal = Field(ge=0)
    open_commitment: Decimal = Field(ge=0)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class PurchaseOrderCommitmentResponse(BaseModel):
    """Open purchase-order commitments."""

    organization_id: uuid.UUID
    generated_at: datetime
    items: list[PurchaseOrderCommitmentItem]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)


class AccountsPayableItem(BaseModel):
    """Computed settlement state for one approved supplier bill."""

    supplier_bill_id: uuid.UUID
    supplier_bill_number: str
    supplier_invoice_number: str
    supplier_id: uuid.UUID
    supplier_name: str
    purchase_order_id: uuid.UUID
    invoice_date: date
    due_date: date | None
    currency: str = Field(min_length=3, max_length=3)
    total_amount: Decimal = Field(ge=0)
    amount_paid: Decimal = Field(ge=0)
    balance_due: Decimal = Field(ge=0)
    settlement_status: ProcurementSettlementStatus
    is_overdue: bool

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class AccountsPayableResponse(BaseModel):
    """Approved supplier-bill balances."""

    organization_id: uuid.UUID
    generated_at: datetime
    as_of_date: date
    items: list[AccountsPayableItem]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)


class MatchExceptionItem(BaseModel):
    """Persisted three-way-match exception snapshot."""

    match_result_id: uuid.UUID
    supplier_bill_id: uuid.UUID
    supplier_bill_number: str
    supplier_invoice_number: str
    supplier_id: uuid.UUID
    supplier_name: str
    purchase_order_id: uuid.UUID
    purchase_order_line_item_id: uuid.UUID
    description: str
    currency: str = Field(min_length=3, max_length=3)
    quantity_ordered: Decimal = Field(ge=0)
    quantity_received: Decimal = Field(ge=0)
    quantity_billed: Decimal = Field(gt=0)
    purchase_order_unit_price: Decimal = Field(ge=0)
    supplier_bill_unit_price: Decimal = Field(ge=0)
    quantity_variance: Decimal
    unit_price_variance: Decimal
    quantity_variance_percent: Decimal
    unit_price_variance_percent: Decimal
    reasons: list[str]
    evaluated_at: datetime

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class MatchExceptionResponse(ProcurementDateRangeResponse):
    """Three-way matching exceptions."""

    items: list[MatchExceptionItem]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)


class ReceiptVarianceItem(BaseModel):
    """Rejected or damaged quantity recorded on a posted receipt line."""

    goods_receipt_id: uuid.UUID
    goods_receipt_number: str
    purchase_order_id: uuid.UUID
    purchase_order_number: str
    supplier_id: uuid.UUID
    supplier_name: str
    purchase_order_line_item_id: uuid.UUID
    inventory_item_id: uuid.UUID | None
    description: str
    received_at: datetime | None
    quantity_accepted: Decimal = Field(ge=0)
    quantity_rejected: Decimal = Field(ge=0)
    quantity_damaged: Decimal = Field(ge=0)
    total_delivered: Decimal = Field(gt=0)
    exception_rate_percent: Decimal = Field(ge=0)
    rejection_reason: str | None
    damage_notes: str | None


class ReceiptVarianceResponse(ProcurementDateRangeResponse):
    """Posted goods-receipt quantity exceptions."""

    items: list[ReceiptVarianceItem]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)


class PaymentHistoryItem(BaseModel):
    """Supplier payment activity with allocation totals."""

    supplier_payment_id: uuid.UUID
    payment_number: str
    supplier_id: uuid.UUID
    supplier_name: str
    payment_date: date
    payment_method: str
    currency: str = Field(min_length=3, max_length=3)
    total_amount: Decimal = Field(gt=0)
    allocated_amount: Decimal = Field(ge=0)
    allocation_count: int = Field(ge=0)
    reference_number: str | None
    status: str
    reversed_at: datetime | None
    reversal_reason: str | None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class PaymentHistoryResponse(ProcurementDateRangeResponse):
    """Supplier payment history."""

    items: list[PaymentHistoryItem]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
