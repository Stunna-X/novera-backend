"""
Role and permission schemas.

Defines API response models for organization roles,
permissions, and the authenticated member's access context.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PermissionResponse(BaseModel):
    """
    Permission returned by the API.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    name: str
    description: str | None = None


class RoleSummaryResponse(BaseModel):
    """
    Lightweight role representation.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    name: str
    description: str | None = None
    is_system: bool


class RoleResponse(RoleSummaryResponse):
    """
    Complete role representation including permissions.
    """

    permissions: list[PermissionResponse] = Field(
        default_factory=list,
    )


class MembershipAccessResponse(BaseModel):
    """
    Current user's access within one organization.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    membership_id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID

    role: RoleResponse

    permission_names: list[str] = Field(
        default_factory=list,
    )

    created_at: datetime
    updated_at: datetime


class OrganizationAccessResponse(BaseModel):
    """
    Complete access information required by the frontend.

    Includes the current membership, assigned role,
    granted permissions, and roles available for assignment.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    membership: MembershipAccessResponse

    available_roles: list[RoleSummaryResponse] = Field(
        default_factory=list,
    )