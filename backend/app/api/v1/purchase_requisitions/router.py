"""Organization-scoped purchase requisition routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import OrganizationContext, require_permission
from app.database.session import get_db
from app.schemas.purchase_requisition import (
    CancelPurchaseRequisitionSchema,
    CreatePurchaseRequisitionSchema,
    PurchaseRequisitionLineCreate,
    PurchaseRequisitionLineUpdate,
    PurchaseRequisitionListResponse,
    PurchaseRequisitionPriority,
    PurchaseRequisitionResponse,
    PurchaseRequisitionStatus,
    RejectPurchaseRequisitionSchema,
    UpdatePurchaseRequisitionSchema,
)
from app.services.purchase_requisition_service import (
    PurchaseRequisitionService,
)


router = APIRouter(
    prefix=(
        "/organizations/{organization_id}/purchase-requisitions"
    ),
    tags=["Purchase Requisitions"],
)


@router.post(
    "",
    response_model=PurchaseRequisitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create purchase requisition",
)
def create_purchase_requisition(
    payload: CreatePurchaseRequisitionSchema,
    context: OrganizationContext = Depends(
        require_permission("purchase_requisitions.create")
    ),
    db: Session = Depends(get_db),
) -> PurchaseRequisitionResponse:
    service = PurchaseRequisitionService(db)
    return service.create_requisition(
        organization_id=context.organization.id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.get(
    "",
    response_model=PurchaseRequisitionListResponse,
    summary="List purchase requisitions",
)
def list_purchase_requisitions(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
    ),
    requisition_status: PurchaseRequisitionStatus | None = Query(
        default=None,
        alias="status",
    ),
    priority: PurchaseRequisitionPriority | None = Query(
        default=None,
    ),
    preferred_supplier_id: uuid.UUID | None = Query(
        default=None,
    ),
    work_order_id: uuid.UUID | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    context: OrganizationContext = Depends(
        require_permission("purchase_requisitions.read")
    ),
    db: Session = Depends(get_db),
) -> PurchaseRequisitionListResponse:
    service = PurchaseRequisitionService(db)
    return service.list_requisitions(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        search=search,
        status_filter=requisition_status,
        priority=priority,
        preferred_supplier_id=preferred_supplier_id,
        work_order_id=work_order_id,
        include_inactive=include_inactive,
    )


@router.get(
    "/{requisition_id}",
    response_model=PurchaseRequisitionResponse,
    summary="Get purchase requisition",
)
def get_purchase_requisition(
    requisition_id: uuid.UUID,
    include_inactive: bool = Query(default=False),
    context: OrganizationContext = Depends(
        require_permission("purchase_requisitions.read")
    ),
    db: Session = Depends(get_db),
) -> PurchaseRequisitionResponse:
    service = PurchaseRequisitionService(db)
    return service.get_requisition(
        organization_id=context.organization.id,
        requisition_id=requisition_id,
        include_inactive=include_inactive,
    )


@router.patch(
    "/{requisition_id}",
    response_model=PurchaseRequisitionResponse,
    summary="Update purchase requisition",
)
def update_purchase_requisition(
    requisition_id: uuid.UUID,
    payload: UpdatePurchaseRequisitionSchema,
    context: OrganizationContext = Depends(
        require_permission("purchase_requisitions.update")
    ),
    db: Session = Depends(get_db),
) -> PurchaseRequisitionResponse:
    service = PurchaseRequisitionService(db)
    return service.update_requisition(
        organization_id=context.organization.id,
        requisition_id=requisition_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{requisition_id}/line-items",
    response_model=PurchaseRequisitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add purchase requisition line",
)
def add_purchase_requisition_line(
    requisition_id: uuid.UUID,
    payload: PurchaseRequisitionLineCreate,
    context: OrganizationContext = Depends(
        require_permission("purchase_requisitions.update")
    ),
    db: Session = Depends(get_db),
) -> PurchaseRequisitionResponse:
    service = PurchaseRequisitionService(db)
    return service.add_line_item(
        organization_id=context.organization.id,
        requisition_id=requisition_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.patch(
    "/{requisition_id}/line-items/{line_item_id}",
    response_model=PurchaseRequisitionResponse,
    summary="Update purchase requisition line",
)
def update_purchase_requisition_line(
    requisition_id: uuid.UUID,
    line_item_id: uuid.UUID,
    payload: PurchaseRequisitionLineUpdate,
    context: OrganizationContext = Depends(
        require_permission("purchase_requisitions.update")
    ),
    db: Session = Depends(get_db),
) -> PurchaseRequisitionResponse:
    service = PurchaseRequisitionService(db)
    return service.update_line_item(
        organization_id=context.organization.id,
        requisition_id=requisition_id,
        line_item_id=line_item_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.delete(
    "/{requisition_id}/line-items/{line_item_id}",
    response_model=PurchaseRequisitionResponse,
    summary="Remove purchase requisition line",
)
def remove_purchase_requisition_line(
    requisition_id: uuid.UUID,
    line_item_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("purchase_requisitions.update")
    ),
    db: Session = Depends(get_db),
) -> PurchaseRequisitionResponse:
    service = PurchaseRequisitionService(db)
    return service.delete_line_item(
        organization_id=context.organization.id,
        requisition_id=requisition_id,
        line_item_id=line_item_id,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{requisition_id}/submit",
    response_model=PurchaseRequisitionResponse,
    summary="Submit purchase requisition",
)
def submit_purchase_requisition(
    requisition_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("purchase_requisitions.submit")
    ),
    db: Session = Depends(get_db),
) -> PurchaseRequisitionResponse:
    service = PurchaseRequisitionService(db)
    return service.submit_requisition(
        organization_id=context.organization.id,
        requisition_id=requisition_id,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{requisition_id}/approve",
    response_model=PurchaseRequisitionResponse,
    summary="Approve purchase requisition",
)
def approve_purchase_requisition(
    requisition_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("purchase_requisitions.approve")
    ),
    db: Session = Depends(get_db),
) -> PurchaseRequisitionResponse:
    service = PurchaseRequisitionService(db)
    return service.approve_requisition(
        organization_id=context.organization.id,
        requisition_id=requisition_id,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{requisition_id}/reject",
    response_model=PurchaseRequisitionResponse,
    summary="Reject purchase requisition",
)
def reject_purchase_requisition(
    requisition_id: uuid.UUID,
    payload: RejectPurchaseRequisitionSchema,
    context: OrganizationContext = Depends(
        require_permission("purchase_requisitions.approve")
    ),
    db: Session = Depends(get_db),
) -> PurchaseRequisitionResponse:
    service = PurchaseRequisitionService(db)
    return service.reject_requisition(
        organization_id=context.organization.id,
        requisition_id=requisition_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{requisition_id}/cancel",
    response_model=PurchaseRequisitionResponse,
    summary="Cancel purchase requisition",
)
def cancel_purchase_requisition(
    requisition_id: uuid.UUID,
    payload: CancelPurchaseRequisitionSchema,
    context: OrganizationContext = Depends(
        require_permission("purchase_requisitions.cancel")
    ),
    db: Session = Depends(get_db),
) -> PurchaseRequisitionResponse:
    service = PurchaseRequisitionService(db)
    return service.cancel_requisition(
        organization_id=context.organization.id,
        requisition_id=requisition_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )
