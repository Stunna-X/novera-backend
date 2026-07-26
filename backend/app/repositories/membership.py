"""
Membership repository.

Contains database operations for organization memberships.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.membership import Membership
from app.repositories.base import BaseRepository


class MembershipRepository(
    BaseRepository[Membership]
):
    """
    Repository for organization membership operations.
    """

    def __init__(self, db: Session):
        super().__init__(db, Membership)

    def create_membership(
        self,
        membership: Membership,
    ) -> Membership:
        """
        Persist a new organization membership.
        """

        return self.create(membership)

    def get_membership(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Membership | None:
        """
        Retrieve a user's membership in an organization.
        """

        return (
            self.db.query(Membership)
            .filter(
                Membership.organization_id == organization_id,
                Membership.user_id == user_id,
            )
            .first()
        )

    def membership_exists(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """
        Check whether a user already belongs to an organization.
        """

        return (
            self.get_membership(
                organization_id=organization_id,
                user_id=user_id,
            )
            is not None
        )

    def get_user_memberships(
        self,
        user_id: uuid.UUID,
    ) -> list[Membership]:
        """
        Retrieve all memberships belonging to a user.
        """

        return (
            self.db.query(Membership)
            .filter(
                Membership.user_id == user_id
            )
            .order_by(Membership.created_at.asc())
            .all()
        )

    def get_organization_memberships(
        self,
        organization_id: uuid.UUID,
    ) -> list[Membership]:
        """
        Retrieve all memberships in an organization.
        """

        return (
            self.db.query(Membership)
            .filter(
                Membership.organization_id == organization_id
            )
            .order_by(Membership.created_at.asc())
            .all()
        )

    def update_membership(
        self,
        membership: Membership,
    ) -> Membership:
        """
        Persist changes to a membership.
        """

        return self.update(membership)

    def delete_membership(
        self,
        membership: Membership,
    ) -> None:
        """
        Remove a user from an organization.
        """

        self.delete(membership)