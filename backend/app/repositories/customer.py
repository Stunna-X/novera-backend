"""
Customer repository.

Contains organization-scoped database operations for
customer records.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    """
    Repository for customer database operations.

    Every customer lookup is scoped to an organization to
    preserve tenant isolation.
    """

    def __init__(
        self,
        db: Session,
    ):
        super().__init__(
            db,
            Customer,
        )

    def create_customer(
        self,
        customer: Customer,
    ) -> Customer:
        """
        Persist a new customer.
        """

        customer.name = customer.name.strip()

        if customer.email:
            customer.email = customer.email.strip().lower()

        return self.create(
            customer
        )

    def get_by_id_for_organization(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> Customer | None:
        """
        Retrieve one customer belonging to an organization.
        """

        query = self.db.query(Customer).filter(
            Customer.id == customer_id,
            Customer.organization_id == organization_id,
        )

        if not include_inactive:
            query = query.filter(
                Customer.is_active.is_(True)
            )

        return query.first()

    def list_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        include_inactive: bool = False,
    ) -> list[Customer]:
        """
        Retrieve customers belonging to an organization.

        Supports pagination, optional searching, and optional
        inclusion of inactive records.
        """

        query = self.db.query(Customer).filter(
            Customer.organization_id == organization_id
        )

        if not include_inactive:
            query = query.filter(
                Customer.is_active.is_(True)
            )

        normalized_search = (
            search.strip()
            if search
            else None
        )

        if normalized_search:
            search_pattern = (
                f"%{normalized_search}%"
            )

            query = query.filter(
                or_(
                    Customer.name.ilike(
                        search_pattern
                    ),
                    Customer.contact_name.ilike(
                        search_pattern
                    ),
                    Customer.email.ilike(
                        search_pattern
                    ),
                    Customer.phone.ilike(
                        search_pattern
                    ),
                    Customer.city.ilike(
                        search_pattern
                    ),
                    Customer.state.ilike(
                        search_pattern
                    ),
                )
            )

        return (
            query.order_by(
                Customer.name.asc(),
                Customer.created_at.asc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None = None,
        include_inactive: bool = False,
    ) -> int:
        """
        Count customers belonging to an organization.
        """

        query = (
            self.db.query(
                func.count(Customer.id)
            )
            .filter(
                Customer.organization_id
                == organization_id
            )
        )

        if not include_inactive:
            query = query.filter(
                Customer.is_active.is_(True)
            )

        normalized_search = (
            search.strip()
            if search
            else None
        )

        if normalized_search:
            search_pattern = (
                f"%{normalized_search}%"
            )

            query = query.filter(
                or_(
                    Customer.name.ilike(
                        search_pattern
                    ),
                    Customer.contact_name.ilike(
                        search_pattern
                    ),
                    Customer.email.ilike(
                        search_pattern
                    ),
                    Customer.phone.ilike(
                        search_pattern
                    ),
                    Customer.city.ilike(
                        search_pattern
                    ),
                    Customer.state.ilike(
                        search_pattern
                    ),
                )
            )

        return query.scalar() or 0

    def email_exists_for_organization(
        self,
        organization_id: uuid.UUID,
        email: str,
        *,
        exclude_customer_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Check whether an email is already used by another customer
        in the same organization.
        """

        normalized_email = (
            email.strip().lower()
        )

        query = self.db.query(Customer.id).filter(
            Customer.organization_id == organization_id,
            func.lower(Customer.email)
            == normalized_email,
        )

        if exclude_customer_id is not None:
            query = query.filter(
                Customer.id
                != exclude_customer_id
            )

        return query.first() is not None

    def update_customer(
        self,
        customer: Customer,
    ) -> Customer:
        """
        Persist customer changes.
        """

        customer.name = customer.name.strip()

        if customer.email:
            customer.email = customer.email.strip().lower()

        return self.update(
            customer
        )

    def deactivate_customer(
        self,
        customer: Customer,
    ) -> Customer:
        """
        Soft-delete a customer.
        """

        customer.is_active = False

        return self.update(
            customer
        )

    def reactivate_customer(
        self,
        customer: Customer,
    ) -> Customer:
        """
        Reactivate a previously deactivated customer.
        """

        customer.is_active = True

        return self.update(
            customer
        )