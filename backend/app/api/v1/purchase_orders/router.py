"""Organization-scoped purchase order routes."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import OrganizationContext, require_permission
from app.database.session import get_db
from app.schemas.purchase_order import (
    AcknowledgePurchaseOrderSchema,
    CancelPurchaseOrderSchema,
    ConvertRequisitionToPurchaseOrderSchema,
    CreatePurchaseOrderSchema,
    PurchaseOrderLineCreate,
    PurchaseOrderLineUpdate,
    PurchaseOrderListResponse,
    PurchaseOrderResponse,
    PurchaseOrderStatus,
    UpdatePurchaseOrderSchema,
)
from app.services.purchase_order_service import PurchaseOrderService


router = APIRouter(
    prefix="/organizations/{organization_id}/purchase-orders",
    tags=["Purchase Orders"],
)


@router.post(
    "",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create purchase order",
)
def create_purchase_order(
    payload: CreatePurchaseOrderSchema,
    context: OrganizationContext = Depends(
        require_permission("purchase_orders.create")
    ),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    service = PurchaseOrderService(db)
    return service.create_purchase_order(
        organization_id=context.organization.id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/from-requisition/{requisition_id}",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create purchase order from requisition",
)
def create_purchase_order_from_requisition(
    requisition_id: uuid.UUID,
    payload: ConvertRequisitionToPurchaseOrderSchema,
    context: OrganizationContext = Depends(
        require_permission("purchase_orders.create")
    ),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    service = PurchaseOrderService(db)
    return service.convert_requisition(
        organization_id=context.organization.id,
        requisition_id=requisition_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.get(
    "",
    response_model=PurchaseOrderListResponse,
    summary="List purchase orders",
)
def list_purchase_orders(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
    ),
    purchase_order_status: PurchaseOrderStatus | None = Query(
        default=None,
        alias="status",
    ),
    supplier_id: uuid.UUID | None = Query(default=None),
    source_requisition_id: uuid.UUID | None = Query(
        default=None,
    ),
    expected_from: date | None = Query(default=None),
    expected_to: date | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    context: OrganizationContext = Depends(
        require_permission("purchase_orders.read")
    ),
    db: Session = Depends(get_db),
) -> PurchaseOrderListResponse:
    service = PurchaseOrderService(db)
    return service.list_purchase_orders(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        search=search,
        status_filter=purchase_order_status,
        supplier_id=supplier_id,
        source_requisition_id=source_requisition_id,
        expected_from=expected_from,
        expected_to=expected_to,
        include_inactive=include_inactive,
    )


@router.get(
    "/{purchase_order_id}",
    response_model=PurchaseOrderResponse,
    summary="Get purchase order",
)
def get_purchase_order(
    purchase_order_id: uuid.UUID,
    include_inactive: bool = Query(default=False),
    context: OrganizationContext = Depends(
        require_permission("purchase_orders.read")
    ),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    service = PurchaseOrderService(db)
    return service.get_purchase_order(
        organization_id=context.organization.id,
        purchase_order_id=purchase_order_id,
        include_inactive=include_inactive,
    )


@router.patch(
    "/{purchase_order_id}",
    response_model=PurchaseOrderResponse,
    summary="Update purchase order",
)
def update_purchase_order(
    purchase_order_id: uuid.UUID,
    payload: UpdatePurchaseOrderSchema,
    context: OrganizationContext = Depends(
        require_permission("purchase_orders.update")
    ),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    service = PurchaseOrderService(db)
    return service.update_purchase_order(
        organization_id=context.organization.id,
        purchase_order_id=purchase_order_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{purchase_order_id}/line-items",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add purchase order line",
)
def add_purchase_order_line(
    purchase_order_id: uuid.UUID,
    payload: PurchaseOrderLineCreate,
    context: OrganizationContext = Depends(
        require_permission("purchase_orders.update")
    ),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    service = PurchaseOrderService(db)
    return service.add_line_item(
        organization_id=context.organization.id,
        purchase_order_id=purchase_order_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.patch(
    "/{purchase_order_id}/line-items/{line_item_id}",
    response_model=PurchaseOrderResponse,
    summary="Update purchase order line",
)
def update_purchase_order_line(
    purchase_order_id: uuid.UUID,
    line_item_id: uuid.UUID,
    payload: PurchaseOrderLineUpdate,
    context: OrganizationContext = Depends(
        require_permission("purchase_orders.update")
    ),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    service = PurchaseOrderService(db)
    return service.update_line_item(
        organization_id=context.organization.id,
        purchase_order_id=purchase_order_id,
        line_item_id=line_item_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.delete(
    "/{purchase_order_id}/line-items/{line_item_id}",
    response_model=PurchaseOrderResponse,
    summary="Remove purchase order line",
)
def remove_purchase_order_line(
    purchase_order_id: uuid.UUID,
    line_item_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("purchase_orders.update")
    ),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    service = PurchaseOrderService(db)
    return service.delete_line_item(
        organization_id=context.organization.id,
        purchase_order_id=purchase_order_id,
        line_item_id=line_item_id,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{purchase_order_id}/issue",
    response_model=PurchaseOrderResponse,
    summary="Issue purchase order",
)
def issue_purchase_order(
    purchase_order_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("purchase_orders.issue")
    ),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    service = PurchaseOrderService(db)
    return service.issue_purchase_order(
        organization_id=context.organization.id,
        purchase_order_id=purchase_order_id,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{purchase_order_id}/acknowledge",
    response_model=PurchaseOrderResponse,
    summary="Record purchase order acknowledgement",
)
def acknowledge_purchase_order(
    purchase_order_id: uuid.UUID,
    payload: AcknowledgePurchaseOrderSchema,
    context: OrganizationContext = Depends(
        require_permission("purchase_orders.acknowledge")
    ),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    service = PurchaseOrderService(db)
    return service.acknowledge_purchase_order(
        organization_id=context.organization.id,
        purchase_order_id=purchase_order_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{purchase_order_id}/cancel",
    response_model=PurchaseOrderResponse,
    summary="Cancel purchase order",
)
def cancel_purchase_order(
    purchase_order_id: uuid.UUID,
    payload: CancelPurchaseOrderSchema,
    context: OrganizationContext = Depends(
        require_permission("purchase_orders.cancel")
    ),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    service = PurchaseOrderService(db)
    return service.cancel_purchase_order(
        organization_id=context.organization.id,
        purchase_order_id=purchase_order_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{purchase_order_id}/close",
    response_model=PurchaseOrderResponse,
    summary="Close purchase order",
)
def close_purchase_order(
    purchase_order_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("purchase_orders.close")
    ),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    service = PurchaseOrderService(db)
    return service.close_purchase_order(
        organization_id=context.organization.id,
        purchase_order_id=purchase_order_id,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )
