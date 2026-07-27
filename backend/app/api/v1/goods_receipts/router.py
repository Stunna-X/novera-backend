"""Organization-scoped goods receipt routes."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import OrganizationContext, require_permission
from app.database.session import get_db
from app.schemas.goods_receipt import (
    CancelGoodsReceiptSchema,
    CreateGoodsReceiptSchema,
    GoodsReceiptLineCreate,
    GoodsReceiptLineUpdate,
    GoodsReceiptListResponse,
    GoodsReceiptResponse,
    GoodsReceiptStatus,
    UpdateGoodsReceiptSchema,
)
from app.services.goods_receipt_service import GoodsReceiptService


router = APIRouter(
    prefix="/organizations/{organization_id}/goods-receipts",
    tags=["Goods Receipts"],
)


@router.post(
    "",
    response_model=GoodsReceiptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create goods receipt",
)
def create_goods_receipt(
    payload: CreateGoodsReceiptSchema,
    context: OrganizationContext = Depends(
        require_permission("goods_receipts.create")
    ),
    db: Session = Depends(get_db),
) -> GoodsReceiptResponse:
    service = GoodsReceiptService(db)
    return service.create_goods_receipt(
        organization_id=context.organization.id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.get(
    "",
    response_model=GoodsReceiptListResponse,
    summary="List goods receipts",
)
def list_goods_receipts(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
    ),
    goods_receipt_status: GoodsReceiptStatus | None = Query(
        default=None,
        alias="status",
    ),
    purchase_order_id: uuid.UUID | None = Query(default=None),
    supplier_id: uuid.UUID | None = Query(default=None),
    receiving_location_id: uuid.UUID | None = Query(default=None),
    received_from: datetime | None = Query(default=None),
    received_to: datetime | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    context: OrganizationContext = Depends(
        require_permission("goods_receipts.read")
    ),
    db: Session = Depends(get_db),
) -> GoodsReceiptListResponse:
    service = GoodsReceiptService(db)
    return service.list_goods_receipts(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        search=search,
        status_filter=goods_receipt_status,
        purchase_order_id=purchase_order_id,
        supplier_id=supplier_id,
        receiving_location_id=receiving_location_id,
        received_from=received_from,
        received_to=received_to,
        include_inactive=include_inactive,
    )


@router.get(
    "/{goods_receipt_id}",
    response_model=GoodsReceiptResponse,
    summary="Get goods receipt",
)
def get_goods_receipt(
    goods_receipt_id: uuid.UUID,
    include_inactive: bool = Query(default=False),
    context: OrganizationContext = Depends(
        require_permission("goods_receipts.read")
    ),
    db: Session = Depends(get_db),
) -> GoodsReceiptResponse:
    service = GoodsReceiptService(db)
    return service.get_goods_receipt(
        organization_id=context.organization.id,
        goods_receipt_id=goods_receipt_id,
        include_inactive=include_inactive,
    )


@router.patch(
    "/{goods_receipt_id}",
    response_model=GoodsReceiptResponse,
    summary="Update goods receipt",
)
def update_goods_receipt(
    goods_receipt_id: uuid.UUID,
    payload: UpdateGoodsReceiptSchema,
    context: OrganizationContext = Depends(
        require_permission("goods_receipts.update")
    ),
    db: Session = Depends(get_db),
) -> GoodsReceiptResponse:
    service = GoodsReceiptService(db)
    return service.update_goods_receipt(
        organization_id=context.organization.id,
        goods_receipt_id=goods_receipt_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{goods_receipt_id}/line-items",
    response_model=GoodsReceiptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add goods receipt line",
)
def add_goods_receipt_line(
    goods_receipt_id: uuid.UUID,
    payload: GoodsReceiptLineCreate,
    context: OrganizationContext = Depends(
        require_permission("goods_receipts.update")
    ),
    db: Session = Depends(get_db),
) -> GoodsReceiptResponse:
    service = GoodsReceiptService(db)
    return service.add_line_item(
        organization_id=context.organization.id,
        goods_receipt_id=goods_receipt_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.patch(
    "/{goods_receipt_id}/line-items/{line_item_id}",
    response_model=GoodsReceiptResponse,
    summary="Update goods receipt line",
)
def update_goods_receipt_line(
    goods_receipt_id: uuid.UUID,
    line_item_id: uuid.UUID,
    payload: GoodsReceiptLineUpdate,
    context: OrganizationContext = Depends(
        require_permission("goods_receipts.update")
    ),
    db: Session = Depends(get_db),
) -> GoodsReceiptResponse:
    service = GoodsReceiptService(db)
    return service.update_line_item(
        organization_id=context.organization.id,
        goods_receipt_id=goods_receipt_id,
        line_item_id=line_item_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.delete(
    "/{goods_receipt_id}/line-items/{line_item_id}",
    response_model=GoodsReceiptResponse,
    summary="Remove goods receipt line",
)
def remove_goods_receipt_line(
    goods_receipt_id: uuid.UUID,
    line_item_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("goods_receipts.update")
    ),
    db: Session = Depends(get_db),
) -> GoodsReceiptResponse:
    service = GoodsReceiptService(db)
    return service.delete_line_item(
        organization_id=context.organization.id,
        goods_receipt_id=goods_receipt_id,
        line_item_id=line_item_id,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{goods_receipt_id}/post",
    response_model=GoodsReceiptResponse,
    summary="Post goods receipt",
)
def post_goods_receipt(
    goods_receipt_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("goods_receipts.post")
    ),
    db: Session = Depends(get_db),
) -> GoodsReceiptResponse:
    service = GoodsReceiptService(db)
    return service.post_goods_receipt(
        organization_id=context.organization.id,
        goods_receipt_id=goods_receipt_id,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{goods_receipt_id}/cancel",
    response_model=GoodsReceiptResponse,
    summary="Cancel goods receipt",
)
def cancel_goods_receipt(
    goods_receipt_id: uuid.UUID,
    payload: CancelGoodsReceiptSchema,
    context: OrganizationContext = Depends(
        require_permission("goods_receipts.cancel")
    ),
    db: Session = Depends(get_db),
) -> GoodsReceiptResponse:
    service = GoodsReceiptService(db)
    return service.cancel_goods_receipt(
        organization_id=context.organization.id,
        goods_receipt_id=goods_receipt_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )
