"""
Organization schemas.

Defines request and response models for organizations.
Sensitive document configuration is exposed through its own
permission-protected schema and endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
)

from app.enums.industry import Industry


class CreateOrganizationSchema(BaseModel):
    """
    Request body for creating an organization.

    Document settings may be supplied during initial onboarding.
    They are not returned through the ordinary organization
    response.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=2,
        max_length=255,
    )
    industry: Industry | None = None
    email: EmailStr | None = None
    phone: str | None = Field(
        default=None,
        max_length=50,
    )
    country: str | None = Field(
        default=None,
        max_length=100,
    )
    timezone: str = Field(
        default="UTC",
        min_length=1,
        max_length=100,
    )
    logo_url: str | None = Field(
        default=None,
        max_length=500,
    )

    business_address: str | None = Field(
        default=None,
        max_length=2000,
    )
    tax_identification_number: str | None = Field(
        default=None,
        max_length=100,
    )
    vat_number: str | None = Field(
        default=None,
        max_length=100,
    )
    bank_name: str | None = Field(
        default=None,
        max_length=200,
    )
    bank_account_name: str | None = Field(
        default=None,
        max_length=200,
    )
    bank_account_number: str | None = Field(
        default=None,
        max_length=100,
    )
    bank_routing_number: str | None = Field(
        default=None,
        max_length=100,
    )
    payment_instructions: str | None = Field(
        default=None,
        max_length=2000,
    )
    default_invoice_terms: str | None = Field(
        default=None,
        max_length=2000,
    )
    default_quote_terms: str | None = Field(
        default=None,
        max_length=2000,
    )
    invoice_footer: str | None = Field(
        default=None,
        max_length=2000,
    )
    quote_footer: str | None = Field(
        default=None,
        max_length=2000,
    )


class UpdateOrganizationSchema(BaseModel):
    """
    Request body for updating general organization details.

    Sensitive document and banking settings must be changed through
    the dedicated document-settings endpoint.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=255,
    )
    industry: Industry | None = None
    email: EmailStr | None = None
    phone: str | None = Field(
        default=None,
        max_length=50,
    )
    country: str | None = Field(
        default=None,
        max_length=100,
    )
    timezone: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    logo_url: str | None = Field(
        default=None,
        max_length=500,
    )


class OrganizationResponse(BaseModel):
    """
    Safe organization response for ordinary organization readers.

    Sensitive tax, banking, payment, and document configuration is
    deliberately excluded.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    name: str
    slug: str
    industry: Industry | None
    email: str | None
    phone: str | None
    country: str | None
    timezone: str
    logo_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
