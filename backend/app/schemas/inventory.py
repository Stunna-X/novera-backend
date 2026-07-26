"""
Inventory schemas.

Defines validation and API responses for inventory locations,
catalogue items, stock balances, stock operations, reservations, and the movement ledger.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


InventoryLocationType = Literal[
    "warehouse",
    "store",
    "vehicle",
    "job_site",
    "technician",
    "other",
]

InventoryItemType = Literal[
    "material",
    "consumable",
    "spare_part",
    "supply",
    "fuel",
    "other",
]


class InventoryLocationBaseSchema(BaseModel):
    """
    Shared inventory-location fields.
    """

    code: str = Field(
        min_length=1,
        max_length=50,
    )

    name: str = Field(
        min_length=1,
        max_length=160,
    )

    location_type: InventoryLocationType = "warehouse"

    address: str | None = Field(
        default=None,
        max_length=5000,
    )

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    @field_validator(
        "code",
        mode="before",
    )
    @classmethod
    def normalize_code(
        cls,
        value: object,
    ) -> object:
        """
        Normalize location codes to uppercase.
        """

        if isinstance(value, str):
            normalized = value.strip().upper()

            if not normalized:
                raise ValueError(
                    "Location code cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "name",
        mode="before",
    )
    @classmethod
    def normalize_name(
        cls,
        value: object,
    ) -> object:
        """
        Strip and validate the location name.
        """

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Location name cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "location_type",
        mode="before",
    )
    @classmethod
    def normalize_location_type(
        cls,
        value: object,
    ) -> object:
        """
        Normalize controlled location values.
        """

        if isinstance(value, str):
            return value.strip().lower()

        return value

    @field_validator(
        "address",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """
        Convert blank optional strings to None.
        """

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value


class CreateInventoryLocationSchema(
    InventoryLocationBaseSchema
):
    """
    Payload for creating a stock location.
    """

    pass


class UpdateInventoryLocationSchema(BaseModel):
    """
    Partial stock-location update.
    """

    code: str | None = Field(
        default=None,
        max_length=50,
    )

    name: str | None = Field(
        default=None,
        max_length=160,
    )

    location_type: InventoryLocationType | None = None

    address: str | None = Field(
        default=None,
        max_length=5000,
    )

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    @field_validator(
        "code",
        mode="before",
    )
    @classmethod
    def normalize_code(
        cls,
        value: object,
    ) -> object:
        """
        Normalize supplied location codes.
        """

        if isinstance(value, str):
            normalized = value.strip().upper()

            if not normalized:
                raise ValueError(
                    "Location code cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "name",
        mode="before",
    )
    @classmethod
    def normalize_name(
        cls,
        value: object,
    ) -> object:
        """
        Validate a supplied location name.
        """

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Location name cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "location_type",
        mode="before",
    )
    @classmethod
    def normalize_location_type(
        cls,
        value: object,
    ) -> object:
        """
        Normalize controlled location values.
        """

        if isinstance(value, str):
            return value.strip().lower()

        return value

    @field_validator(
        "address",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """
        Convert blank optional strings to None.
        """

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value


class InventoryLocationResponse(BaseModel):
    """
    Inventory location returned by the API.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    organization_id: uuid.UUID

    code: str
    name: str
    location_type: InventoryLocationType

    address: str | None
    notes: str | None

    is_active: bool

    created_at: datetime
    updated_at: datetime


class InventoryLocationListResponse(BaseModel):
    """
    Paginated inventory-location response.
    """

    items: list[InventoryLocationResponse]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1)


