"""Validation and response schemas for purchase requisitions."""

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


PurchaseRequisitionStatus = Literal[
    "draft",
    "submitted",
    "approved",
    "rejected",
    "cancelled",
    "converted",
]

PurchaseRequisitionPriority = Literal[
    "low",
    "normal",
    "high",
    "urgent",
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


class PurchaseRequisitionLineCreate(BaseModel):
    """One line included in a purchase requisition."""

    inventory_item_id: uuid.UUID | None = None
    preferred_supplier_id: uuid.UUID | None = None

    description: str = Field(
        min_length=1,
        max_length=500,
    )

    quantity: Decimal = Field(
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

    estimated_unit_cost: Decimal = Field(
        default=Decimal("0.0000"),
        ge=Decimal("0"),
        max_digits=14,
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


class PurchaseRequisitionLineUpdate(BaseModel):
    """Editable fields for one requisition line."""

    inventory_item_id: uuid.UUID | None = None
    preferred_supplier_id: uuid.UUID | None = None

    description: str | None = Field(
        default=None,
        max_length=500,
    )

    quantity: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
        max_digits=16,
        decimal_places=3,
    )

    unit_of_measure: str | None = Field(
        default=None,
        max_length=40,
    )

    estimated_unit_cost: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=14,
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


class CreatePurchaseRequisitionSchema(BaseModel):
    """Payload used to create a draft purchase requisition."""

    requisition_number: str | None = Field(
        default=None,
        max_length=50,
    )

    title: str = Field(
        min_length=1,
        max_length=200,
    )

    description: str | None = Field(
        default=None,
        max_length=10000,
    )

    priority: PurchaseRequisitionPriority = "normal"

    currency: str = Field(
        default="NGN",
        min_length=3,
        max_length=3,
    )

    preferred_supplier_id: uuid.UUID | None = None
    work_order_id: uuid.UUID | None = None
    delivery_location_id: uuid.UUID | None = None
    requested_delivery_date: date | None = None

    justification: str | None = Field(
        default=None,
        max_length=10000,
    )

    notes: str | None = Field(
        default=None,
        max_length=10000,
    )

    details: dict[str, object] = Field(
        default_factory=dict,
    )

    line_items: list[
        PurchaseRequisitionLineCreate
    ] = Field(
        default_factory=list,
        max_length=200,
    )

    @field_validator("requisition_number", mode="before")
    @classmethod
    def normalize_requisition_number(
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
            field_label="Requisition title",
        )

    @field_validator(
        "description",
        "justification",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _normalize_optional_text(value)

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()

        return value

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return _normalize_currency(value)

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


class UpdatePurchaseRequisitionSchema(BaseModel):
    """Editable purchase requisition header fields."""

    title: str | None = Field(
        default=None,
        max_length=200,
    )

    description: str | None = Field(
        default=None,
        max_length=10000,
    )

    priority: PurchaseRequisitionPriority | None = None

    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
    )

    preferred_supplier_id: uuid.UUID | None = None
    work_order_id: uuid.UUID | None = None
    delivery_location_id: uuid.UUID | None = None
    requested_delivery_date: date | None = None

    justification: str | None = Field(
        default=None,
        max_length=10000,
    )

    notes: str | None = Field(
        default=None,
        max_length=10000,
    )

    details: dict[str, object] | None = None

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: object) -> object:
        if value is None:
            return None

        return _normalize_required_text(
            value,
            field_label="Requisition title",
        )

    @field_validator(
        "description",
        "justification",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _normalize_optional_text(value)

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()

        return value

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        if value is None:
            return None

        return _normalize_currency(value)


class RejectPurchaseRequisitionSchema(BaseModel):
    """Reason supplied when rejecting a submitted request."""

    reason: str = Field(
        min_length=1,
        max_length=5000,
    )

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        return _normalize_required_text(
            value,
            field_label="Rejection reason",
        )


class CancelPurchaseRequisitionSchema(BaseModel):
    """Optional reason supplied when cancelling a request."""

    reason: str | None = Field(
        default=None,
        max_length=5000,
    )

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        return _normalize_optional_text(value)


class PurchaseRequisitionLineResponse(BaseModel):
    """One requisition line returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requisition_id: uuid.UUID
    inventory_item_id: uuid.UUID | None
    preferred_supplier_id: uuid.UUID | None
    description: str
    quantity: Decimal
    unit_of_measure: str
    estimated_unit_cost: Decimal
    line_total: Decimal
    position: int
    notes: str | None
    details: dict[str, object]
    created_at: datetime
    updated_at: datetime


class PurchaseRequisitionResponse(BaseModel):
    """Purchase requisition returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    requisition_number: str
    title: str
    description: str | None
    status: PurchaseRequisitionStatus
    priority: PurchaseRequisitionPriority
    currency: str
    preferred_supplier_id: uuid.UUID | None
    work_order_id: uuid.UUID | None
    delivery_location_id: uuid.UUID | None
    requested_delivery_date: date | None
    justification: str | None
    notes: str | None
    total_estimated_amount: Decimal
    created_by_user_id: uuid.UUID | None
    submitted_by_user_id: uuid.UUID | None
    approved_by_user_id: uuid.UUID | None
    rejected_by_user_id: uuid.UUID | None
    cancelled_by_user_id: uuid.UUID | None
    submitted_at: datetime | None
    approved_at: datetime | None
    rejected_at: datetime | None
    cancelled_at: datetime | None
    rejection_reason: str | None
    cancellation_reason: str | None
    details: dict[str, object]
    is_active: bool
    line_items: list[PurchaseRequisitionLineResponse]
    created_at: datetime
    updated_at: datetime


class PurchaseRequisitionListResponse(BaseModel):
    """Paginated purchase requisition collection."""

    items: list[PurchaseRequisitionResponse]
    total: int
    skip: int
    limit: int
