"""
Membership service.

Contains business logic for organization membership management,
including adding users, listing members, assigning roles,
and removing members.

Route dependencies handle permission authorization.
This service protects organization membership invariants,
especially rules involving the Owner role.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.enums.user import UserStatus
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.role import Role
from app.models.user import User
from app.repositories.membership import MembershipRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.role import RoleRepository
from app.repositories.user import UserRepository
from app.schemas.membership import (
    AddOrganizationMemberSchema,
    UpdateMembershipRoleSchema,
)


OWNER_ROLE_NAME = "Owner"
OWNER_ROLE_NAME_NORMALIZED = OWNER_ROLE_NAME.lower()


class MembershipService:
    """
    Handles organization membership business logic.
    """

    def __init__(self, db: Session):
        self.db = db

        self.users = UserRepository(db)
        self.roles = RoleRepository(db)
        self.organizations = OrganizationRepository(db)
        self.memberships = MembershipRepository(db)

    @staticmethod
    def _normalized_role_name(
        role: Role,
    ) -> str:
        """
        Return a normalized role name for comparisons.
        """

        return role.name.strip().lower()

    def _get_organization_or_404(
        self,
        organization_id: uuid.UUID,
    ) -> Organization:
        """
        Retrieve an active organization or raise an error.
        """

        organization = self.organizations.get_by_id(
            organization_id
        )

        if organization is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found.",
            )

        if not organization.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This organization is inactive.",
            )

        return organization

    def _get_requester_membership(
        self,
        organization_id: uuid.UUID,
        current_user: User,
    ) -> Membership:
        """
        Retrieve the current user's organization membership.

        Permission checks happen in the route dependency, but this
        keeps the service safe when called from another entry point.
        """

        self._get_organization_or_404(
            organization_id
        )

        membership = (
            self.db.query(Membership)
            .options(
                joinedload(Membership.role),
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

        return membership

    def _get_role_or_404(
        self,
        role_name: str,
    ) -> Role:
        """
        Retrieve a role by name or raise 404.
        """

        normalized_role_name = (
            role_name.strip().lower()
        )

        role = self.roles.get_by_name(
            normalized_role_name
        )

        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Role '{role_name.strip()}' "
                    "was not found."
                ),
            )

        return role

    def _get_target_membership_or_404(
        self,
        organization_id: uuid.UUID,
        membership_id: uuid.UUID,
        *,
        load_user: bool = False,
    ) -> Membership:
        """
        Retrieve a membership belonging to the organization.
        """

        query = self.db.query(Membership).options(
            joinedload(Membership.role),
        )

        if load_user:
            query = query.options(
                joinedload(Membership.user),
            )

        membership = (
            query.filter(
                Membership.id == membership_id,
                Membership.organization_id
                == organization_id,
            )
            .first()
        )

        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Membership not found.",
            )

        return membership

    def _count_owners(
        self,
        organization_id: uuid.UUID,
    ) -> int:
        """
        Count Owner memberships in an organization.
        """

        return (
            self.db.query(
                func.count(Membership.id)
            )
            .join(
                Role,
                Membership.role_id == Role.id,
            )
            .filter(
                Membership.organization_id
                == organization_id,
                func.lower(Role.name)
                == OWNER_ROLE_NAME_NORMALIZED,
            )
            .scalar()
            or 0
        )

    def _ensure_not_sole_owner(
        self,
        membership: Membership,
    ) -> None:
        """
        Prevent removal or demotion of the sole Owner.
        """

        role_name = self._normalized_role_name(
            membership.role
        )

        if role_name != OWNER_ROLE_NAME_NORMALIZED:
            return

        owner_count = self._count_owners(
            membership.organization_id
        )

        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The organization's only Owner cannot "
                    "be removed or assigned another role."
                ),
            )

    def _require_owner_for_owner_action(
        self,
        requester_membership: Membership,
    ) -> None:
        """
        Require the requester to hold the Owner role.
        """

        requester_role_name = (
            self._normalized_role_name(
                requester_membership.role
            )
        )

        if requester_role_name != OWNER_ROLE_NAME_NORMALIZED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Only an Owner can manage "
                    "Owner memberships."
                ),
            )

    def add_member(
        self,
        organization_id: uuid.UUID,
        payload: AddOrganizationMemberSchema,
        current_user: User,
    ) -> Membership:
        """
        Add an existing registered user to an organization.

        Route authorization requires:
        - memberships.create
        - roles.assign
        """

        requester_membership = (
            self._get_requester_membership(
                organization_id=organization_id,
                current_user=current_user,
            )
        )

        target_user = self.users.get_by_email(
            str(payload.email)
        )

        if target_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "No registered Novera user was found "
                    "with that email address."
                ),
            )

        if target_user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The selected user account "
                    "is not active."
                ),
            )

        if self.memberships.membership_exists(
            organization_id=organization_id,
            user_id=target_user.id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This user already belongs "
                    "to the organization."
                ),
            )

        role = self._get_role_or_404(
            payload.role_name
        )

        requested_role_name = (
            self._normalized_role_name(role)
        )

        if requested_role_name == OWNER_ROLE_NAME_NORMALIZED:
            self._require_owner_for_owner_action(
                requester_membership
            )

        membership = Membership(
            organization_id=organization_id,
            user_id=target_user.id,
            role_id=role.id,
        )

        try:
            membership = (
                self.memberships.create_membership(
                    membership
                )
            )

            return (
                self.db.query(Membership)
                .options(
                    joinedload(Membership.user),
                    joinedload(Membership.role),
                )
                .filter(
                    Membership.id == membership.id
                )
                .one()
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The membership could not be created "
                    "because it conflicts with existing data."
                ),
            ) from exc

    def list_members(
        self,
        organization_id: uuid.UUID,
        current_user: User,
    ) -> list[Membership]:
        """
        List all members of an organization.

        Route authorization requires:
        - memberships.read
        """

        self._get_requester_membership(
            organization_id=organization_id,
            current_user=current_user,
        )

        return (
            self.db.query(Membership)
            .options(
                joinedload(Membership.user),
                joinedload(Membership.role),
            )
            .filter(
                Membership.organization_id
                == organization_id
            )
            .order_by(
                Membership.created_at.asc()
            )
            .all()
        )

    def update_member_role(
        self,
        organization_id: uuid.UUID,
        membership_id: uuid.UUID,
        payload: UpdateMembershipRoleSchema,
        current_user: User,
    ) -> Membership:
        """
        Change an organization member's assigned role.

        Route authorization requires:
        - memberships.update
        - roles.assign
        """

        requester_membership = (
            self._get_requester_membership(
                organization_id=organization_id,
                current_user=current_user,
            )
        )

        target_membership = (
            self._get_target_membership_or_404(
                organization_id=organization_id,
                membership_id=membership_id,
                load_user=True,
            )
        )

        new_role = self._get_role_or_404(
            payload.role_name
        )

        current_role_name = (
            self._normalized_role_name(
                target_membership.role
            )
        )

        new_role_name = self._normalized_role_name(
            new_role
        )

        owner_is_involved = (
            current_role_name
            == OWNER_ROLE_NAME_NORMALIZED
            or new_role_name
            == OWNER_ROLE_NAME_NORMALIZED
        )

        if owner_is_involved:
            self._require_owner_for_owner_action(
                requester_membership
            )

        if (
            current_role_name
            == OWNER_ROLE_NAME_NORMALIZED
            and new_role_name
            != OWNER_ROLE_NAME_NORMALIZED
        ):
            self._ensure_not_sole_owner(
                target_membership
            )

        if target_membership.role_id == new_role.id:
            return target_membership

        target_membership.role_id = new_role.id

        updated_membership = (
            self.memberships.update_membership(
                target_membership
            )
        )

        return (
            self.db.query(Membership)
            .options(
                joinedload(Membership.user),
                joinedload(Membership.role),
            )
            .filter(
                Membership.id
                == updated_membership.id
            )
            .one()
        )

    def remove_member(
        self,
        organization_id: uuid.UUID,
        membership_id: uuid.UUID,
        current_user: User,
    ) -> None:
        """
        Remove a member from an organization.

        Route authorization requires:
        - memberships.delete
        """

        requester_membership = (
            self._get_requester_membership(
                organization_id=organization_id,
                current_user=current_user,
            )
        )

        target_membership = (
            self._get_target_membership_or_404(
                organization_id=organization_id,
                membership_id=membership_id,
            )
        )

        target_role_name = (
            self._normalized_role_name(
                target_membership.role
            )
        )

        if (
            target_role_name
            == OWNER_ROLE_NAME_NORMALIZED
        ):
            self._require_owner_for_owner_action(
                requester_membership
            )

            self._ensure_not_sole_owner(
                target_membership
            )

        self.memberships.delete_membership(
            target_membership
        )