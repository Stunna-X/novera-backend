"""Validation and response schemas for purchase orders."""

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


PurchaseOrderStatus = Literal[
    "draft",
    "issued",
    "acknowledged",
    "partially_received",
    "received",
    "cancelled",
    "closed",
]


def _normalize_optional_text(value: object) -> object:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None

    return value


def _normalize_required_text(
    value: object,
    *,
    field_label: str,
) -> object:
    if isinstance(value, str):
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{field_label} cannot be empty."
            )

        return normalized

    return value


def _normalize_currency(value: object) -> object:
    if isinstance(value, str):
        normalized = value.strip().upper()

        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError(
                "Currency must be a three-letter code."
            )

        return normalized

    return value


class PurchaseOrderLineCreate(BaseModel):
    """One commercial line included in a purchase order."""

    inventory_item_id: uuid.UUID | None = None

    description: str = Field(
        min_length=1,
        max_length=500,
    )

    quantity_ordered: Decimal = Field(
        default=Decimal("1.000"),
        gt=Decimal("0"),
        max_digits=16,
        decimal_places=3,
    )

    unit_of_measure: str = Field(
        default="each",
        min_length=1,
        max_length=40,
    )

    unit_price: Decimal = Field(
        default=Decimal("0.0000"),
        ge=Decimal("0"),
        max_digits=14,
        decimal_places=4,
    )

    discount_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        max_digits=16,
        decimal_places=2,
    )

    tax_rate: Decimal = Field(
        default=Decimal("0.0000"),
        ge=Decimal("0"),
        le=Decimal("100"),
        max_digits=7,
        decimal_places=4,
    )

    position: int | None = Field(
        default=None,
        ge=0,
    )

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    details: dict[str, object] = Field(
        default_factory=dict,
    )

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: object) -> object:
        return _normalize_required_text(
            value,
            field_label="Line description",
        )

    @field_validator("unit_of_measure", mode="before")
    @classmethod
    def normalize_unit_of_measure(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()

            if not normalized:
                raise ValueError(
                    "Unit of measure cannot be empty."
                )

            return normalized

        return value

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: object) -> object:
        return _normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_discount_within_subtotal(self):
        subtotal = self.quantity_ordered * self.unit_price

        if self.discount_amount > subtotal:
            raise ValueError(
                "Discount amount cannot exceed line subtotal."
            )

        return self


class PurchaseOrderLineUpdate(BaseModel):
    """Editable fields for one draft purchase-order line."""

    inventory_item_id: uuid.UUID | None = None

    description: str | None = Field(
        default=None,
        max_length=500,
    )

    quantity_ordered: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
        max_digits=16,
        decimal_places=3,
    )

    unit_of_measure: str | None = Field(
        default=None,
        max_length=40,
    )

    unit_price: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=14,
        decimal_places=4,
    )

    discount_amount: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=16,
        decimal_places=2,
    )

    tax_rate: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("100"),
        max_digits=7,
        decimal_places=4,
    )

    position: int | None = Field(
        default=None,
        ge=0,
    )

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    details: dict[str, object] | None = None

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: object) -> object:
        if value is None:
            return None

        return _normalize_required_text(
            value,
            field_label="Line description",
        )

    @field_validator("unit_of_measure", mode="before")
    @classmethod
    def normalize_unit_of_measure(
        cls,
        value: object,
    ) -> object:
        if value is None:
            return None

        if isinstance(value, str):
            normalized = value.strip().lower()

            if not normalized:
                raise ValueError(
                    "Unit of measure cannot be empty."
                )

            return normalized

        return value

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: object) -> object:
        return _normalize_optional_text(value)


