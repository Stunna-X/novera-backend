"""
Customer site schemas.

Defines request validation and API responses for
customer operational locations.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


class CustomerSiteBaseSchema(BaseModel):
    """
    Shared customer-site fields.
    """

    name: str = Field(
        min_length=1,
        max_length=160,
    )

    site_code: str | None = Field(
        default=None,
        max_length=50,
    )

    site_type: str | None = Field(
        default=None,
        max_length=50,
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

    address_line_1: str = Field(
        min_length=1,
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

    latitude: Decimal | None = Field(
        default=None,
        ge=Decimal("-90"),
        le=Decimal("90"),
    )

    longitude: Decimal | None = Field(
        default=None,
        ge=Decimal("-180"),
        le=Decimal("180"),
    )

    access_instructions: str | None = Field(
        default=None,
        max_length=5000,
    )

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    @field_validator(
        "name",
        "address_line_1",
        mode="before",
    )
    @classmethod
    def normalize_required_text(
        cls,
        value: object,
    ) -> object:
        """
        Strip required text and reject blank values.
        """

        if isinstance(value, str):
            normalized_value = value.strip()

            if not normalized_value:
                raise ValueError(
                    "This field cannot be empty."
                )

            return normalized_value

        return value

    @field_validator(
        "site_code",
        "site_type",
        "contact_name",
        "phone",
        "address_line_2",
        "city",
        "state",
        "postal_code",
        "country",
        "access_instructions",
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
            normalized_value = value.strip()

            return normalized_value or None

        return value

    @field_validator(
        "email",
        mode="before",
    )
    @classmethod
    def normalize_email(
        cls,
        value: object,
    ) -> object:
        """
        Normalize the optional email address.
        """

        if isinstance(value, str):
            normalized_value = value.strip().lower()

            return normalized_value or None

        return value

    @field_validator(
        "site_code",
        mode="after",
    )
    @classmethod
    def normalize_site_code(
        cls,
        value: str | None,
    ) -> str | None:
        """
        Normalize site codes to uppercase.
        """

        return value.upper() if value else None


class CreateCustomerSiteSchema(CustomerSiteBaseSchema):
    """
    Payload used to create a customer site.
    """

    pass


class UpdateCustomerSiteSchema(BaseModel):
    """
    Payload used to update selected site fields.
    """

    name: str | None = Field(
        default=None,
        max_length=160,
    )

    site_code: str | None = Field(
        default=None,
        max_length=50,
    )

    site_type: str | None = Field(
        default=None,
        max_length=50,
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

    latitude: Decimal | None = Field(
        default=None,
        ge=Decimal("-90"),
        le=Decimal("90"),
    )

    longitude: Decimal | None = Field(
        default=None,
        ge=Decimal("-180"),
        le=Decimal("180"),
    )

    access_instructions: str | None = Field(
        default=None,
        max_length=5000,
    )

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    @field_validator(
        "name",
        "address_line_1",
        mode="before",
    )
    @classmethod
    def normalize_required_text(
        cls,
        value: object,
    ) -> object:
        """
        Reject blank required values when supplied.
        """

        if isinstance(value, str):
            normalized_value = value.strip()

            if not normalized_value:
                raise ValueError(
                    "This field cannot be empty."
                )

            return normalized_value

        return value

    @field_validator(
        "site_code",
        "site_type",
        "contact_name",
        "phone",
        "address_line_2",
        "city",
        "state",
        "postal_code",
        "country",
        "access_instructions",
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
            normalized_value = value.strip()

            return normalized_value or None

        return value

    @field_validator(
        "email",
        mode="before",
    )
    @classmethod
    def normalize_email(
        cls,
        value: object,
    ) -> object:
        """
        Normalize the optional email address.
        """

        if isinstance(value, str):
            normalized_value = value.strip().lower()

            return normalized_value or None

        return value

    @field_validator(
        "site_code",
        mode="after",
    )
    @classmethod
    def normalize_site_code(
        cls,
        value: str | None,
    ) -> str | None:
        """
        Normalize site codes to uppercase.
        """

        return value.upper() if value else None


class CustomerSiteResponse(BaseModel):
    """
    Customer site returned by the API.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID

    name: str
    site_code: str | None = None
    site_type: str | None = None

    contact_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None

    address_line_1: str
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None

    latitude: Decimal | None = None
    longitude: Decimal | None = None

    access_instructions: str | None = None
    notes: str | None = None

    is_active: bool

    created_at: datetime
    updated_at: datetime


class CustomerSiteListResponse(BaseModel):
    """
    Paginated customer-site collection.
    """

    items: list[CustomerSiteResponse] = Field(
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