class InventoryItemBaseSchema(BaseModel):
    """
    Shared inventory-item fields.
    """

    sku: str = Field(
        min_length=1,
        max_length=80,
    )

    barcode: str | None = Field(
        default=None,
        max_length=120,
    )

    name: str = Field(
        min_length=1,
        max_length=180,
    )

    item_type: InventoryItemType = "material"

    category: str | None = Field(
        default=None,
        max_length=120,
    )

    description: str | None = Field(
        default=None,
        max_length=10000,
    )

    unit_of_measure: str = Field(
        default="each",
        min_length=1,
        max_length=40,
    )

    default_unit_cost: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        decimal_places=4,
    )

    currency: str = Field(
        default="NGN",
        min_length=3,
        max_length=3,
    )

    reorder_level: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        decimal_places=3,
    )

    reorder_quantity: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
        decimal_places=3,
    )

    preferred_supplier: str | None = Field(
        default=None,
        max_length=200,
    )

    details: dict[str, Any] = Field(
        default_factory=dict,
    )

    @field_validator(
        "sku",
        mode="before",
    )
    @classmethod
    def normalize_sku(
        cls,
        value: object,
    ) -> object:
        """
        Normalize stock-keeping units.
        """

        if isinstance(value, str):
            normalized = value.strip().upper()

            if not normalized:
                raise ValueError(
                    "SKU cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "barcode",
        mode="before",
    )
    @classmethod
    def normalize_barcode(
        cls,
        value: object,
    ) -> object:
        """
        Normalize optional barcode values.
        """

        if isinstance(value, str):
            normalized = value.strip().upper()

            return normalized or None

        return value

    @field_validator(
        "name",
        mode="before",
    )
    @classmethod
    def normalize_name(
        cls,
        value: object,
    ) -> object:
        """
        Strip and validate the item name.
        """

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Inventory item name cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "item_type",
        mode="before",
    )
    @classmethod
    def normalize_item_type(
        cls,
        value: object,
    ) -> object:
        """
        Normalize item-type values.
        """

        if isinstance(value, str):
            return value.strip().lower()

        return value

    @field_validator(
        "unit_of_measure",
        mode="before",
    )
    @classmethod
    def normalize_unit(
        cls,
        value: object,
    ) -> object:
        """
        Normalize units of measure.
        """

        if isinstance(value, str):
            normalized = value.strip().lower()

            if not normalized:
                raise ValueError(
                    "Unit of measure cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "currency",
        mode="before",
    )
    @classmethod
    def normalize_currency(
        cls,
        value: object,
    ) -> object:
        """
        Normalize ISO-style currency codes.
        """

        if isinstance(value, str):
            normalized = value.strip().upper()

            if (
                len(normalized) != 3
                or not normalized.isalpha()
            ):
                raise ValueError(
                    "Currency must contain three letters."
                )

            return normalized

        return value

    @field_validator(
        "category",
        "description",
        "preferred_supplier",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """
        Convert blank optional strings to None.
        """

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value


class CreateInventoryItemSchema(
    InventoryItemBaseSchema
):
    """
    Payload for creating an inventory item.
    """

    pass


class UpdateInventoryItemSchema(BaseModel):
    """
    Partial inventory-item update.
    """

    sku: str | None = Field(
        default=None,
        max_length=80,
    )

    barcode: str | None = Field(
        default=None,
        max_length=120,
    )

    name: str | None = Field(
        default=None,
        max_length=180,
    )

    item_type: InventoryItemType | None = None

    category: str | None = Field(
        default=None,
        max_length=120,
    )

    description: str | None = Field(
        default=None,
        max_length=10000,
    )

    unit_of_measure: str | None = Field(
        default=None,
        max_length=40,
    )

    default_unit_cost: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        decimal_places=4,
    )

    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
    )

    reorder_level: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        decimal_places=3,
    )

    reorder_quantity: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
        decimal_places=3,
    )

    preferred_supplier: str | None = Field(
        default=None,
        max_length=200,
    )

    details: dict[str, Any] | None = None

    @field_validator(
        "sku",
        mode="before",
    )
    @classmethod
    def normalize_sku(
        cls,
        value: object,
    ) -> object:
        """
        Normalize supplied SKUs.
        """

        if isinstance(value, str):
            normalized = value.strip().upper()

            if not normalized:
                raise ValueError(
                    "SKU cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "barcode",
        mode="before",
    )
    @classmethod
    def normalize_barcode(
        cls,
        value: object,
    ) -> object:
        """
        Normalize optional barcode values.
        """

        if isinstance(value, str):
            normalized = value.strip().upper()

            return normalized or None

        return value

    @field_validator(
        "name",
        mode="before",
    )
    @classmethod
    def normalize_name(
        cls,
        value: object,
    ) -> object:
        """
        Validate a supplied item name.
        """

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Inventory item name cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "item_type",
        mode="before",
    )
    @classmethod
    def normalize_item_type(
        cls,
        value: object,
    ) -> object:
        """
        Normalize item-type values.
        """

        if isinstance(value, str):
            return value.strip().lower()

        return value

    @field_validator(
        "unit_of_measure",
        mode="before",
    )
    @classmethod
    def normalize_unit(
        cls,
        value: object,
    ) -> object:
        """
        Normalize units of measure.
        """

        if isinstance(value, str):
            normalized = value.strip().lower()

            if not normalized:
                raise ValueError(
                    "Unit of measure cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "currency",
        mode="before",
    )
    @classmethod
    def normalize_currency(
        cls,
        value: object,
    ) -> object:
        """
        Normalize currency codes.
        """

        if isinstance(value, str):
            normalized = value.strip().upper()

            if (
                len(normalized) != 3
                or not normalized.isalpha()
            ):
                raise ValueError(
                    "Currency must contain three letters."
                )

            return normalized

        return value

    @field_validator(
        "category",
        "description",
        "preferred_supplier",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """
        Convert blank optional strings to None.
        """

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value


class InventoryItemResponse(BaseModel):
    """
    Inventory catalogue item returned by the API.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    organization_id: uuid.UUID

    sku: str
    barcode: str | None
    name: str
    item_type: InventoryItemType

    category: str | None
    description: str | None
    unit_of_measure: str

    default_unit_cost: Decimal
    currency: str

    reorder_level: Decimal
    reorder_quantity: Decimal | None

    preferred_supplier: str | None
    details: dict[str, Any]

    is_active: bool

    created_at: datetime
    updated_at: datetime


class InventoryItemListResponse(BaseModel):
    """
    Paginated inventory-item response.
    """

    items: list[InventoryItemResponse]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1)


class InventoryItemSummary(BaseModel):
    """
    Compact item representation used in balance responses.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    sku: str
    name: str
    item_type: InventoryItemType
    unit_of_measure: str
    currency: str
    reorder_level: Decimal
    is_active: bool


class InventoryLocationSummary(BaseModel):
    """
    Compact location representation used in balances.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    code: str
    name: str
    location_type: InventoryLocationType
    is_active: bool


class InventoryBalanceResponse(BaseModel):
    """
    Current item balance at one location.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    organization_id: uuid.UUID
    item_id: uuid.UUID
    location_id: uuid.UUID

    quantity_on_hand: Decimal
    quantity_reserved: Decimal
    available_quantity: Decimal
    average_unit_cost: Decimal

    last_movement_at: datetime | None

    item: InventoryItemSummary
    location: InventoryLocationSummary

    created_at: datetime
    updated_at: datetime


class InventoryBalanceListResponse(BaseModel):
    """
    Paginated location-level stock balances.
    """

    items: list[InventoryBalanceResponse]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1)


