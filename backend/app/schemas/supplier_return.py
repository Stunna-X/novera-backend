"""Schemas for supplier returns, debit notes, and credit settlement."""

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


def _required_text(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Value cannot be blank.")
    return cleaned


class SupplierReturnStatus(StrEnum):
    DRAFT = "draft"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SupplierReturnReasonCode(StrEnum):
    DAMAGED = "damaged"
    DEFECTIVE = "defective"
    WRONG_ITEM = "wrong_item"
    OVER_DELIVERY = "over_delivery"
    QUALITY_FAILURE = "quality_failure"
    OTHER = "other"


class SupplierReturnQuantitySource(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DAMAGED = "damaged"


class SupplierReturnLineCreate(BaseModel):
    goods_receipt_line_item_id: uuid.UUID
    quantity_source: SupplierReturnQuantitySource
    quantity_returned: Decimal = Field(
        gt=0,
        max_digits=16,
        decimal_places=3,
    )
    reason: str = Field(min_length=1, max_length=2000)
    position: int | None = Field(default=None, ge=0)
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return _required_text(value)


class SupplierReturnLineUpdate(BaseModel):
    quantity_returned: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=16,
        decimal_places=3,
    )
    reason: str | None = Field(default=None, max_length=2000)
    position: int | None = Field(default=None, ge=0)
    details: dict[str, Any] | None = None

    @field_validator("reason")
    @classmethod
    def clean_optional_reason(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        return _required_text(value)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one return-line field is required.")
        return self


class CreateSupplierReturnSchema(BaseModel):
    return_number: str | None = Field(default=None, max_length=50)
    goods_receipt_id: uuid.UUID
    source_location_id: uuid.UUID
    return_date: date
    reason_code: SupplierReturnReasonCode
    supplier_reference: str | None = Field(default=None, max_length=150)
    carrier_name: str | None = Field(default=None, max_length=160)
    tracking_number: str | None = Field(default=None, max_length=150)
    notes: str | None = Field(default=None, max_length=4000)
    details: dict[str, Any] = Field(default_factory=dict)
    line_items: list[SupplierReturnLineCreate] = Field(
        default_factory=list,
        max_length=200,
    )

    @model_validator(mode="after")
    def validate_unique_sources(self) -> Self:
        keys = [
            (line.goods_receipt_line_item_id, line.quantity_source)
            for line in self.line_items
        ]
        if len(keys) != len(set(keys)):
            raise ValueError(
                "Return lines cannot repeat the same receipt line "
                "and quantity source."
            )
        return self


class UpdateSupplierReturnSchema(BaseModel):
    return_date: date | None = None
    reason_code: SupplierReturnReasonCode | None = None
    supplier_reference: str | None = Field(default=None, max_length=150)
    carrier_name: str | None = Field(default=None, max_length=160)
    tracking_number: str | None = Field(default=None, max_length=150)
    notes: str | None = Field(default=None, max_length=4000)
    details: dict[str, Any] | None = None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one supplier-return field is required.")
        return self


class CancelSupplierReturnSchema(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return _required_text(value)


class CompleteSupplierReturnSchema(BaseModel):
    supplier_reference: str | None = Field(default=None, max_length=150)


class SupplierReturnLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    goods_receipt_line_item_id: uuid.UUID
    inventory_item_id: uuid.UUID | None
    inventory_movement_id: uuid.UUID | None
    quantity_source: SupplierReturnQuantitySource
    description: str
    quantity_returned: Decimal
    unit_of_measure: str
    unit_cost: Decimal
    currency: str
    reason: str
    position: int
    details: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SupplierReturnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    return_number: str
    supplier_id: uuid.UUID
    purchase_order_id: uuid.UUID
    goods_receipt_id: uuid.UUID
    source_location_id: uuid.UUID
    return_date: date
    reason_code: SupplierReturnReasonCode
    status: SupplierReturnStatus
    supplier_reference: str | None
    carrier_name: str | None
    tracking_number: str | None
    notes: str | None
    dispatched_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    details: dict[str, Any]
    is_active: bool
    line_items: list[SupplierReturnLineResponse]
    created_at: datetime
    updated_at: datetime


class SupplierReturnListResponse(BaseModel):
    items: list[SupplierReturnResponse]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)


class SupplierDebitNoteStatus(StrEnum):
    DRAFT = "draft"
    ISSUED = "issued"
    ACKNOWLEDGED = "acknowledged"
    VOIDED = "voided"


class SupplierDebitNoteLineCreate(BaseModel):
    supplier_return_line_item_id: uuid.UUID | None = None
    supplier_bill_line_item_id: uuid.UUID | None = None
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(
        gt=0,
        max_digits=16,
        decimal_places=3,
    )
    unit_of_measure: str = Field(min_length=1, max_length=40)
    unit_price: Decimal = Field(
        ge=0,
        max_digits=14,
        decimal_places=4,
    )
    tax_rate: Decimal = Field(
        default=Decimal("0.0000"),
        ge=0,
        le=100,
        max_digits=7,
        decimal_places=4,
    )
    position: int | None = Field(default=None, ge=0)
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("description", "unit_of_measure")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        return _required_text(value)


class SupplierDebitNoteLineUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=500)
    quantity: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=16,
        decimal_places=3,
    )
    unit_of_measure: str | None = Field(default=None, max_length=40)
    unit_price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=4,
    )
    tax_rate: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        max_digits=7,
        decimal_places=4,
    )
    position: int | None = Field(default=None, ge=0)
    details: dict[str, Any] | None = None

    @field_validator("description", "unit_of_measure")
    @classmethod
    def clean_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        return _required_text(value)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one debit-note line field is required.")
        return self


