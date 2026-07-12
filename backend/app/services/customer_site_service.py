"""
Customer site service.

Contains business logic for organization-scoped
customer operational locations.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.customer_site import CustomerSite
from app.repositories.customer import CustomerRepository
from app.repositories.customer_site import CustomerSiteRepository
from app.schemas.customer_site import (
    CreateCustomerSiteSchema,
    CustomerSiteListResponse,
    UpdateCustomerSiteSchema,
)


class CustomerSiteService:
    """
    Handles customer-site business logic.
    """

    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.customers = CustomerRepository(db)
        self.sites = CustomerSiteRepository(db)

    def _ensure_customer_exists(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
    ) -> None:
        """
        Ensure the customer exists and is active.
        """

        customer = (
            self.customers.get_by_id_for_organization(
                organization_id=organization_id,
                customer_id=customer_id,
            )
        )

        if customer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found.",
            )

    def _get_site_or_404(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        site_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> CustomerSite:
        """
        Retrieve a customer site or raise 404.
        """

        site = self.sites.get_for_customer(
            organization_id=organization_id,
            customer_id=customer_id,
            site_id=site_id,
            include_inactive=include_inactive,
        )

        if site is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer site not found.",
            )

        return site

    def _ensure_site_code_available(
        self,
        organization_id: uuid.UUID,
        site_code: str | None,
        *,
        exclude_site_id: uuid.UUID | None = None,
    ) -> None:
        """
        Ensure a site code is unique inside the organization.
        """

        if not site_code:
            return

        if self.sites.site_code_exists(
            organization_id=organization_id,
            site_code=site_code,
            exclude_site_id=exclude_site_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another site in this organization "
                    "already uses this site code."
                ),
            )

    def create_site(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        payload: CreateCustomerSiteSchema,
    ) -> CustomerSite:
        """
        Create a site for a customer.
        """

        self._ensure_customer_exists(
            organization_id=organization_id,
            customer_id=customer_id,
        )

        site_data = payload.model_dump()

        self._ensure_site_code_available(
            organization_id=organization_id,
            site_code=site_data.get("site_code"),
        )

        site = CustomerSite(
            organization_id=organization_id,
            customer_id=customer_id,
            **site_data,
        )

        try:
            return self.sites.create_site(
                site
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another site in this organization "
                    "already uses this site code."
                ),
            ) from exc

    def list_sites(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        include_inactive: bool = False,
    ) -> CustomerSiteListResponse:
        """
        Return a paginated customer-site collection.
        """

        self._ensure_customer_exists(
            organization_id=organization_id,
            customer_id=customer_id,
        )

        sites = self.sites.list_for_customer(
            organization_id=organization_id,
            customer_id=customer_id,
            skip=skip,
            limit=limit,
            search=search,
            include_inactive=include_inactive,
        )

        total = self.sites.count_for_customer(
            organization_id=organization_id,
            customer_id=customer_id,
            search=search,
            include_inactive=include_inactive,
        )

        return CustomerSiteListResponse(
            items=sites,
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_site(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        site_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> CustomerSite:
        """
        Return one customer site.
        """

        self._ensure_customer_exists(
            organization_id=organization_id,
            customer_id=customer_id,
        )

        return self._get_site_or_404(
            organization_id=organization_id,
            customer_id=customer_id,
            site_id=site_id,
            include_inactive=include_inactive,
        )

    def update_site(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        site_id: uuid.UUID,
        payload: UpdateCustomerSiteSchema,
    ) -> CustomerSite:
        """
        Update an active customer site.
        """

        self._ensure_customer_exists(
            organization_id=organization_id,
            customer_id=customer_id,
        )

        site = self._get_site_or_404(
            organization_id=organization_id,
            customer_id=customer_id,
            site_id=site_id,
        )

        update_data = payload.model_dump(
            exclude_unset=True
        )

        if (
            "name" in update_data
            and update_data["name"] is None
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Site name cannot be null.",
            )

        if (
            "address_line_1" in update_data
            and update_data["address_line_1"] is None
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Site address cannot be null."
                ),
            )

        if "site_code" in update_data:
            self._ensure_site_code_available(
                organization_id=organization_id,
                site_code=update_data["site_code"],
                exclude_site_id=site.id,
            )

        for field_name, field_value in update_data.items():
            setattr(
                site,
                field_name,
                field_value,
            )

        return self.sites.update_site(
            site
        )

    def deactivate_site(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        site_id: uuid.UUID,
    ) -> None:
        """
        Soft-delete a customer site.
        """

        self._ensure_customer_exists(
            organization_id=organization_id,
            customer_id=customer_id,
        )

        site = self._get_site_or_404(
            organization_id=organization_id,
            customer_id=customer_id,
            site_id=site_id,
        )

        self.sites.deactivate_site(
            site
        )

    def reactivate_site(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        site_id: uuid.UUID,
    ) -> CustomerSite:
        """
        Reactivate a customer site.
        """

        self._ensure_customer_exists(
            organization_id=organization_id,
            customer_id=customer_id,
        )

        site = self._get_site_or_404(
            organization_id=organization_id,
            customer_id=customer_id,
            site_id=site_id,
            include_inactive=True,
        )

        if site.is_active:
            return site

        return self.sites.reactivate_site(
            site
        )