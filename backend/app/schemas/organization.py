"""
Organization schemas.

Defines request and response models for organization operations.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.enums.industry import Industry


class CreateOrganizationSchema(BaseModel):
    """
    Request body for creating an organization.
    """

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


class UpdateOrganizationSchema(BaseModel):
    """
    Request body for updating an organization.

    Every field is optional so only supplied values are changed.
    """

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
    Public organization response.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID

    name: str

    slug: str

    industry: Industry | None

    email: EmailStr | None

    phone: str | None

    country: str | None

    timezone: str

    logo_url: str | None

    is_active: bool