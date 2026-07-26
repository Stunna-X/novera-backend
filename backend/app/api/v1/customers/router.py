"""
Customer routes.

Provides organization-scoped endpoints for creating,
viewing, updating, deactivating, and reactivating customers.
"""

from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    Depends,
    Query,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import (
    OrganizationContext,
    require_permission,
)
from app.database.session import get_db
from app.models.customer import Customer
from app.schemas.customer import (
    CreateCustomerSchema,
    CustomerListResponse,
    CustomerResponse,
    UpdateCustomerSchema,
)
from app.services.customer_service import CustomerService


router = APIRouter(
    prefix="/organizations/{organization_id}/customers",
    tags=["Customers"],
)


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create customer",
)
def create_customer(
    payload: CreateCustomerSchema,
    context: OrganizationContext = Depends(
        require_permission("customers.create")
    ),
    db: Session = Depends(get_db),
) -> Customer:
    """
    Create a customer inside the organization.

    Requires:
    - customers.create
    """

    service = CustomerService(db)

    return service.create_customer(
        organization_id=context.organization.id,
        payload=payload,
    )


@router.get(
    "",
    response_model=CustomerListResponse,
    summary="List customers",
)
def list_customers(
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
    ),
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=160,
    ),
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("customers.read")
    ),
    db: Session = Depends(get_db),
) -> CustomerListResponse:
    """
    List customers belonging to the organization.

    Supports pagination, searching, and optional inclusion
    of inactive customers.

    Requires:
    - customers.read
    """

    service = CustomerService(db)

    return service.list_customers(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        search=search,
        include_inactive=include_inactive,
    )


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get customer",
)
def get_customer(
    customer_id: uuid.UUID,
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("customers.read")
    ),
    db: Session = Depends(get_db),
) -> Customer:
    """
    Return one customer belonging to the organization.

    Requires:
    - customers.read
    """

    service = CustomerService(db)

    return service.get_customer(
        organization_id=context.organization.id,
        customer_id=customer_id,
        include_inactive=include_inactive,
    )


@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Update customer",
)
def update_customer(
    customer_id: uuid.UUID,
    payload: UpdateCustomerSchema,
    context: OrganizationContext = Depends(
        require_permission("customers.update")
    ),
    db: Session = Depends(get_db),
) -> Customer:
    """
    Update an active customer.

    Requires:
    - customers.update
    """

    service = CustomerService(db)

    return service.update_customer(
        organization_id=context.organization.id,
        customer_id=customer_id,
        payload=payload,
    )


@router.delete(
    "/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate customer",
)
def deactivate_customer(
    customer_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("customers.delete")
    ),
    db: Session = Depends(get_db),
) -> Response:
    """
    Soft-delete a customer.

    Requires:
    - customers.delete
    """

    service = CustomerService(db)

    service.deactivate_customer(
        organization_id=context.organization.id,
        customer_id=customer_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )


@router.patch(
    "/{customer_id}/reactivate",
    response_model=CustomerResponse,
    summary="Reactivate customer",
)
def reactivate_customer(
    customer_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("customers.update")
    ),
    db: Session = Depends(get_db),
) -> Customer:
    """
    Reactivate a previously deactivated customer.

    Requires:
    - customers.update
    """

    service = CustomerService(db)

    return service.reactivate_customer(
        organization_id=context.organization.id,
        customer_id=customer_id,
    )