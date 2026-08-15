"""Organization-scoped supplier return endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import OrganizationContext, require_permission
from app.database.session import get_db
from app.schemas.supplier_return import (
    CancelSupplierReturnSchema,
    CompleteSupplierReturnSchema,
    CreateSupplierReturnSchema,
    SupplierReturnLineCreate,
    SupplierReturnLineUpdate,
    SupplierReturnListResponse,
    SupplierReturnResponse,
    SupplierReturnStatus,
    UpdateSupplierReturnSchema,
)
from app.services.supplier_return_service import SupplierReturnService


router = APIRouter(
    prefix="/organizations/{organization_id}/supplier-returns",
    tags=["Supplier Returns"],
)


@router.post(
    "",
    response_model=SupplierReturnResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create supplier return",
)
def create_supplier_return(
    payload: CreateSupplierReturnSchema,
    context: OrganizationContext = Depends(
        require_permission("supplier_returns.create")
    ),
    db: Session = Depends(get_db),
) -> SupplierReturnResponse:
    return SupplierReturnService(db).create_supplier_return(
        context.organization.id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.get(
    "",
    response_model=SupplierReturnListResponse,
    summary="List supplier returns",
)
def list_supplier_returns(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    supplier_id: uuid.UUID | None = Query(default=None),
    status_filter: SupplierReturnStatus | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    context: OrganizationContext = Depends(
        require_permission("supplier_returns.read")
    ),
    db: Session = Depends(get_db),
) -> SupplierReturnListResponse:
    return SupplierReturnService(db).list_supplier_returns(
        context.organization.id,
        skip=skip,
        limit=limit,
        supplier_id=supplier_id,
        status_filter=(
            status_filter.value
            if status_filter is not None
            else None
        ),
        search=search,
    )


@router.get(
    "/{supplier_return_id}",
    response_model=SupplierReturnResponse,
    summary="Get supplier return",
)
def get_supplier_return(
    supplier_return_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("supplier_returns.read")
    ),
    db: Session = Depends(get_db),
) -> SupplierReturnResponse:
    return SupplierReturnService(db).get_supplier_return(
        context.organization.id,
        supplier_return_id,
    )


@router.patch(
    "/{supplier_return_id}",
    response_model=SupplierReturnResponse,
    summary="Update supplier return",
)
def update_supplier_return(
    supplier_return_id: uuid.UUID,
    payload: UpdateSupplierReturnSchema,
    context: OrganizationContext = Depends(
        require_permission("supplier_returns.update")
    ),
    db: Session = Depends(get_db),
) -> SupplierReturnResponse:
    return SupplierReturnService(db).update_supplier_return(
        context.organization.id,
        supplier_return_id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{supplier_return_id}/line-items",
    response_model=SupplierReturnResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add supplier return line",
)
def add_supplier_return_line(
    supplier_return_id: uuid.UUID,
    payload: SupplierReturnLineCreate,
    context: OrganizationContext = Depends(
        require_permission("supplier_returns.update")
    ),
    db: Session = Depends(get_db),
) -> SupplierReturnResponse:
    return SupplierReturnService(db).add_return_line(
        context.organization.id,
        supplier_return_id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.patch(
    "/{supplier_return_id}/line-items/{line_item_id}",
    response_model=SupplierReturnResponse,
    summary="Update supplier return line",
)
def update_supplier_return_line(
    supplier_return_id: uuid.UUID,
    line_item_id: uuid.UUID,
    payload: SupplierReturnLineUpdate,
    context: OrganizationContext = Depends(
        require_permission("supplier_returns.update")
    ),
    db: Session = Depends(get_db),
) -> SupplierReturnResponse:
    return SupplierReturnService(db).update_return_line(
        context.organization.id,
        supplier_return_id,
        line_item_id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.delete(
    "/{supplier_return_id}/line-items/{line_item_id}",
    response_model=SupplierReturnResponse,
    summary="Remove supplier return line",
)
def delete_supplier_return_line(
    supplier_return_id: uuid.UUID,
    line_item_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("supplier_returns.update")
    ),
    db: Session = Depends(get_db),
) -> SupplierReturnResponse:
    return SupplierReturnService(db).delete_return_line(
        context.organization.id,
        supplier_return_id,
        line_item_id,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{supplier_return_id}/dispatch",
    response_model=SupplierReturnResponse,
    summary="Dispatch supplier return",
)
def dispatch_supplier_return(
    supplier_return_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("supplier_returns.dispatch")
    ),
    db: Session = Depends(get_db),
) -> SupplierReturnResponse:
    return SupplierReturnService(db).dispatch_supplier_return(
        context.organization.id,
        supplier_return_id,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{supplier_return_id}/complete",
    response_model=SupplierReturnResponse,
    summary="Complete supplier return",
)
def complete_supplier_return(
    supplier_return_id: uuid.UUID,
    payload: CompleteSupplierReturnSchema,
    context: OrganizationContext = Depends(
        require_permission("supplier_returns.complete")
    ),
    db: Session = Depends(get_db),
) -> SupplierReturnResponse:
    return SupplierReturnService(db).complete_supplier_return(
        context.organization.id,
        supplier_return_id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{supplier_return_id}/cancel",
    response_model=SupplierReturnResponse,
    summary="Cancel supplier return",
)
def cancel_supplier_return(
    supplier_return_id: uuid.UUID,
    payload: CancelSupplierReturnSchema,
    context: OrganizationContext = Depends(
        require_permission("supplier_returns.cancel")
    ),
    db: Session = Depends(get_db),
) -> SupplierReturnResponse:
    return SupplierReturnService(db).cancel_supplier_return(
        context.organization.id,
        supplier_return_id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )
