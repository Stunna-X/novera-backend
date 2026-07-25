"""
Shared API dependencies.

Provides organization context and permission-based authorization
for organization-scoped endpoints.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.role import Role
from app.models.user import User


@dataclass(frozen=True)
class OrganizationContext:
    """
    Authenticated user's context within an organization.
    """

    organization: Organization
    membership: Membership
    current_user: User

    @property
    def role(self) -> Role:
        """
        Return the user's assigned organization role.
        """

        return self.membership.role

    @property
    def permission_names(self) -> set[str]:
        """
        Return normalized permission names assigned to the role.
        """

        return {
            permission.name.strip().lower()
            for permission in self.role.permissions
        }


def get_organization_context(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizationContext:
    """
    Load the current user's membership and authorization context.

    A 404 response is returned when the organization does not exist
    or the authenticated user does not belong to it. This prevents
    exposing the existence of organizations to unrelated users.
    """

    membership = (
        db.query(Membership)
        .options(
            joinedload(Membership.organization),
            joinedload(Membership.user),
            joinedload(Membership.role).options(
                selectinload(Role.permissions),
            ),
        )
        .filter(
            Membership.organization_id == organization_id,
            Membership.user_id == current_user.id,
        )
        .first()
    )

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    organization = membership.organization

    if not organization.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This organization is inactive.",
        )

    return OrganizationContext(
        organization=organization,
        membership=membership,
        current_user=current_user,
    )


def require_permission(
    permission_name: str,
) -> Callable[..., OrganizationContext]:
    """
    Create a dependency requiring one specific permission.

    Example:

        context: OrganizationContext = Depends(
            require_permission("customers.create")
        )
    """

    normalized_permission = permission_name.strip().lower()

    if not normalized_permission:
        raise ValueError(
            "A permission name must be provided."
        )

    def permission_dependency(
        context: OrganizationContext = Depends(
            get_organization_context
        ),
    ) -> OrganizationContext:
        if normalized_permission not in context.permission_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You do not have permission to perform "
                    "this action."
                ),
            )

        return context

    return permission_dependency


def require_any_permission(
    *permission_names: str,
) -> Callable[..., OrganizationContext]:
    """
    Create a dependency requiring at least one permission.

    Example:

        context: OrganizationContext = Depends(
            require_any_permission(
                "work_orders.update",
                "work_orders.update_status",
            )
        )
    """

    normalized_permissions = {
        permission_name.strip().lower()
        for permission_name in permission_names
        if permission_name.strip()
    }

    if not normalized_permissions:
        raise ValueError(
            "At least one permission name must be provided."
        )

    def permission_dependency(
        context: OrganizationContext = Depends(
            get_organization_context
        ),
    ) -> OrganizationContext:
        if context.permission_names.isdisjoint(
            normalized_permissions
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You do not have permission to perform "
                    "this action."
                ),
            )

        return context

    return permission_dependency


def require_all_permissions(
    *permission_names: str,
) -> Callable[..., OrganizationContext]:
    """
    Create a dependency requiring every supplied permission.
    """

    normalized_permissions = {
        permission_name.strip().lower()
        for permission_name in permission_names
        if permission_name.strip()
    }

    if not normalized_permissions:
        raise ValueError(
            "At least one permission name must be provided."
        )

    def permission_dependency(
        context: OrganizationContext = Depends(
            get_organization_context
        ),
    ) -> OrganizationContext:
        missing_permissions = (
            normalized_permissions
            - context.permission_names
        )

        if missing_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You do not have permission to perform "
                    "this action."
                ),
            )

        return context

    return permission_dependency
