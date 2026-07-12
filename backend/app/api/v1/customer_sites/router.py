"""
Customer site routes.

Provides organization-scoped endpoints for managing
customer operational locations.
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
from app.models.customer_site import CustomerSite
from app.schemas.customer_site import (
    CreateCustomerSiteSchema,
    CustomerSiteListResponse,
    CustomerSiteResponse,
    UpdateCustomerSiteSchema,
)
from app.services.customer_site_service import CustomerSiteService


router = APIRouter(
    prefix=(
        "/organizations/{organization_id}"
        "/customers/{customer_id}/sites"
    ),
    tags=["Customer Sites"],
)


@router.post(
    "",
    response_model=CustomerSiteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create customer site",
)
def create_customer_site(
    customer_id: uuid.UUID,
    payload: CreateCustomerSiteSchema,
    context: OrganizationContext = Depends(
        require_permission("customers.create")
    ),
    db: Session = Depends(get_db),
) -> CustomerSite:
    """
    Create a customer operational location.

    Requires:
    - customers.create
    """

    service = CustomerSiteService(db)

    return service.create_site(
        organization_id=context.organization.id,
        customer_id=customer_id,
        payload=payload,
    )


@router.get(
    "",
    response_model=CustomerSiteListResponse,
    summary="List customer sites",
)
def list_customer_sites(
    customer_id: uuid.UUID,
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
) -> CustomerSiteListResponse:
    """
    List a customer's operational locations.

    Requires:
    - customers.read
    """

    service = CustomerSiteService(db)

    return service.list_sites(
        organization_id=context.organization.id,
        customer_id=customer_id,
        skip=skip,
        limit=limit,
        search=search,
        include_inactive=include_inactive,
    )


@router.get(
    "/{site_id}",
    response_model=CustomerSiteResponse,
    summary="Get customer site",
)
def get_customer_site(
    customer_id: uuid.UUID,
    site_id: uuid.UUID,
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("customers.read")
    ),
    db: Session = Depends(get_db),
) -> CustomerSite:
    """
    Return one customer operational location.

    Requires:
    - customers.read
    """

    service = CustomerSiteService(db)

    return service.get_site(
        organization_id=context.organization.id,
        customer_id=customer_id,
        site_id=site_id,
        include_inactive=include_inactive,
    )


@router.patch(
    "/{site_id}",
    response_model=CustomerSiteResponse,
    summary="Update customer site",
)
def update_customer_site(
    customer_id: uuid.UUID,
    site_id: uuid.UUID,
    payload: UpdateCustomerSiteSchema,
    context: OrganizationContext = Depends(
        require_permission("customers.update")
    ),
    db: Session = Depends(get_db),
) -> CustomerSite:
    """
    Update a customer operational location.

    Requires:
    - customers.update
    """

    service = CustomerSiteService(db)

    return service.update_site(
        organization_id=context.organization.id,
        customer_id=customer_id,
        site_id=site_id,
        payload=payload,
    )


@router.delete(
    "/{site_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate customer site",
)
def deactivate_customer_site(
    customer_id: uuid.UUID,
    site_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("customers.delete")
    ),
    db: Session = Depends(get_db),
) -> Response:
    """
    Soft-delete a customer operational location.

    Requires:
    - customers.delete
    """

    service = CustomerSiteService(db)

    service.deactivate_site(
        organization_id=context.organization.id,
        customer_id=customer_id,
        site_id=site_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )


@router.patch(
    "/{site_id}/reactivate",
    response_model=CustomerSiteResponse,
    summary="Reactivate customer site",
)
def reactivate_customer_site(
    customer_id: uuid.UUID,
    site_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("customers.update")
    ),
    db: Session = Depends(get_db),
) -> CustomerSite:
    """
    Reactivate a customer operational location.

    Requires:
    - customers.update
    """

    service = CustomerSiteService(db)

    return service.reactivate_site(
        organization_id=context.organization.id,
        customer_id=customer_id,
        site_id=site_id,
    )