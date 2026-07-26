"""
Organization document-settings schemas.

Defines the protected tax, banking, payment, invoice, and quote
configuration used when generating business documents.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class UpdateOrganizationDocumentSettingsSchema(BaseModel):
    """
    Partially update organization document settings.

    Explicit null values clear existing settings. Omitted values remain
    unchanged.
    """

    model_config = ConfigDict(extra="forbid")

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


class OrganizationDocumentSettingsResponse(BaseModel):
    """
    Protected organization document-settings response.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    organization_id: uuid.UUID
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
    updated_at: datetime
