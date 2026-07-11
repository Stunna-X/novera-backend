"""
Organization repository.

Contains all database operations related to organizations.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.repositories.base import BaseRepository


class OrganizationRepository(
    BaseRepository[Organization]
):
    """
    Repository for organization database operations.
    """

    def __init__(self, db: Session):
        super().__init__(db, Organization)

    def create_organization(
        self,
        organization: Organization,
    ) -> Organization:
        """
        Persist a new organization.
        """

        organization.slug = self.normalize_slug(
            organization.slug
        )

        return self.create(organization)

    def get_by_id(
        self,
        organization_id: uuid.UUID,
    ) -> Organization | None:
        """
        Retrieve an organization by UUID.
        """

        return self.get(organization_id)

    def get_by_slug(
        self,
        slug: str,
    ) -> Organization | None:
        """
        Retrieve an organization by normalized slug.
        """

        normalized_slug = self.normalize_slug(slug)

        return (
            self.db.query(Organization)
            .filter(
                Organization.slug == normalized_slug
            )
            .first()
        )

    def slug_exists(
        self,
        slug: str,
    ) -> bool:
        """
        Check whether an organization slug already exists.
        """

        return self.get_by_slug(slug) is not None

    def update_organization(
        self,
        organization: Organization,
    ) -> Organization:
        """
        Persist organization changes.
        """

        organization.slug = self.normalize_slug(
            organization.slug
        )

        return self.update(organization)

    def deactivate(
        self,
        organization: Organization,
    ) -> Organization:
        """
        Deactivate an organization.
        """

        organization.is_active = False

        return self.update(organization)

    def activate(
        self,
        organization: Organization,
    ) -> Organization:
        """
        Reactivate an organization.
        """

        organization.is_active = True

        return self.update(organization)

    def list_active(
        self,
    ) -> list[Organization]:
        """
        Retrieve all active organizations.
        """

        return (
            self.db.query(Organization)
            .filter(
                Organization.is_active.is_(True)
            )
            .order_by(Organization.name.asc())
            .all()
        )

    @staticmethod
    def normalize_slug(
        slug: str,
    ) -> str:
        """
        Normalize an organization slug for lookup and storage.
        """

        return slug.strip().lower()