class CreateSupplierDebitNoteSchema(BaseModel):
    debit_note_number: str | None = Field(default=None, max_length=50)
    supplier_id: uuid.UUID
    supplier_return_id: uuid.UUID | None = None
    purchase_order_id: uuid.UUID | None = None
    note_date: date
    currency: str = Field(default="NGN", min_length=3, max_length=3)
    reason: str = Field(min_length=1, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)
    details: dict[str, Any] = Field(default_factory=dict)
    line_items: list[SupplierDebitNoteLineCreate] = Field(
        default_factory=list,
        max_length=200,
    )

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return _required_text(value)


class UpdateSupplierDebitNoteSchema(BaseModel):
    note_date: date | None = None
    reason: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)
    details: dict[str, Any] | None = None

    @field_validator("reason")
    @classmethod
    def clean_optional_reason(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        return _required_text(value)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one debit-note field is required.")
        return self


class AcknowledgeSupplierDebitNoteSchema(BaseModel):
    supplier_credit_reference: str = Field(min_length=1, max_length=150)

    @field_validator("supplier_credit_reference")
    @classmethod
    def normalize_reference(cls, value: str) -> str:
        return _required_text(value).upper()


class VoidSupplierDebitNoteSchema(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return _required_text(value)


class SupplierCreditAllocationCreate(BaseModel):
    supplier_bill_id: uuid.UUID
    amount_allocated: Decimal = Field(
        gt=0,
        max_digits=16,
        decimal_places=2,
    )
    notes: str | None = Field(default=None, max_length=2000)
    details: dict[str, Any] = Field(default_factory=dict)


class SettleSupplierDebitNoteSchema(BaseModel):
    settlement_date: date
    allocations: list[SupplierCreditAllocationCreate] = Field(
        min_length=1,
        max_length=200,
    )
    notes: str | None = Field(default=None, max_length=4000)
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_unique_bills(self) -> Self:
        bill_ids = [
            allocation.supplier_bill_id
            for allocation in self.allocations
        ]
        if len(bill_ids) != len(set(bill_ids)):
            raise ValueError(
                "A supplier bill can appear only once per credit settlement."
            )
        return self


class ReverseSupplierCreditSettlementSchema(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return _required_text(value)


class SupplierDebitNoteLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    supplier_return_line_item_id: uuid.UUID | None
    supplier_bill_line_item_id: uuid.UUID | None
    description: str
    quantity: Decimal
    unit_of_measure: str
    unit_price: Decimal
    tax_rate: Decimal
    line_subtotal: Decimal
    tax_amount: Decimal
    line_total: Decimal
    position: int
    details: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SupplierCreditSettlementResponse(BaseModel):
    id: uuid.UUID
    supplier_payment_id: uuid.UUID
    payment_number: str
    amount_settled: Decimal
    settlement_date: date
    status: str
    reversed_at: datetime | None
    reversal_reason: str | None
    position: int
    details: dict[str, Any]
    created_at: datetime


class SupplierDebitNoteResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    debit_note_number: str
    supplier_id: uuid.UUID
    supplier_return_id: uuid.UUID | None
    purchase_order_id: uuid.UUID | None
    note_date: date
    status: SupplierDebitNoteStatus
    currency: str
    supplier_credit_reference: str | None
    reason: str
    subtotal: Decimal
    tax_total: Decimal
    total_amount: Decimal
    amount_settled: Decimal
    available_credit: Decimal
    settlement_status: str
    notes: str | None
    issued_at: datetime | None
    acknowledged_at: datetime | None
    voided_at: datetime | None
    void_reason: str | None
    details: dict[str, Any]
    line_items: list[SupplierDebitNoteLineResponse]
    settlements: list[SupplierCreditSettlementResponse]
    created_at: datetime
    updated_at: datetime


class SupplierDebitNoteListResponse(BaseModel):
    items: list[SupplierDebitNoteResponse]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
