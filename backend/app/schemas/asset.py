"""
Asset schemas.

Defines request validation and API responses for
organization operational assets.
"""

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
)


AssetType = Literal[
    "equipment",
    "vehicle",
    "machine",
    "tool",
    "generator",
    "pump",
    "other",
]

AssetStatus = Literal[
    "available",
    "in_use",
    "maintenance",
    "unavailable",
    "retired",
]

AssetCondition = Literal[
    "excellent",
    "good",
    "fair",
    "poor",
    "damaged",
]


class AssetBaseSchema(BaseModel):
    """
    Shared asset fields.
    """

    asset_code: str = Field(
        min_length=1,
        max_length=50,
    )

    name: str = Field(
        min_length=1,
        max_length=160,
    )

    asset_type: AssetType = "equipment"

    category: str | None = Field(
        default=None,
        max_length=100,
    )

    manufacturer: str | None = Field(
        default=None,
        max_length=120,
    )

    model_number: str | None = Field(
        default=None,
        max_length=100,
    )

    serial_number: str | None = Field(
        default=None,
        max_length=120,
    )

    registration_number: str | None = Field(
        default=None,
        max_length=100,
    )

    year_of_manufacture: int | None = Field(
        default=None,
        ge=1900,
        le=2100,
    )

    purchase_date: date | None = None

    purchase_cost: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        decimal_places=2,
    )

    status: AssetStatus = "available"

    condition: AssetCondition = "good"

    location: str | None = Field(
        default=None,
        max_length=255,
    )

    last_service_date: date | None = None

    next_service_date: date | None = None

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    @field_validator(
        "asset_code",
        mode="before",
    )
    @classmethod
    def normalize_asset_code(
        cls,
        value: object,
    ) -> object:
        """
        Normalize asset codes to uppercase.
        """

        if isinstance(value, str):
            normalized = value.strip().upper()

            if not normalized:
                raise ValueError(
                    "Asset code cannot be empty."
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
        Strip and validate the asset name.
        """

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Asset name cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "category",
        "manufacturer",
        "model_number",
        "serial_number",
        "registration_number",
        "location",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """
        Convert blank optional values to None.
        """

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value

    @field_validator(
        "serial_number",
        "registration_number",
        mode="after",
    )
    @classmethod
    def normalize_identifiers(
        cls,
        value: str | None,
    ) -> str | None:
        """
        Normalize equipment identifiers to uppercase.
        """

        return value.upper() if value else None

    @field_validator(
        "asset_type",
        "status",
        "condition",
        mode="before",
    )
    @classmethod
    def normalize_choice_values(
        cls,
        value: object,
    ) -> object:
        """
        Normalize controlled text values.
        """

        if isinstance(value, str):
            return value.strip().lower()

        return value


class CreateAssetSchema(AssetBaseSchema):
    """
    Payload used to create an asset.
    """

    pass


class UpdateAssetSchema(BaseModel):
    """
    Payload used to update selected asset fields.
    """

    asset_code: str | None = Field(
        default=None,
        max_length=50,
    )

    name: str | None = Field(
        default=None,
        max_length=160,
    )

    asset_type: AssetType | None = None

    category: str | None = Field(
        default=None,
        max_length=100,
    )

    manufacturer: str | None = Field(
        default=None,
        max_length=120,
    )

    model_number: str | None = Field(
        default=None,
        max_length=100,
    )

    serial_number: str | None = Field(
        default=None,
        max_length=120,
    )

    registration_number: str | None = Field(
        default=None,
        max_length=100,
    )

    year_of_manufacture: int | None = Field(
        default=None,
        ge=1900,
        le=2100,
    )

    purchase_date: date | None = None

    purchase_cost: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        decimal_places=2,
    )

    status: AssetStatus | None = None

    condition: AssetCondition | None = None

    location: str | None = Field(
        default=None,
        max_length=255,
    )

    last_service_date: date | None = None

    next_service_date: date | None = None

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    @field_validator(
        "asset_code",
        mode="before",
    )
    @classmethod
    def normalize_asset_code(
        cls,
        value: object,
    ) -> object:
        """
        Normalize supplied asset codes.
        """

        if isinstance(value, str):
            normalized = value.strip().upper()

            if not normalized:
                raise ValueError(
                    "Asset code cannot be empty."
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
        Validate the supplied asset name.
        """

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Asset name cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "category",
        "manufacturer",
        "model_number",
        "serial_number",
        "registration_number",
        "location",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """
        Convert blank optional values to None.
        """

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value

    @field_validator(
        "serial_number",
        "registration_number",
        mode="after",
    )
    @classmethod
    def normalize_identifiers(
        cls,
        value: str | None,
    ) -> str | None:
        """
        Normalize equipment identifiers to uppercase.
        """

        return value.upper() if value else None

    @field_validator(
        "asset_type",
        "status",
        "condition",
        mode="before",
    )
    @classmethod
    def normalize_choice_values(
        cls,
        value: object,
    ) -> object:
        """
        Normalize controlled text values.
        """

        if isinstance(value, str):
            return value.strip().lower()

        return value


class AssetResponse(BaseModel):
    """
    Asset returned by the API.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    organization_id: uuid.UUID

    asset_code: str
    name: str
    asset_type: AssetType

    category: str | None = None
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    registration_number: str | None = None

    year_of_manufacture: int | None = None

    purchase_date: date | None = None
    purchase_cost: Decimal | None = None

    status: AssetStatus
    condition: AssetCondition

    location: str | None = None

    last_service_date: date | None = None
    next_service_date: date | None = None

    notes: str | None = None

    is_active: bool

    created_at: datetime
    updated_at: datetime


class AssetListResponse(BaseModel):
    """
    Paginated asset collection.
    """

    items: list[AssetResponse] = Field(
        default_factory=list,
    )

    total: int = Field(
        ge=0,
    )

    skip: int = Field(
        ge=0,
    )

    limit: int = Field(
        ge=1,
    )