class LowStockItemResponse(BaseModel):
    """
    Organization-level low-stock summary.
    """

    item_id: uuid.UUID
    sku: str
    name: str
    item_type: InventoryItemType
    unit_of_measure: str
    currency: str

    reorder_level: Decimal
    reorder_quantity: Decimal | None

    quantity_on_hand: Decimal
    quantity_reserved: Decimal
    available_quantity: Decimal
    shortage_quantity: Decimal


class LowStockListResponse(BaseModel):
    """
    Paginated low-stock collection.
    """

    items: list[LowStockItemResponse]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1)

# ------------------------------------------------------------------
# Stock operations, reservations, and movement ledger
# ------------------------------------------------------------------


InventoryMovementType = Literal[
    "opening_balance",
    "receipt",
    "issue",
    "return",
    "adjustment_in",
    "adjustment_out",
    "transfer_in",
    "transfer_out",
]

InventoryReceiptType = Literal[
    "receipt",
    "opening_balance",
]

InventoryReservationStatus = Literal[
    "active",
    "partially_consumed",
    "consumed",
    "released",
    "cancelled",
]


class InventoryOperationMetadataSchema(BaseModel):
    """
    Shared optional metadata for stock-changing operations.
    """

    occurred_at: datetime | None = None

    reference_type: str | None = Field(
        default=None,
        max_length=50,
    )

    reference_id: str | None = Field(
        default=None,
        max_length=120,
    )

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    details: dict[str, Any] = Field(
        default_factory=dict,
    )

    @field_validator(
        "occurred_at",
        mode="after",
    )
    @classmethod
    def validate_occurred_at(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        """
        Require timezone-aware operation timestamps.
        """

        if (
            value is not None
            and (
                value.tzinfo is None
                or value.utcoffset() is None
            )
        ):
            raise ValueError(
                "occurred_at must include a timezone."
            )

        return value

    @field_validator(
        "reference_type",
        "reference_id",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """
        Convert blank optional strings to null.
        """

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value


class ReceiveInventoryStockSchema(
    InventoryOperationMetadataSchema
):
    """
    Receive purchased stock or establish an opening balance.
    """

    item_id: uuid.UUID
    location_id: uuid.UUID

    quantity: Decimal = Field(
        gt=0,
        max_digits=16,
        decimal_places=3,
    )

    unit_cost: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=4,
    )

    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
    )

    movement_type: InventoryReceiptType = "receipt"

    @field_validator(
        "currency",
        mode="before",
    )
    @classmethod
    def normalize_currency(
        cls,
        value: object,
    ) -> object:
        """
        Normalize optional receipt currency codes.
        """

        if isinstance(value, str):
            normalized = value.strip().upper()

            if (
                len(normalized) != 3
                or not normalized.isalpha()
            ):
                raise ValueError(
                    "Currency must contain three letters."
                )

            return normalized

        return value


