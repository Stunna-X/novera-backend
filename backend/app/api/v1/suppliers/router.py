"""Supplier routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import OrganizationContext, require_permission
from app.database.session import get_db
from app.models.supplier import Supplier
from app.schemas.supplier import (
    CreateSupplierSchema,
    SupplierListResponse,
    SupplierResponse,
    SupplierType,
    UpdateSupplierSchema,
)
from app.services.supplier_service import SupplierService


router = APIRouter(
    prefix="/organizations/{organization_id}/suppliers",
    tags=["Suppliers"],
)


@router.post(
    "",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create supplier",
)
def create_supplier(
    payload: CreateSupplierSchema,
    context: OrganizationContext = Depends(
        require_permission("suppliers.create")
    ),
    db: Session = Depends(get_db),
) -> Supplier:
    """Create an organization supplier."""

    return SupplierService(db).create_supplier(
        organization_id=context.organization.id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.get(
    "",
    response_model=SupplierListResponse,
    summary="List suppliers",
)
def list_suppliers(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=180,
    ),
    supplier_type: SupplierType | None = Query(default=None),
    category: str | None = Query(
        default=None,
        min_length=1,
        max_length=120,
    ),
    include_inactive: bool = Query(default=False),
    context: OrganizationContext = Depends(
        require_permission("suppliers.read")
    ),
    db: Session = Depends(get_db),
) -> SupplierListResponse:
    """List organization suppliers with filters and pagination."""

    return SupplierService(db).list_suppliers(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        search=search,
        supplier_type=supplier_type,
        category=category,
        include_inactive=include_inactive,
    )


@router.get(
    "/{supplier_id}",
    response_model=SupplierResponse,
    summary="Get supplier",
)
def get_supplier(
    supplier_id: uuid.UUID,
    include_inactive: bool = Query(default=False),
    context: OrganizationContext = Depends(
        require_permission("suppliers.read")
    ),
    db: Session = Depends(get_db),
) -> Supplier:
    """Return one organization supplier."""

    return SupplierService(db).get_supplier(
        organization_id=context.organization.id,
        supplier_id=supplier_id,
        include_inactive=include_inactive,
    )


@router.patch(
    "/{supplier_id}",
    response_model=SupplierResponse,
    summary="Update supplier",
)
def update_supplier(
    supplier_id: uuid.UUID,
    payload: UpdateSupplierSchema,
    context: OrganizationContext = Depends(
        require_permission("suppliers.update")
    ),
    db: Session = Depends(get_db),
) -> Supplier:
    """Update an active organization supplier."""

    return SupplierService(db).update_supplier(
        organization_id=context.organization.id,
        supplier_id=supplier_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.delete(
    "/{supplier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate supplier",
)
def deactivate_supplier(
    supplier_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("suppliers.delete")
    ),
    db: Session = Depends(get_db),
) -> Response:
    """Soft-delete an active organization supplier."""

    SupplierService(db).deactivate_supplier(
        organization_id=context.organization.id,
        supplier_id=supplier_id,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )


@router.patch(
    "/{supplier_id}/reactivate",
    response_model=SupplierResponse,
    summary="Reactivate supplier",
)
def reactivate_supplier(
    supplier_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("suppliers.update")
    ),
    db: Session = Depends(get_db),
) -> Supplier:
    """Reactivate a previously deactivated supplier."""

    return SupplierService(db).reactivate_supplier(
        organization_id=context.organization.id,
        supplier_id=supplier_id,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )
