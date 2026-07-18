"""
Organization schemas.

Defines request and response models for organizations.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.enums.industry import Industry


class CreateOrganizationSchema(BaseModel):
    """
    Request body for creating an organization.
    """

    name: str = Field(min_length=2, max_length=255)
    industry: Industry | None = None
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    country: str | None = Field(default=None, max_length=100)
    timezone: str = Field(
        default="UTC",
        min_length=1,
        max_length=100,
    )
    logo_url: str | None = Field(default=None, max_length=500)

    business_address: str | None = Field(default=None, max_length=2000)
    tax_identification_number: str | None = Field(default=None, max_length=100)
    vat_number: str | None = Field(default=None, max_length=100)
    bank_name: str | None = Field(default=None, max_length=200)
    bank_account_name: str | None = Field(default=None, max_length=200)
    bank_account_number: str | None = Field(default=None, max_length=100)
    bank_routing_number: str | None = Field(default=None, max_length=100)
    payment_instructions: str | None = Field(default=None, max_length=2000)
    default_invoice_terms: str | None = Field(default=None, max_length=2000)
    default_quote_terms: str | None = Field(default=None, max_length=2000)
    invoice_footer: str | None = Field(default=None, max_length=2000)
    quote_footer: str | None = Field(default=None, max_length=2000)


class UpdateOrganizationSchema(BaseModel):
    """
    Request body for updating an organization.
    """

    name: str | None = Field(default=None, min_length=2, max_length=255)
    industry: Industry | None = None
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    country: str | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, min_length=1, max_length=100)
    logo_url: str | None = Field(default=None, max_length=500)

    business_address: str | None = Field(default=None, max_length=2000)
    tax_identification_number: str | None = Field(default=None, max_length=100)
    vat_number: str | None = Field(default=None, max_length=100)
    bank_name: str | None = Field(default=None, max_length=200)
    bank_account_name: str | None = Field(default=None, max_length=200)
    bank_account_number: str | None = Field(default=None, max_length=100)
    bank_routing_number: str | None = Field(default=None, max_length=100)
    payment_instructions: str | None = Field(default=None, max_length=2000)
    default_invoice_terms: str | None = Field(default=None, max_length=2000)
    default_quote_terms: str | None = Field(default=None, max_length=2000)
    invoice_footer: str | None = Field(default=None, max_length=2000)
    quote_footer: str | None = Field(default=None, max_length=2000)


class OrganizationResponse(BaseModel):
    """
    Public organization response.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    industry: Industry | None
    email: str | None
    phone: str | None
    country: str | None
    timezone: str
    logo_url: str | None

    business_address: str | None
    tax_identification_number: str | None
    vat_number: str | None
    bank_name: str | None
    bank_account_name: str | None
    bank_account_number: str | None
    bank_routing_number: str | None
    payment_instructions: str | None
    default_invoice_terms: str | None
    default_quote_terms: str | None
    invoice_footer: str | None
    quote_footer: str | None

    is_active: bool
    created_at: datetime
    updated_at: datetime