class IssueInventoryStockSchema(
    InventoryOperationMetadataSchema
):
    """
    Issue available stock from one location.
    """

    item_id: uuid.UUID
    location_id: uuid.UUID
    work_order_id: uuid.UUID | None = None

    quantity: Decimal = Field(
        gt=0,
        max_digits=16,
        decimal_places=3,
    )


class ReturnInventoryStockSchema(
    InventoryOperationMetadataSchema
):
    """
    Return previously issued stock to a location.
    """

    item_id: uuid.UUID
    location_id: uuid.UUID
    work_order_id: uuid.UUID | None = None

    quantity: Decimal = Field(
        gt=0,
        max_digits=16,
        decimal_places=3,
    )

    unit_cost: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=4,
    )

    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
    )

    @field_validator(
        "currency",
        mode="before",
    )
    @classmethod
    def normalize_currency(
        cls,
        value: object,
    ) -> object:
        """
        Normalize optional return currency codes.
        """

        if isinstance(value, str):
            normalized = value.strip().upper()

            if (
                len(normalized) != 3
                or not normalized.isalpha()
            ):
                raise ValueError(
                    "Currency must contain three letters."
                )

            return normalized

        return value


class AdjustInventoryStockSchema(
    InventoryOperationMetadataSchema
):
    """
    Increase or decrease an item-location balance by a delta.
    """

    item_id: uuid.UUID
    location_id: uuid.UUID

    quantity_delta: Decimal = Field(
        max_digits=16,
        decimal_places=3,
    )

    unit_cost: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=4,
    )

    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
    )

    @field_validator(
        "quantity_delta",
        mode="after",
    )
    @classmethod
    def validate_quantity_delta(
        cls,
        value: Decimal,
    ) -> Decimal:
        """
        Reject zero-value stock adjustments.
        """

        if value == 0:
            raise ValueError(
                "quantity_delta cannot be zero."
            )

        return value

    @field_validator(
        "currency",
        mode="before",
    )
    @classmethod
    def normalize_currency(
        cls,
        value: object,
    ) -> object:
        """
        Normalize optional adjustment currency codes.
        """

        if isinstance(value, str):
            normalized = value.strip().upper()

            if (
                len(normalized) != 3
                or not normalized.isalpha()
            ):
                raise ValueError(
                    "Currency must contain three letters."
                )

            return normalized

        return value


class TransferInventoryStockSchema(
    InventoryOperationMetadataSchema
):
    """
    Transfer available stock between two locations.
    """

    item_id: uuid.UUID
    source_location_id: uuid.UUID
    destination_location_id: uuid.UUID
    work_order_id: uuid.UUID | None = None

    quantity: Decimal = Field(
        gt=0,
        max_digits=16,
        decimal_places=3,
    )


