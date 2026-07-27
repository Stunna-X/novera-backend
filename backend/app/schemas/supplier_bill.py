"""Validation and response schemas for supplier bills."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


SupplierBillStatus = Literal[
    "draft",
    "submitted",
    "matched",
    "exception",
    "approved",
    "voided",
]
SupplierBillMatchStatus = Literal[
    "not_run",
    "matched",
    "exception",
]


def _optional_text(value: object) -> object:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return value


def _required_text(value: object, label: str) -> object:
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{label} cannot be empty.")
        return normalized
    return value


def _currency(value: object) -> object:
    if isinstance(value, str):
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("Currency must be a three-letter code.")
        return normalized
    return value


class SupplierBillLineCreate(BaseModel):
    """Create one supplier-bill line from a purchase-order line."""

    purchase_order_line_item_id: uuid.UUID
    description: str | None = Field(default=None, max_length=500)
    quantity_billed: Decimal = Field(
        gt=Decimal("0"),
        max_digits=16,
        decimal_places=3,
    )
    unit_of_measure: str | None = Field(default=None, max_length=40)
    unit_price: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=14,
        decimal_places=4,
    )
    tax_rate: Decimal = Field(
        default=Decimal("0.0000"),
        ge=Decimal("0"),
        le=Decimal("100"),
        max_digits=7,
        decimal_places=4,
    )
    position: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=5000)
    details: dict[str, object] = Field(default_factory=dict)

    @field_validator("description", "unit_of_measure", "notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _optional_text(value)


class SupplierBillLineUpdate(BaseModel):
    """Editable fields for one draft supplier-bill line."""

    description: str | None = Field(default=None, max_length=500)
    quantity_billed: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
        max_digits=16,
        decimal_places=3,
    )
    unit_of_measure: str | None = Field(default=None, max_length=40)
    unit_price: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=14,
        decimal_places=4,
    )
    tax_rate: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("100"),
        max_digits=7,
        decimal_places=4,
    )
    position: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=5000)
    details: dict[str, object] | None = None

    @field_validator("description", "unit_of_measure", "notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _optional_text(value)

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one line field must be supplied.")
        return self


class CreateSupplierBillSchema(BaseModel):
    """Create a draft supplier bill."""

    supplier_bill_number: str | None = Field(default=None, max_length=50)
    supplier_invoice_number: str = Field(min_length=1, max_length=120)
    supplier_id: uuid.UUID
    purchase_order_id: uuid.UUID
    invoice_date: date
    due_date: date | None = None
    currency: str = Field(default="NGN", min_length=3, max_length=3)
    quantity_tolerance_percent: Decimal = Field(
        default=Decimal("0.0000"),
        ge=Decimal("0"),
        le=Decimal("100"),
        max_digits=7,
        decimal_places=4,
    )
    price_tolerance_percent: Decimal = Field(
        default=Decimal("0.0000"),
        ge=Decimal("0"),
        le=Decimal("100"),
        max_digits=7,
        decimal_places=4,
    )
    notes: str | None = Field(default=None, max_length=10000)
    details: dict[str, object] = Field(default_factory=dict)
    line_items: list[SupplierBillLineCreate] = Field(default_factory=list)

    @field_validator("supplier_bill_number", mode="before")
    @classmethod
    def normalize_bill_number(cls, value: object) -> object:
        normalized = _optional_text(value)
        return normalized.upper() if isinstance(normalized, str) else normalized

    @field_validator("supplier_invoice_number", mode="before")
    @classmethod
    def normalize_supplier_invoice(cls, value: object) -> object:
        return _required_text(value, "Supplier invoice number")

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return _currency(value)

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: object) -> object:
        return _optional_text(value)

    @model_validator(mode="after")
    def validate_dates_and_lines(self):
        if self.due_date is not None and self.due_date < self.invoice_date:
            raise ValueError("Due date cannot precede invoice date.")
        line_ids = [line.purchase_order_line_item_id for line in self.line_items]
        if len(line_ids) != len(set(line_ids)):
            raise ValueError("Supplier bill lines cannot repeat a purchase-order line.")
        return self


class UpdateSupplierBillSchema(BaseModel):
    """Editable supplier-bill header fields."""

    supplier_invoice_number: str | None = Field(default=None, max_length=120)
    invoice_date: date | None = None
    due_date: date | None = None
    quantity_tolerance_percent: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("100"),
        max_digits=7,
        decimal_places=4,
    )
    price_tolerance_percent: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("100"),
        max_digits=7,
        decimal_places=4,
    )
    notes: str | None = Field(default=None, max_length=10000)
    details: dict[str, object] | None = None

    @field_validator("supplier_invoice_number", mode="before")
    @classmethod
    def normalize_supplier_invoice(cls, value: object) -> object:
        if value is None:
            return None
        return _required_text(value, "Supplier invoice number")

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: object) -> object:
        return _optional_text(value)

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one supplier-bill field must be supplied.")
        return self


class SubmitSupplierBillSchema(BaseModel):
    """Optional submission note."""

    note: str | None = Field(default=None, max_length=5000)

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value: object) -> object:
        return _optional_text(value)


class MatchSupplierBillSchema(BaseModel):
    """Optional tolerances applied to a three-way match run."""

    quantity_tolerance_percent: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("100"),
        max_digits=7,
        decimal_places=4,
    )
    price_tolerance_percent: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("100"),
        max_digits=7,
        decimal_places=4,
    )


class ApproveSupplierBillSchema(BaseModel):
    """Approve a matched bill or override documented exceptions."""

    override_reason: str | None = Field(default=None, max_length=5000)

    @field_validator("override_reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        return _optional_text(value)


class VoidSupplierBillSchema(BaseModel):
    """Void a supplier bill while retaining its audit trail."""

    reason: str = Field(min_length=1, max_length=5000)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        return _required_text(value, "Void reason")


class SupplierBillMatchResultResponse(BaseModel):
    """Persisted match evidence for one line."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    supplier_bill_line_item_id: uuid.UUID
    purchase_order_line_item_id: uuid.UUID
    status: Literal["matched", "exception"]
    quantity_ordered: Decimal
    quantity_received: Decimal
    quantity_billed: Decimal
    purchase_order_unit_price: Decimal
    supplier_bill_unit_price: Decimal
    quantity_variance: Decimal
    unit_price_variance: Decimal
    quantity_variance_percent: Decimal
    unit_price_variance_percent: Decimal
    quantity_within_tolerance: bool
    price_within_tolerance: bool
    reasons: list[str]
    evaluated_at: datetime
    evaluated_by_user_id: uuid.UUID | None


