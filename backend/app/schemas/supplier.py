"""
Supplier schemas.

Defines validation and response models for organization-scoped
supplier records.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


SupplierType = Literal[
    "company",
    "individual",
]


OPTIONAL_TEXT_FIELDS = (
    "category",
    "contact_name",
    "phone",
    "alternate_phone",
    "address_line_1",
    "address_line_2",
    "city",
    "state",
    "postal_code",
    "country",
    "notes",
)

IDENTIFIER_FIELDS = (
    "tax_id",
    "registration_number",
)


class SupplierBaseSchema(BaseModel):
    """Shared supplier fields."""

    code: str = Field(
        min_length=1,
        max_length=50,
    )

    name: str = Field(
        min_length=1,
        max_length=180,
    )

    supplier_type: SupplierType = "company"

    category: str | None = Field(
        default=None,
        max_length=120,
    )

    contact_name: str | None = Field(
        default=None,
        max_length=160,
    )

    email: EmailStr | None = None

    phone: str | None = Field(
        default=None,
        max_length=50,
    )

    alternate_phone: str | None = Field(
        default=None,
        max_length=50,
    )

    tax_id: str | None = Field(
        default=None,
        max_length=80,
    )

    registration_number: str | None = Field(
        default=None,
        max_length=100,
    )

    payment_terms_days: int = Field(
        default=0,
        ge=0,
        le=3650,
    )

    currency: str = Field(
        default="NGN",
        min_length=3,
        max_length=3,
    )

    address_line_1: str | None = Field(
        default=None,
        max_length=255,
    )

    address_line_2: str | None = Field(
        default=None,
        max_length=255,
    )

    city: str | None = Field(
        default=None,
        max_length=100,
    )

    state: str | None = Field(
        default=None,
        max_length=100,
    )

    postal_code: str | None = Field(
        default=None,
        max_length=30,
    )

    country: str | None = Field(
        default=None,
        max_length=100,
    )

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    details: dict[str, object] = Field(
        default_factory=dict,
    )

    @field_validator(
        "code",
        mode="before",
    )
    @classmethod
    def normalize_code(cls, value: object) -> object:
        """Normalize supplier codes."""

        if isinstance(value, str):
            normalized = value.strip().upper()

            if not normalized:
                raise ValueError(
                    "Supplier code cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "name",
        mode="before",
    )
    @classmethod
    def normalize_name(cls, value: object) -> object:
        """Normalize supplier names."""

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Supplier name cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        *OPTIONAL_TEXT_FIELDS,
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        """Convert blank optional text values to null."""

        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None

        return value

    @field_validator(
        *IDENTIFIER_FIELDS,
        mode="before",
    )
    @classmethod
    def normalize_identifier(cls, value: object) -> object:
        """Normalize optional supplier identifiers."""

        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or None

        return value

    @field_validator(
        "email",
        mode="before",
    )
    @classmethod
    def normalize_email(cls, value: object) -> object:
        """Normalize supplier email addresses."""

        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized or None

        return value

    @field_validator(
        "supplier_type",
        mode="before",
    )
    @classmethod
    def normalize_supplier_type(cls, value: object) -> object:
        """Normalize supplier types."""

        if isinstance(value, str):
            return value.strip().lower()

        return value

    @field_validator(
        "currency",
        mode="before",
    )
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        """Normalize and validate ISO-style currency codes."""

        if isinstance(value, str):
            normalized = value.strip().upper()

            if len(normalized) != 3 or not normalized.isalpha():
                raise ValueError(
                    "Currency must be a three-letter code."
                )

            return normalized

        return value


class CreateSupplierSchema(SupplierBaseSchema):
    """Payload used to create a supplier."""

    pass


class UpdateSupplierSchema(BaseModel):
    """Payload used to partially update a supplier."""

    code: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=180,
    )

    supplier_type: SupplierType | None = None

    category: str | None = Field(
        default=None,
        max_length=120,
    )

    contact_name: str | None = Field(
        default=None,
        max_length=160,
    )

    email: EmailStr | None = None

    phone: str | None = Field(
        default=None,
        max_length=50,
    )

    alternate_phone: str | None = Field(
        default=None,
        max_length=50,
    )

    tax_id: str | None = Field(
        default=None,
        max_length=80,
    )

    registration_number: str | None = Field(
        default=None,
        max_length=100,
    )

    payment_terms_days: int | None = Field(
        default=None,
        ge=0,
        le=3650,
    )

    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
    )

    address_line_1: str | None = Field(
        default=None,
        max_length=255,
    )

    address_line_2: str | None = Field(
        default=None,
        max_length=255,
    )

    city: str | None = Field(
        default=None,
        max_length=100,
    )

    state: str | None = Field(
        default=None,
        max_length=100,
    )

    postal_code: str | None = Field(
        default=None,
        max_length=30,
    )

    country: str | None = Field(
        default=None,
        max_length=100,
    )

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    details: dict[str, object] = Field(
        default_factory=dict,
    )

    @field_validator(
        "code",
        "name",
        "supplier_type",
        "payment_terms_days",
        "currency",
        mode="before",
    )
    @classmethod
    def reject_null_required_fields(
        cls,
        value: object,
    ) -> object:
        """Reject explicit nulls for non-null database fields."""

        if value is None:
            raise ValueError(
                "This supplier field cannot be null."
            )

        return value

    @field_validator(
        "code",
        mode="before",
    )
    @classmethod
    def normalize_code(cls, value: object) -> object:
        """Normalize a supplied supplier code."""

        if isinstance(value, str):
            normalized = value.strip().upper()

            if not normalized:
                raise ValueError(
                    "Supplier code cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "name",
        mode="before",
    )
    @classmethod
    def normalize_name(cls, value: object) -> object:
        """Normalize a supplied supplier name."""

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Supplier name cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        *OPTIONAL_TEXT_FIELDS,
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        """Convert blank optional text values to null."""

        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None

        return value

    @field_validator(
        *IDENTIFIER_FIELDS,
        mode="before",
    )
    @classmethod
    def normalize_identifier(cls, value: object) -> object:
        """Normalize supplied supplier identifiers."""

        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or None

        return value

    @field_validator(
        "email",
        mode="before",
    )
    @classmethod
    def normalize_email(cls, value: object) -> object:
        """Normalize a supplied supplier email."""

        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized or None

        return value

    @field_validator(
        "supplier_type",
        mode="before",
    )
    @classmethod
    def normalize_supplier_type(cls, value: object) -> object:
        """Normalize a supplied supplier type."""

        if isinstance(value, str):
            return value.strip().lower()

        return value

    @field_validator(
        "currency",
        mode="before",
    )
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        """Normalize a supplied currency code."""

        if isinstance(value, str):
            normalized = value.strip().upper()

            if len(normalized) != 3 or not normalized.isalpha():
                raise ValueError(
                    "Currency must be a three-letter code."
                )

            return normalized

        return value


class SupplierResponse(BaseModel):
    """Supplier returned by the API."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    organization_id: uuid.UUID

    code: str
    name: str
    supplier_type: SupplierType
    category: str | None = None

    contact_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    alternate_phone: str | None = None

    tax_id: str | None = None
    registration_number: str | None = None
    payment_terms_days: int
    currency: str

    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None

    notes: str | None = None
    details: dict[str, object]
    is_active: bool

    created_at: datetime
    updated_at: datetime


class SupplierListResponse(BaseModel):
    """Paginated supplier collection returned by the API."""

    items: list[SupplierResponse] = Field(
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
