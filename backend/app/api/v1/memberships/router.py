"""
Membership routes.

Provides authenticated endpoints for managing organization members
and their assigned roles.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import (
    OrganizationContext,
    require_all_permissions,
    require_permission,
)
from app.database.session import get_db
from app.models.membership import Membership
from app.schemas.membership import (
    AddOrganizationMemberSchema,
    MembershipResponse,
    UpdateMembershipRoleSchema,
)
from app.services.membership_service import MembershipService


router = APIRouter(
    prefix="/organizations/{organization_id}/members",
    tags=["Organization Members"],
)


@router.post(
    "",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add organization member",
)
def add_member(
    organization_id: uuid.UUID,
    payload: AddOrganizationMemberSchema,
    context: OrganizationContext = Depends(
        require_all_permissions(
            "memberships.create",
            "roles.assign",
        )
    ),
    db: Session = Depends(get_db),
) -> Membership:
    """
    Add an existing registered Novera user to an organization.

    Requires:
    - memberships.create
    - roles.assign
    """

    service = MembershipService(db)

    return service.add_member(
        organization_id=organization_id,
        payload=payload,
        current_user=context.current_user,
    )


@router.get(
    "",
    response_model=list[MembershipResponse],
    summary="List organization members",
)
def list_members(
    organization_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("memberships.read")
    ),
    db: Session = Depends(get_db),
) -> list[Membership]:
    """
    List every member belonging to an organization.

    Requires:
    - memberships.read
    """

    service = MembershipService(db)

    return service.list_members(
        organization_id=organization_id,
        current_user=context.current_user,
    )


@router.patch(
    "/{membership_id}/role",
    response_model=MembershipResponse,
    summary="Update member role",
)
def update_member_role(
    organization_id: uuid.UUID,
    membership_id: uuid.UUID,
    payload: UpdateMembershipRoleSchema,
    context: OrganizationContext = Depends(
        require_all_permissions(
            "memberships.update",
            "roles.assign",
        )
    ),
    db: Session = Depends(get_db),
) -> Membership:
    """
    Change the role assigned to an organization member.

    Requires:
    - memberships.update
    - roles.assign
    """

    service = MembershipService(db)

    return service.update_member_role(
        organization_id=organization_id,
        membership_id=membership_id,
        payload=payload,
        current_user=context.current_user,
    )


@router.delete(
    "/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove organization member",
)
def remove_member(
    organization_id: uuid.UUID,
    membership_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("memberships.delete")
    ),
    db: Session = Depends(get_db),
) -> Response:
    """
    Remove a member from an organization.

    Requires:
    - memberships.delete
    """

    service = MembershipService(db)

    service.remove_member(
        organization_id=organization_id,
        membership_id=membership_id,
        current_user=context.current_user,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )