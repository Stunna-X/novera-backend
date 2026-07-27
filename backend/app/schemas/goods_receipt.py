"""Validation and response schemas for goods receipts."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


GoodsReceiptStatus = Literal[
    "draft",
    "posted",
    "cancelled",
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
            raise ValueError(f"{field_label} cannot be empty.")

        return normalized

    return value


def _validate_timezone(value: datetime | None) -> datetime | None:
    if (
        value is not None
        and (value.tzinfo is None or value.utcoffset() is None)
    ):
        raise ValueError("received_at must include a timezone.")

    return value


class GoodsReceiptLineCreate(BaseModel):
    """One purchase-order line included in a draft receipt."""

    purchase_order_line_item_id: uuid.UUID

    quantity_accepted: Decimal = Field(
        default=Decimal("0.000"),
        ge=Decimal("0"),
        max_digits=16,
        decimal_places=3,
    )

    quantity_rejected: Decimal = Field(
        default=Decimal("0.000"),
        ge=Decimal("0"),
        max_digits=16,
        decimal_places=3,
    )

    quantity_damaged: Decimal = Field(
        default=Decimal("0.000"),
        ge=Decimal("0"),
        max_digits=16,
        decimal_places=3,
    )

    unit_cost: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=14,
        decimal_places=4,
    )

    rejection_reason: str | None = Field(
        default=None,
        max_length=5000,
    )

    damage_notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    position: int | None = Field(
        default=None,
        ge=0,
    )

    details: dict[str, object] = Field(default_factory=dict)

    @field_validator(
        "rejection_reason",
        "damage_notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_quantities_and_reasons(self):
        total = (
            self.quantity_accepted
            + self.quantity_rejected
            + self.quantity_damaged
        )

        if total <= Decimal("0"):
            raise ValueError(
                "At least one delivered quantity must be greater than zero."
            )

        if (
            self.quantity_rejected > Decimal("0")
            and self.rejection_reason is None
        ):
            raise ValueError(
                "A rejection reason is required for rejected quantity."
            )

        if (
            self.quantity_damaged > Decimal("0")
            and self.damage_notes is None
        ):
            raise ValueError(
                "Damage notes are required for damaged quantity."
            )

        return self


class GoodsReceiptLineUpdate(BaseModel):
    """Editable fields for one draft receipt line."""

    quantity_accepted: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=16,
        decimal_places=3,
    )

    quantity_rejected: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=16,
        decimal_places=3,
    )

    quantity_damaged: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=16,
        decimal_places=3,
    )

    unit_cost: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=14,
        decimal_places=4,
    )

    rejection_reason: str | None = Field(
        default=None,
        max_length=5000,
    )

    damage_notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    position: int | None = Field(default=None, ge=0)
    details: dict[str, object] | None = None

    @field_validator(
        "rejection_reason",
        "damage_notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _normalize_optional_text(value)

    @model_validator(mode="after")
    def require_at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("At least one line field must be supplied.")

        non_nullable_fields = {
            "quantity_accepted",
            "quantity_rejected",
            "quantity_damaged",
            "unit_cost",
            "position",
            "details",
        }

        for field_name in self.model_fields_set & non_nullable_fields:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")

        return self


class CreateGoodsReceiptSchema(BaseModel):
    """Payload used to create a draft goods receipt."""

    goods_receipt_number: str | None = Field(
        default=None,
        max_length=50,
    )

    purchase_order_id: uuid.UUID
    receiving_location_id: uuid.UUID

    received_at: datetime | None = None

    supplier_delivery_note: str | None = Field(
        default=None,
        max_length=120,
    )

    carrier_name: str | None = Field(
        default=None,
        max_length=160,
    )

    vehicle_reference: str | None = Field(
        default=None,
        max_length=100,
    )

    notes: str | None = Field(
        default=None,
        max_length=10000,
    )

    details: dict[str, object] = Field(default_factory=dict)

    line_items: list[GoodsReceiptLineCreate] = Field(
        default_factory=list,
        max_length=300,
    )

    @field_validator("goods_receipt_number", mode="before")
    @classmethod
    def normalize_number(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or None

        return value

    @field_validator("received_at", mode="after")
    @classmethod
    def validate_received_at(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        return _validate_timezone(value)

    @field_validator(
        "supplier_delivery_note",
        "carrier_name",
        "vehicle_reference",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_line_uniqueness(self):
        line_ids = [
            line.purchase_order_line_item_id
            for line in self.line_items
        ]

        if len(line_ids) != len(set(line_ids)):
            raise ValueError(
                "Each purchase-order line can appear only once per receipt."
            )

        positions = [
            line.position
            for line in self.line_items
            if line.position is not None
        ]

        if len(positions) != len(set(positions)):
            raise ValueError("Receipt line positions must be unique.")

        return self


class UpdateGoodsReceiptSchema(BaseModel):
    """Editable header fields for a draft goods receipt."""

    receiving_location_id: uuid.UUID | None = None
    received_at: datetime | None = None

    supplier_delivery_note: str | None = Field(
        default=None,
        max_length=120,
    )

    carrier_name: str | None = Field(
        default=None,
        max_length=160,
    )

    vehicle_reference: str | None = Field(
        default=None,
        max_length=100,
    )

    notes: str | None = Field(
        default=None,
        max_length=10000,
    )

    details: dict[str, object] | None = None

    @field_validator("received_at", mode="after")
    @classmethod
    def validate_received_at(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        return _validate_timezone(value)

    @field_validator(
        "supplier_delivery_note",
        "carrier_name",
        "vehicle_reference",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _normalize_optional_text(value)

    @model_validator(mode="after")
    def require_at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("At least one receipt field must be supplied.")

        for field_name in {"receiving_location_id", "details"}:
            if (
                field_name in self.model_fields_set
                and getattr(self, field_name) is None
            ):
                raise ValueError(f"{field_name} cannot be null.")

        return self


class CancelGoodsReceiptSchema(BaseModel):
    """Reason supplied when cancelling a draft receipt."""

    reason: str = Field(min_length=1, max_length=5000)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        return _normalize_required_text(
            value,
            field_label="Cancellation reason",
        )


class GoodsReceiptLineResponse(BaseModel):
    """One goods-receipt line returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    goods_receipt_id: uuid.UUID
    purchase_order_line_item_id: uuid.UUID
    inventory_item_id: uuid.UUID | None
    inventory_movement_id: uuid.UUID | None
    description: str
    quantity_accepted: Decimal
    quantity_rejected: Decimal
    quantity_damaged: Decimal
    total_delivered_quantity: Decimal
    unit_of_measure: str
    unit_cost: Decimal
    currency: str
    rejection_reason: str | None
    damage_notes: str | None
    position: int
    details: dict[str, object]
    created_at: datetime
    updated_at: datetime


class GoodsReceiptResponse(BaseModel):
    """Goods receipt returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    goods_receipt_number: str
    purchase_order_id: uuid.UUID
    supplier_id: uuid.UUID
    receiving_location_id: uuid.UUID
    status: GoodsReceiptStatus
    received_at: datetime | None
    supplier_delivery_note: str | None
    carrier_name: str | None
    vehicle_reference: str | None
    notes: str | None
    created_by_user_id: uuid.UUID | None
    posted_by_user_id: uuid.UUID | None
    cancelled_by_user_id: uuid.UUID | None
    posted_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    details: dict[str, object]
    is_active: bool
    total_accepted_quantity: Decimal
    total_rejected_quantity: Decimal
    total_damaged_quantity: Decimal
    total_delivered_quantity: Decimal
    line_items: list[GoodsReceiptLineResponse]
    created_at: datetime
    updated_at: datetime


class GoodsReceiptListResponse(BaseModel):
    """Paginated goods-receipt collection."""

    items: list[GoodsReceiptResponse]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1)
