"""
Customer schemas.

Defines validation and response models for organization-scoped
customer records.
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


CustomerType = Literal[
    "business",
    "individual",
]


class CustomerBaseSchema(BaseModel):
    """
    Shared customer fields.
    """

    name: str = Field(
        min_length=1,
        max_length=160,
    )

    customer_type: CustomerType = "business"

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
        Strip surrounding whitespace from the customer name.
        """

        if isinstance(value, str):
            normalized_value = value.strip()

            if not normalized_value:
                raise ValueError(
                    "Customer name cannot be empty."
                )

            return normalized_value

        return value

    @field_validator(
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
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """
        Convert blank optional text values to None.
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
        Normalize customer email addresses.
        """

        if isinstance(value, str):
            normalized_value = value.strip().lower()

            return normalized_value or None

        return value

    @field_validator(
        "customer_type",
        mode="before",
    )
    @classmethod
    def normalize_customer_type(
        cls,
        value: object,
    ) -> object:
        """
        Normalize customer type values.
        """

        if isinstance(value, str):
            return value.strip().lower()

        return value


class CreateCustomerSchema(CustomerBaseSchema):
    """
    Payload used to create a customer.
    """

    pass


class UpdateCustomerSchema(BaseModel):
    """
    Payload used to update a customer.

    Only supplied fields are changed.
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=160,
    )

    customer_type: CustomerType | None = None

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
        Strip the supplied customer name.
        """

        if isinstance(value, str):
            normalized_value = value.strip()

            if not normalized_value:
                raise ValueError(
                    "Customer name cannot be empty."
                )

            return normalized_value

        return value

    @field_validator(
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
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """
        Convert blank optional text values to None.
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
        Normalize the supplied email address.
        """

        if isinstance(value, str):
            normalized_value = value.strip().lower()

            return normalized_value or None

        return value

    @field_validator(
        "customer_type",
        mode="before",
    )
    @classmethod
    def normalize_customer_type(
        cls,
        value: object,
    ) -> object:
        """
        Normalize the supplied customer type.
        """

        if isinstance(value, str):
            return value.strip().lower()

        return value


class CustomerResponse(BaseModel):
    """
    Customer returned by the API.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    organization_id: uuid.UUID

    name: str
    customer_type: CustomerType

    contact_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    alternate_phone: str | None = None

    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None

    notes: str | None = None
    is_active: bool

    created_at: datetime
    updated_at: datetime


class CustomerListResponse(BaseModel):
    """
    Paginated customer collection returned by the API.
    """

    items: list[CustomerResponse] = Field(
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