class SupplierBillLineResponse(BaseModel):
    """Serialized supplier-bill line."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    purchase_order_line_item_id: uuid.UUID
    description: str
    quantity_billed: Decimal
    unit_of_measure: str
    unit_price: Decimal
    tax_rate: Decimal
    line_subtotal: Decimal
    tax_amount: Decimal
    line_total: Decimal
    position: int
    notes: str | None
    details: dict[str, object]
    match_result: SupplierBillMatchResultResponse | None
    created_at: datetime
    updated_at: datetime


class SupplierBillResponse(BaseModel):
    """Serialized supplier bill."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    supplier_bill_number: str
    supplier_invoice_number: str
    supplier_id: uuid.UUID
    purchase_order_id: uuid.UUID
    invoice_date: date
    due_date: date | None
    status: SupplierBillStatus
    match_status: SupplierBillMatchStatus
    currency: str
    quantity_tolerance_percent: Decimal
    price_tolerance_percent: Decimal
    subtotal: Decimal
    tax_total: Decimal
    total_amount: Decimal
    notes: str | None
    created_by_user_id: uuid.UUID | None
    submitted_by_user_id: uuid.UUID | None
    matched_by_user_id: uuid.UUID | None
    approved_by_user_id: uuid.UUID | None
    voided_by_user_id: uuid.UUID | None
    submitted_at: datetime | None
    matched_at: datetime | None
    approved_at: datetime | None
    voided_at: datetime | None
    approval_override_reason: str | None
    void_reason: str | None
    details: dict[str, object]
    is_active: bool
    line_items: list[SupplierBillLineResponse]
    created_at: datetime
    updated_at: datetime


class SupplierBillListResponse(BaseModel):
    """Paginated supplier-bill collection."""

    items: list[SupplierBillResponse]
    total: int
    skip: int
    limit: int


class SupplierBillMatchSummaryResponse(BaseModel):
    """Header-level summary of the latest persisted match run."""

    supplier_bill_id: uuid.UUID
    status: SupplierBillStatus
    match_status: SupplierBillMatchStatus
    matched_lines: int
    exception_lines: int
    total_lines: int
    quantity_tolerance_percent: Decimal
    price_tolerance_percent: Decimal
    evaluated_at: datetime | None
    results: list[SupplierBillMatchResultResponse]
