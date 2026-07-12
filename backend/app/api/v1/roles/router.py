"""
Organization access and role routes.

Provides endpoints for retrieving the authenticated user's
organization access context and the roles available within Novera.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import (
    OrganizationContext,
    get_organization_context,
    require_permission,
)
from app.database.session import get_db
from app.models.role import Role
from app.repositories.role import RoleRepository
from app.schemas.role import (
    MembershipAccessResponse,
    OrganizationAccessResponse,
    RoleResponse,
    RoleSummaryResponse,
)


router = APIRouter(
    prefix="/organizations/{organization_id}",
    tags=["Organization Access"],
)


@router.get(
    "/access",
    response_model=OrganizationAccessResponse,
    summary="Get my organization access",
)
def get_organization_access(
    context: OrganizationContext = Depends(
        get_organization_context
    ),
    db: Session = Depends(get_db),
) -> OrganizationAccessResponse:
    """
    Return the authenticated user's organization access context.

    The response includes:

    - Membership information
    - Assigned role
    - Granted permissions
    - Roles available for assignment

    Any active organization member may retrieve their own
    access context.

    Available roles are only included when the member has
    the roles.read permission.
    """

    permission_names = sorted(
        context.permission_names
    )

    role_response = RoleResponse.model_validate(
        context.role
    )

    membership_response = MembershipAccessResponse(
        membership_id=context.membership.id,
        organization_id=context.membership.organization_id,
        user_id=context.membership.user_id,
        role=role_response,
        permission_names=permission_names,
        created_at=context.membership.created_at,
        updated_at=context.membership.updated_at,
    )

    available_roles: list[RoleSummaryResponse] = []

    if "roles.read" in context.permission_names:
        repository = RoleRepository(db)

        roles = repository.list_system_roles()

        available_roles = [
            RoleSummaryResponse.model_validate(role)
            for role in roles
        ]

    return OrganizationAccessResponse(
        membership=membership_response,
        available_roles=available_roles,
    )


@router.get(
    "/roles",
    response_model=list[RoleResponse],
    summary="List organization roles",
)
def list_organization_roles(
    context: OrganizationContext = Depends(
        require_permission("roles.read")
    ),
    db: Session = Depends(get_db),
) -> list[Role]:
    """
    Return every platform-managed organization role
    with its assigned permissions.

    Requires:
    - roles.read
    """

    repository = RoleRepository(db)

    return repository.list_system_roles_with_permissions()