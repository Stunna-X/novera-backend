"""
Customer service.

Contains business logic for creating, retrieving,
updating, listing, deactivating, and reactivating customers.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.repositories.customer import CustomerRepository
from app.schemas.customer import (
    CreateCustomerSchema,
    CustomerListResponse,
    UpdateCustomerSchema,
)


class CustomerService:
    """
    Handles organization-scoped customer business logic.
    """

    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.customers = CustomerRepository(db)

    def _get_customer_or_404(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> Customer:
        """
        Retrieve an organization customer or raise 404.
        """

        customer = (
            self.customers.get_by_id_for_organization(
                organization_id=organization_id,
                customer_id=customer_id,
                include_inactive=include_inactive,
            )
        )

        if customer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found.",
            )

        return customer

    def _ensure_email_available(
        self,
        organization_id: uuid.UUID,
        email: str | None,
        *,
        exclude_customer_id: uuid.UUID | None = None,
    ) -> None:
        """
        Ensure a customer email is not already used
        within the same organization.
        """

        if not email:
            return

        email_exists = (
            self.customers.email_exists_for_organization(
                organization_id=organization_id,
                email=email,
                exclude_customer_id=exclude_customer_id,
            )
        )

        if email_exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another customer in this organization "
                    "already uses this email address."
                ),
            )

    def create_customer(
        self,
        organization_id: uuid.UUID,
        payload: CreateCustomerSchema,
    ) -> Customer:
        """
        Create a customer for an organization.
        """

        customer_data = payload.model_dump()

        self._ensure_email_available(
            organization_id=organization_id,
            email=customer_data.get("email"),
        )

        customer = Customer(
            organization_id=organization_id,
            **customer_data,
        )

        return self.customers.create_customer(
            customer
        )

    def list_customers(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        include_inactive: bool = False,
    ) -> CustomerListResponse:
        """
        Return a paginated collection of organization customers.
        """

        customers = (
            self.customers.list_for_organization(
                organization_id=organization_id,
                skip=skip,
                limit=limit,
                search=search,
                include_inactive=include_inactive,
            )
        )

        total = (
            self.customers.count_for_organization(
                organization_id=organization_id,
                search=search,
                include_inactive=include_inactive,
            )
        )

        return CustomerListResponse(
            items=customers,
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_customer(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> Customer:
        """
        Return one organization customer.
        """

        return self._get_customer_or_404(
            organization_id=organization_id,
            customer_id=customer_id,
            include_inactive=include_inactive,
        )

    def update_customer(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        payload: UpdateCustomerSchema,
    ) -> Customer:
        """
        Update an active customer.
        """

        customer = self._get_customer_or_404(
            organization_id=organization_id,
            customer_id=customer_id,
        )

        update_data = payload.model_dump(
            exclude_unset=True
        )

        if "email" in update_data:
            self._ensure_email_available(
                organization_id=organization_id,
                email=update_data["email"],
                exclude_customer_id=customer.id,
            )

        for field_name, field_value in update_data.items():
            setattr(
                customer,
                field_name,
                field_value,
            )

        return self.customers.update_customer(
            customer
        )

    def deactivate_customer(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
    ) -> None:
        """
        Soft-delete an active customer.
        """

        customer = self._get_customer_or_404(
            organization_id=organization_id,
            customer_id=customer_id,
        )

        self.customers.deactivate_customer(
            customer
        )

    def reactivate_customer(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
    ) -> Customer:
        """
        Reactivate a previously deactivated customer.
        """

        customer = self._get_customer_or_404(
            organization_id=organization_id,
            customer_id=customer_id,
            include_inactive=True,
        )

        if customer.is_active:
            return customer

        return self.customers.reactivate_customer(
            customer
        )