class CreatePurchaseOrderSchema(BaseModel):
    """Payload used to create a manual draft purchase order."""

    purchase_order_number: str | None = Field(
        default=None,
        max_length=50,
    )

    supplier_id: uuid.UUID

    title: str = Field(
        min_length=1,
        max_length=200,
    )

    currency: str = Field(
        default="NGN",
        min_length=3,
        max_length=3,
    )

    expected_delivery_date: date | None = None
    delivery_location_id: uuid.UUID | None = None

    delivery_address: str | None = Field(
        default=None,
        max_length=5000,
    )

    payment_terms_days: int = Field(
        default=0,
        ge=0,
        le=3650,
    )

    supplier_reference: str | None = Field(
        default=None,
        max_length=120,
    )

    notes: str | None = Field(
        default=None,
        max_length=10000,
    )

    terms_and_conditions: str | None = Field(
        default=None,
        max_length=20000,
    )

    details: dict[str, object] = Field(
        default_factory=dict,
    )

    line_items: list[PurchaseOrderLineCreate] = Field(
        default_factory=list,
        max_length=300,
    )

    @field_validator("purchase_order_number", mode="before")
    @classmethod
    def normalize_purchase_order_number(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or None

        return value

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: object) -> object:
        return _normalize_required_text(
            value,
            field_label="Purchase order title",
        )

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return _normalize_currency(value)

    @field_validator(
        "delivery_address",
        "supplier_reference",
        "notes",
        "terms_and_conditions",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_line_positions(self):
        positions = [
            line.position
            for line in self.line_items
            if line.position is not None
        ]

        if len(positions) != len(set(positions)):
            raise ValueError(
                "Line-item positions must be unique."
            )

        return self


class ConvertRequisitionToPurchaseOrderSchema(BaseModel):
    """Options used when converting an approved requisition."""

    supplier_id: uuid.UUID | None = None

    purchase_order_number: str | None = Field(
        default=None,
        max_length=50,
    )

    title: str | None = Field(
        default=None,
        max_length=200,
    )

    expected_delivery_date: date | None = None
    delivery_location_id: uuid.UUID | None = None

    delivery_address: str | None = Field(
        default=None,
        max_length=5000,
    )

    payment_terms_days: int | None = Field(
        default=None,
        ge=0,
        le=3650,
    )

    supplier_reference: str | None = Field(
        default=None,
        max_length=120,
    )

    notes: str | None = Field(
        default=None,
        max_length=10000,
    )

    terms_and_conditions: str | None = Field(
        default=None,
        max_length=20000,
    )

    details: dict[str, object] = Field(
        default_factory=dict,
    )

    @field_validator("purchase_order_number", mode="before")
    @classmethod
    def normalize_purchase_order_number(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or None

        return value

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: object) -> object:
        if value is None:
            return None

        return _normalize_required_text(
            value,
            field_label="Purchase order title",
        )

    @field_validator(
        "delivery_address",
        "supplier_reference",
        "notes",
        "terms_and_conditions",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _normalize_optional_text(value)


class UpdatePurchaseOrderSchema(BaseModel):
    """Editable purchase order header fields."""

    supplier_id: uuid.UUID | None = None

    title: str | None = Field(
        default=None,
        max_length=200,
    )

    expected_delivery_date: date | None = None
    delivery_location_id: uuid.UUID | None = None

    delivery_address: str | None = Field(
        default=None,
        max_length=5000,
    )

    payment_terms_days: int | None = Field(
        default=None,
        ge=0,
        le=3650,
    )

    supplier_reference: str | None = Field(
        default=None,
        max_length=120,
    )

    notes: str | None = Field(
        default=None,
        max_length=10000,
    )

    terms_and_conditions: str | None = Field(
        default=None,
        max_length=20000,
    )

    details: dict[str, object] | None = None

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: object) -> object:
        if value is None:
            return None

        return _normalize_required_text(
            value,
            field_label="Purchase order title",
        )

    @field_validator(
        "delivery_address",
        "supplier_reference",
        "notes",
        "terms_and_conditions",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _normalize_optional_text(value)


class AcknowledgePurchaseOrderSchema(BaseModel):
    """Optional supplier reference recorded on acknowledgement."""

    supplier_reference: str | None = Field(
        default=None,
        max_length=120,
    )

    @field_validator("supplier_reference", mode="before")
    @classmethod
    def normalize_supplier_reference(
        cls,
        value: object,
    ) -> object:
        return _normalize_optional_text(value)


class CancelPurchaseOrderSchema(BaseModel):
    """Reason supplied when cancelling a purchase order."""

    reason: str = Field(
        min_length=1,
        max_length=5000,
    )

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        return _normalize_required_text(
            value,
            field_label="Cancellation reason",
        )


class PurchaseOrderLineResponse(BaseModel):
    """One purchase order line returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    purchase_order_id: uuid.UUID
    source_requisition_line_id: uuid.UUID | None
    inventory_item_id: uuid.UUID | None
    description: str
    quantity_ordered: Decimal
    quantity_received: Decimal
    outstanding_quantity: Decimal
    is_fully_received: bool
    unit_of_measure: str
    unit_price: Decimal
    discount_amount: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    line_subtotal: Decimal
    line_total: Decimal
    position: int
    notes: str | None
    details: dict[str, object]
    created_at: datetime
    updated_at: datetime


class PurchaseOrderResponse(BaseModel):
    """Purchase order returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    purchase_order_number: str
    source_requisition_id: uuid.UUID | None
    supplier_id: uuid.UUID
    title: str
    status: PurchaseOrderStatus
    currency: str
    issue_date: date | None
    expected_delivery_date: date | None
    delivery_location_id: uuid.UUID | None
    delivery_address: str | None
    payment_terms_days: int
    supplier_reference: str | None
    supplier_name: str
    supplier_email: str | None
    supplier_phone: str | None
    supplier_tax_id: str | None
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total_amount: Decimal
    notes: str | None
    terms_and_conditions: str | None
    created_by_user_id: uuid.UUID | None
    issued_by_user_id: uuid.UUID | None
    acknowledged_by_user_id: uuid.UUID | None
    cancelled_by_user_id: uuid.UUID | None
    closed_by_user_id: uuid.UUID | None
    issued_at: datetime | None
    acknowledged_at: datetime | None
    cancelled_at: datetime | None
    closed_at: datetime | None
    cancellation_reason: str | None
    details: dict[str, object]
    is_active: bool
    line_items: list[PurchaseOrderLineResponse]
    created_at: datetime
    updated_at: datetime


class PurchaseOrderListResponse(BaseModel):
    """Paginated purchase order collection."""

    items: list[PurchaseOrderResponse]
    total: int
    skip: int
    limit: int