class CreateInventoryReservationSchema(BaseModel):
    """
    Reserve available stock for a work order.
    """

    item_id: uuid.UUID
    location_id: uuid.UUID
    work_order_id: uuid.UUID

    quantity: Decimal = Field(
        gt=0,
        max_digits=16,
        decimal_places=3,
    )

    expires_at: datetime | None = None

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    details: dict[str, Any] = Field(
        default_factory=dict,
    )

    @field_validator(
        "expires_at",
        mode="after",
    )
    @classmethod
    def validate_expires_at(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        """
        Require timezone-aware reservation expiry timestamps.
        """

        if (
            value is not None
            and (
                value.tzinfo is None
                or value.utcoffset() is None
            )
        ):
            raise ValueError(
                "expires_at must include a timezone."
            )

        return value

    @field_validator(
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_notes(
        cls,
        value: object,
    ) -> object:
        """
        Convert blank reservation notes to null.
        """

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value


class ConsumeInventoryReservationSchema(BaseModel):
    """
    Consume some or all remaining reserved stock.
    """

    quantity: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=16,
        decimal_places=3,
    )

    occurred_at: datetime | None = None

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    details: dict[str, Any] = Field(
        default_factory=dict,
    )

    @field_validator(
        "occurred_at",
        mode="after",
    )
    @classmethod
    def validate_occurred_at(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        """
        Require a timezone-aware consumption timestamp.
        """

        if (
            value is not None
            and (
                value.tzinfo is None
                or value.utcoffset() is None
            )
        ):
            raise ValueError(
                "occurred_at must include a timezone."
            )

        return value

    @field_validator(
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_notes(
        cls,
        value: object,
    ) -> object:
        """
        Convert blank consumption notes to null.
        """

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value


class ReleaseInventoryReservationSchema(BaseModel):
    """
    Release all unconsumed stock held by a reservation.
    """

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    details: dict[str, Any] = Field(
        default_factory=dict,
    )

    @field_validator(
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_notes(
        cls,
        value: object,
    ) -> object:
        """
        Convert blank release notes to null.
        """

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value


class InventoryMovementResponse(BaseModel):
    """
    Immutable stock-movement ledger entry.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    organization_id: uuid.UUID
    item_id: uuid.UUID
    location_id: uuid.UUID
    work_order_id: uuid.UUID | None
    reservation_id: uuid.UUID | None

    movement_type: InventoryMovementType

    quantity: Decimal
    quantity_delta: Decimal
    quantity_before: Decimal
    quantity_after: Decimal

    unit_cost: Decimal | None
    currency: str

    reference_type: str | None
    reference_id: str | None
    transfer_group_id: uuid.UUID | None

    occurred_at: datetime
    notes: str | None
    created_by_user_id: uuid.UUID | None
    details: dict[str, Any]

    item: InventoryItemSummary
    location: InventoryLocationSummary

    created_at: datetime
    updated_at: datetime


class InventoryMovementListResponse(BaseModel):
    """
    Paginated immutable movement-ledger collection.
    """

    items: list[InventoryMovementResponse]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1)


class InventoryReservationResponse(BaseModel):
    """
    Work-order stock reservation returned by the API.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    organization_id: uuid.UUID
    item_id: uuid.UUID
    location_id: uuid.UUID
    work_order_id: uuid.UUID

    quantity_reserved: Decimal
    quantity_consumed: Decimal
    remaining_quantity: Decimal
    status: InventoryReservationStatus

    reserved_at: datetime
    expires_at: datetime | None
    released_at: datetime | None
    consumed_at: datetime | None

    notes: str | None
    created_by_user_id: uuid.UUID | None
    updated_by_user_id: uuid.UUID | None
    details: dict[str, Any]
    is_active: bool

    item: InventoryItemSummary
    location: InventoryLocationSummary

    created_at: datetime
    updated_at: datetime


class InventoryReservationListResponse(BaseModel):
    """
    Paginated stock-reservation collection.
    """

    items: list[InventoryReservationResponse]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1)


class InventoryStockOperationResponse(BaseModel):
    """
    Result of a one-location stock mutation.
    """

    movement: InventoryMovementResponse
    balance: InventoryBalanceResponse


class InventoryTransferResponse(BaseModel):
    """
    Result of an atomic two-location stock transfer.
    """

    transfer_group_id: uuid.UUID
    outbound_movement: InventoryMovementResponse
    inbound_movement: InventoryMovementResponse
    source_balance: InventoryBalanceResponse
    destination_balance: InventoryBalanceResponse


class InventoryReservationOperationResponse(BaseModel):
    """
    Reservation state plus the affected item-location balance.
    """

    reservation: InventoryReservationResponse
    balance: InventoryBalanceResponse


class InventoryReservationConsumptionResponse(BaseModel):
    """
    Reservation consumption result and immutable issue movement.
    """

    reservation: InventoryReservationResponse
    movement: InventoryMovementResponse
    balance: InventoryBalanceResponse
