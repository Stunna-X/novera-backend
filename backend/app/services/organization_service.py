"""
Organization service.

Contains business logic for organization onboarding,
membership access, updates, and deactivation.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.membership import Membership
from app.models.organization import Organization
from app.models.role import Role
from app.models.user import User
from app.repositories.membership import MembershipRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.role import RoleRepository
from app.schemas.organization import (
    CreateOrganizationSchema,
    UpdateOrganizationSchema,
)
from app.utils.slug import slugify


OWNER_ROLE_NAME = "Owner"
MANAGEMENT_ROLES = {
    "owner",
    "admin",
}


class OrganizationService:
    """
    Handles organization business logic.
    """

    def __init__(self, db: Session):
        self.db = db

        self.organizations = OrganizationRepository(db)
        self.memberships = MembershipRepository(db)
        self.roles = RoleRepository(db)

    def _generate_unique_slug(
        self,
        organization_name: str,
    ) -> str:
        """
        Generate a unique organization slug.
        """

        base_slug = slugify(organization_name)

        if not base_slug:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Organization name cannot produce a valid slug.",
            )

        slug = base_slug
        suffix = 2

        while self.organizations.slug_exists(slug):
            slug = f"{base_slug}-{suffix}"
            suffix += 1

        return slug

    def _get_or_create_owner_role(self) -> Role:
        """
        Retrieve the system Owner role.

        Creates it during initial platform bootstrap when it
        does not already exist.
        """

        owner_role = self.roles.get_by_name(
            OWNER_ROLE_NAME
        )

        if owner_role is not None:
            return owner_role

        owner_role = Role(
            name=OWNER_ROLE_NAME,
            description=(
                "Full administrative control over an organization."
            ),
            is_system=True,
        )

        self.db.add(owner_role)
        self.db.flush()

        return owner_role

    def _get_membership_or_404(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> tuple[Organization, Membership]:
        """
        Retrieve an organization and the user's membership.

        Returns 404 when either the organization does not exist
        or the user does not belong to it.
        """

        organization = self.organizations.get_by_id(
            organization_id
        )

        if organization is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found.",
            )

        membership = self.memberships.get_membership(
            organization_id=organization_id,
            user_id=user_id,
        )

        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found.",
            )

        return organization, membership

    def _require_management_access(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> tuple[Organization, Membership]:
        """
        Require an Owner or Admin membership.
        """

        organization, membership = (
            self._get_membership_or_404(
                organization_id=organization_id,
                user_id=user_id,
            )
        )

        role_name = membership.role.name.strip().lower()

        if role_name not in MANAGEMENT_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You do not have permission to manage "
                    "this organization."
                ),
            )

        return organization, membership

    def create_organization(
        self,
        payload: CreateOrganizationSchema,
        current_user: User,
    ) -> Organization:
        """
        Create an organization and make the current user its Owner.

        The organization, Owner role, and membership are committed
        in one database transaction.
        """

        organization_name = payload.name.strip()

        slug = self._generate_unique_slug(
            organization_name
        )

        try:
            owner_role = self._get_or_create_owner_role()

            organization = Organization(
                name=organization_name,
                slug=slug,
                industry=payload.industry,
                email=(
                    str(payload.email).lower()
                    if payload.email
                    else None
                ),
                phone=(
                    payload.phone.strip()
                    if payload.phone
                    else None
                ),
                country=(
                    payload.country.strip()
                    if payload.country
                    else None
                ),
                timezone=payload.timezone.strip(),
                logo_url=(
                    payload.logo_url.strip()
                    if payload.logo_url
                    else None
                ),
            )

            self.db.add(organization)
            self.db.flush()

            membership = Membership(
                organization_id=organization.id,
                user_id=current_user.id,
                role_id=owner_role.id,
            )

            self.db.add(membership)
            self.db.commit()
            self.db.refresh(organization)

            return organization

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "An organization with the generated slug "
                    "already exists."
                ),
            ) from exc

        except Exception:
            self.db.rollback()
            raise

    def list_user_organizations(
        self,
        current_user: User,
    ) -> list[Organization]:
        """
        Retrieve active organizations belonging to the current user.
        """

        return (
            self.db.query(Organization)
            .join(
                Membership,
                Membership.organization_id
                == Organization.id,
            )
            .filter(
                Membership.user_id == current_user.id,
                Organization.is_active.is_(True),
            )
            .order_by(Organization.name.asc())
            .all()
        )

    def get_organization(
        self,
        organization_id: uuid.UUID,
        current_user: User,
    ) -> Organization:
        """
        Retrieve an organization the current user belongs to.
        """

        organization, _ = self._get_membership_or_404(
            organization_id=organization_id,
            user_id=current_user.id,
        )

        return organization

    def update_organization(
        self,
        organization_id: uuid.UUID,
        payload: UpdateOrganizationSchema,
        current_user: User,
    ) -> Organization:
        """
        Update organization details.

        Only Owner and Admin memberships may perform this action.
        The slug remains stable when the organization name changes.
        """

        organization, _ = self._require_management_access(
            organization_id=organization_id,
            user_id=current_user.id,
        )

        update_data = payload.model_dump(
            exclude_unset=True
        )

        if "name" in update_data:
            organization.name = update_data["name"].strip()

        if "industry" in update_data:
            organization.industry = update_data["industry"]

        if "email" in update_data:
            email = update_data["email"]
            organization.email = (
                str(email).lower()
                if email
                else None
            )

        if "phone" in update_data:
            phone = update_data["phone"]
            organization.phone = (
                phone.strip()
                if phone
                else None
            )

        if "country" in update_data:
            country = update_data["country"]
            organization.country = (
                country.strip()
                if country
                else None
            )

        if "timezone" in update_data:
            timezone = update_data["timezone"]
            organization.timezone = timezone.strip()

        if "logo_url" in update_data:
            logo_url = update_data["logo_url"]
            organization.logo_url = (
                logo_url.strip()
                if logo_url
                else None
            )

        return self.organizations.update_organization(
            organization
        )

    def deactivate_organization(
        self,
        organization_id: uuid.UUID,
        current_user: User,
    ) -> Organization:
        """
        Deactivate an organization.

        Only Owner and Admin memberships may perform this action.
        """

        organization, _ = self._require_management_access(
            organization_id=organization_id,
            user_id=current_user.id,
        )

        if not organization.is_active:
            return organization

        return self.organizations.deactivate(
            organization
        )