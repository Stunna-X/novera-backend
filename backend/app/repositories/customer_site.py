"""
Customer site repository.

Contains tenant-scoped database operations for
customer service locations.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.customer_site import CustomerSite
from app.repositories.base import BaseRepository


class CustomerSiteRepository(
    BaseRepository[CustomerSite]
):
    """
    Repository for customer-site database operations.
    """

    def __init__(
        self,
        db: Session,
    ):
        super().__init__(
            db,
            CustomerSite,
        )

    def create_site(
        self,
        site: CustomerSite,
    ) -> CustomerSite:
        """
        Persist a new customer site.
        """

        site.name = site.name.strip()
        site.address_line_1 = (
            site.address_line_1.strip()
        )

        if site.site_code:
            site.site_code = (
                site.site_code.strip().upper()
            )

        if site.email:
            site.email = (
                site.email.strip().lower()
            )

        return self.create(
            site
        )

    def get_for_customer(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        site_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> CustomerSite | None:
        """
        Retrieve one site belonging to a customer.
        """

        query = self.db.query(CustomerSite).filter(
            CustomerSite.id == site_id,
            CustomerSite.organization_id
            == organization_id,
            CustomerSite.customer_id == customer_id,
        )

        if not include_inactive:
            query = query.filter(
                CustomerSite.is_active.is_(True)
            )

        return query.first()

    def list_for_customer(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        include_inactive: bool = False,
    ) -> list[CustomerSite]:
        """
        Retrieve sites belonging to a customer.
        """

        query = self.db.query(CustomerSite).filter(
            CustomerSite.organization_id
            == organization_id,
            CustomerSite.customer_id == customer_id,
        )

        if not include_inactive:
            query = query.filter(
                CustomerSite.is_active.is_(True)
            )

        normalized_search = (
            search.strip()
            if search
            else None
        )

        if normalized_search:
            pattern = f"%{normalized_search}%"

            query = query.filter(
                or_(
                    CustomerSite.name.ilike(pattern),
                    CustomerSite.site_code.ilike(pattern),
                    CustomerSite.address_line_1.ilike(
                        pattern
                    ),
                    CustomerSite.city.ilike(pattern),
                    CustomerSite.state.ilike(pattern),
                )
            )

        return (
            query.order_by(
                CustomerSite.name.asc(),
                CustomerSite.created_at.asc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_customer(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        *,
        search: str | None = None,
        include_inactive: bool = False,
    ) -> int:
        """
        Count sites belonging to a customer.
        """

        query = (
            self.db.query(
                func.count(CustomerSite.id)
            )
            .filter(
                CustomerSite.organization_id
                == organization_id,
                CustomerSite.customer_id
                == customer_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                CustomerSite.is_active.is_(True)
            )

        normalized_search = (
            search.strip()
            if search
            else None
        )

        if normalized_search:
            pattern = f"%{normalized_search}%"

            query = query.filter(
                or_(
                    CustomerSite.name.ilike(pattern),
                    CustomerSite.site_code.ilike(pattern),
                    CustomerSite.address_line_1.ilike(
                        pattern
                    ),
                    CustomerSite.city.ilike(pattern),
                    CustomerSite.state.ilike(pattern),
                )
            )

        return query.scalar() or 0

    def site_code_exists(
        self,
        organization_id: uuid.UUID,
        site_code: str,
        *,
        exclude_site_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Check whether a site code is already used
        inside the organization.
        """

        normalized_code = (
            site_code.strip().lower()
        )

        query = self.db.query(
            CustomerSite.id
        ).filter(
            CustomerSite.organization_id
            == organization_id,
            func.lower(CustomerSite.site_code)
            == normalized_code,
        )

        if exclude_site_id is not None:
            query = query.filter(
                CustomerSite.id != exclude_site_id
            )

        return query.first() is not None

    def update_site(
        self,
        site: CustomerSite,
    ) -> CustomerSite:
        """
        Persist changes to a customer site.
        """

        site.name = site.name.strip()
        site.address_line_1 = (
            site.address_line_1.strip()
        )

        if site.site_code:
            site.site_code = (
                site.site_code.strip().upper()
            )

        if site.email:
            site.email = (
                site.email.strip().lower()
            )

        return self.update(
            site
        )

    def deactivate_site(
        self,
        site: CustomerSite,
    ) -> CustomerSite:
        """
        Soft-delete a site.
        """

        site.is_active = False

        return self.update(
            site
        )

    def reactivate_site(
        self,
        site: CustomerSite,
    ) -> CustomerSite:
        """
        Reactivate a site.
        """

        site.is_active = True

        return self.update(
            site
        )