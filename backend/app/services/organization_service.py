"""
Organization service.

Contains business logic for organization onboarding,
updates, and deactivation.

Organization-scoped authorization is handled by
API permission dependencies.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.membership import Membership
from app.models.organization import Organization
from app.models.role import Role
from app.models.user import User
from app.repositories.organization import OrganizationRepository
from app.repositories.role import RoleRepository
from app.schemas.organization import (
    CreateOrganizationSchema,
    UpdateOrganizationSchema,
)
from app.utils.slug import slugify


OWNER_ROLE_NAME = "Owner"

DOCUMENT_SETTING_FIELDS = [
    "business_address",
    "tax_identification_number",
    "vat_number",
    "bank_name",
    "bank_account_name",
    "bank_account_number",
    "bank_routing_number",
    "payment_instructions",
    "default_invoice_terms",
    "default_quote_terms",
    "invoice_footer",
    "quote_footer",
]


class OrganizationService:
    """
    Handles organization business logic.

    Protected organization actions are authorized through
    organization-scoped RBAC dependencies before this service
    is called.
    """

    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.organizations = OrganizationRepository(db)
        self.roles = RoleRepository(db)

    @staticmethod
    def _clean_optional_text(
        value: str | None,
    ) -> str | None:
        """
        Normalize optional organization document-setting text.
        """

        if value is None:
            return None

        cleaned = value.strip()

        return cleaned or None

    def _generate_unique_slug(
        self,
        organization_name: str,
    ) -> str:
        """
        Generate a unique organization slug.
        """

        base_slug = slugify(
            organization_name
        )

        if not base_slug:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Organization name cannot produce "
                    "a valid slug."
                ),
            )

        slug = base_slug
        suffix = 2

        while self.organizations.slug_exists(
            slug
        ):
            slug = f"{base_slug}-{suffix}"
            suffix += 1

        return slug

    def _get_or_create_owner_role(
        self,
    ) -> Role:
        """
        Retrieve the system Owner role.

        Creates the role during initial platform bootstrap
        when it does not already exist.
        """

        owner_role = self.roles.get_by_name(
            OWNER_ROLE_NAME
        )

        if owner_role is not None:
            return owner_role

        owner_role = Role(
            name=OWNER_ROLE_NAME,
            description=(
                "Full administrative control over "
                "an organization."
            ),
            is_system=True,
        )

        self.db.add(
            owner_role
        )
        self.db.flush()

        return owner_role

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
                business_address=self._clean_optional_text(
                    payload.business_address
                ),
                tax_identification_number=self._clean_optional_text(
                    payload.tax_identification_number
                ),
                vat_number=self._clean_optional_text(
                    payload.vat_number
                ),
                bank_name=self._clean_optional_text(
                    payload.bank_name
                ),
                bank_account_name=self._clean_optional_text(
                    payload.bank_account_name
                ),
                bank_account_number=self._clean_optional_text(
                    payload.bank_account_number
                ),
                bank_routing_number=self._clean_optional_text(
                    payload.bank_routing_number
                ),
                payment_instructions=self._clean_optional_text(
                    payload.payment_instructions
                ),
                default_invoice_terms=self._clean_optional_text(
                    payload.default_invoice_terms
                ),
                default_quote_terms=self._clean_optional_text(
                    payload.default_quote_terms
                ),
                invoice_footer=self._clean_optional_text(
                    payload.invoice_footer
                ),
                quote_footer=self._clean_optional_text(
                    payload.quote_footer
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
                Membership.user_id
                == current_user.id,
                Organization.is_active.is_(True),
            )
            .order_by(
                Organization.name.asc()
            )
            .all()
        )

    def update_organization(
        self,
        organization: Organization,
        payload: UpdateOrganizationSchema,
    ) -> Organization:
        """
        Update organization details.

        The slug remains stable when the organization name changes.
        """

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

        for field_name in DOCUMENT_SETTING_FIELDS:
            if field_name not in update_data:
                continue

            setattr(
                organization,
                field_name,
                self._clean_optional_text(
                    update_data[field_name]
                ),
            )

        return self.organizations.update_organization(
            organization
        )

    def deactivate_organization(
        self,
        organization: Organization,
    ) -> Organization:
        """
        Deactivate an organization.

        Authorization is handled by the
        organizations.deactivate permission dependency.
        """

        if not organization.is_active:
            return organization

        return self.organizations.deactivate(
            organization
        )
