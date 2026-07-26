"""
Membership schemas.

Defines request and response models for organization members
and role assignment.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AddOrganizationMemberSchema(BaseModel):
    """
    Add an existing registered user to an organization.
    """

    email: EmailStr

    role_name: str = Field(
        min_length=2,
        max_length=100,
    )


class UpdateMembershipRoleSchema(BaseModel):
    """
    Change the role assigned to an organization member.
    """

    role_name: str = Field(
        min_length=2,
        max_length=100,
    )


class MembershipUserResponse(BaseModel):
    """
    Basic user details returned with a membership.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID

    first_name: str

    last_name: str

    email: EmailStr

    email_verified: bool

    status: str


class MembershipRoleResponse(BaseModel):
    """
    Role details returned with a membership.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID

    name: str

    description: str | None

    is_system: bool


class MembershipResponse(BaseModel):
    """
    Organization membership response.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID

    organization_id: UUID

    user_id: UUID

    role_id: UUID

    user: MembershipUserResponse

    role: MembershipRoleResponse

    created_at: datetime

    updated_at: datetime