"""
Work-order checklist routes.

Provides organization-scoped endpoints for creating,
reading, updating, reordering, completing, skipping,
reopening, deactivating, and reactivating checklist items.
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
from app.schemas.work_order_checklist import (
    WorkOrderChecklistItemCreate,
    WorkOrderChecklistItemResponse,
    WorkOrderChecklistItemUpdate,
    WorkOrderChecklistListResponse,
    WorkOrderChecklistProgressResponse,
    WorkOrderChecklistReorderRequest,
    WorkOrderChecklistStatusUpdate,
)
from app.services.work_order_checklist_service import (
    WorkOrderChecklistService,
)


router = APIRouter(
    prefix="/organizations/{organization_id}/work-orders",
    tags=["Work Order Checklists"],
)


@router.post(
    "/{work_order_id}/checklist-items",
    response_model=WorkOrderChecklistItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create checklist item",
)
def create_checklist_item(
    work_order_id: uuid.UUID,
    payload: WorkOrderChecklistItemCreate,
    context: OrganizationContext = Depends(
        require_permission("work_orders.update")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderChecklistItemResponse:
    """
    Create an operational checklist item.
    """

    service = WorkOrderChecklistService(db)

    return service.create_item(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.get(
    "/{work_order_id}/checklist-items",
    response_model=WorkOrderChecklistListResponse,
    summary="List checklist items",
)
def list_checklist_items(
    work_order_id: uuid.UUID,
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
    ),
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("work_orders.read")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderChecklistListResponse:
    """
    List checklist items in execution order.
    """

    service = WorkOrderChecklistService(db)

    return service.list_items(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        skip=skip,
        limit=limit,
        include_inactive=include_inactive,
    )


@router.get(
    "/{work_order_id}/checklist-items/progress",
    response_model=WorkOrderChecklistProgressResponse,
    summary="Get checklist progress",
)
def get_checklist_progress(
    work_order_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("work_orders.read")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderChecklistProgressResponse:
    """
    Return checklist completion progress.
    """

    service = WorkOrderChecklistService(db)

    return service.get_progress(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
    )


@router.patch(
    "/{work_order_id}/checklist-items/reorder",
    response_model=WorkOrderChecklistListResponse,
    summary="Reorder checklist items",
)
def reorder_checklist_items(
    work_order_id: uuid.UUID,
    payload: WorkOrderChecklistReorderRequest,
    context: OrganizationContext = Depends(
        require_permission("work_orders.update")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderChecklistListResponse:
    """
    Replace the complete active checklist ordering.
    """

    service = WorkOrderChecklistService(db)

    return service.reorder_items(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.get(
    "/{work_order_id}/checklist-items/{item_id}",
    response_model=WorkOrderChecklistItemResponse,
    summary="Get checklist item",
)
def get_checklist_item(
    work_order_id: uuid.UUID,
    item_id: uuid.UUID,
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("work_orders.read")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderChecklistItemResponse:
    """
    Return one checklist item.
    """

    service = WorkOrderChecklistService(db)

    return service.get_item(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        item_id=item_id,
        include_inactive=include_inactive,
    )


@router.patch(
    "/{work_order_id}/checklist-items/{item_id}",
    response_model=WorkOrderChecklistItemResponse,
    summary="Update checklist item",
)
def update_checklist_item(
    work_order_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: WorkOrderChecklistItemUpdate,
    context: OrganizationContext = Depends(
        require_permission("work_orders.update")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderChecklistItemResponse:
    """
    Update checklist-item details.
    """

    service = WorkOrderChecklistService(db)

    return service.update_item(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        item_id=item_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.patch(
    "/{work_order_id}/checklist-items/{item_id}/status",
    response_model=WorkOrderChecklistItemResponse,
    summary="Change checklist-item status",
)
def change_checklist_item_status(
    work_order_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: WorkOrderChecklistStatusUpdate,
    context: OrganizationContext = Depends(
        require_permission("work_orders.update")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderChecklistItemResponse:
    """
    Complete, skip, or reopen a checklist item.
    """

    service = WorkOrderChecklistService(db)

    return service.change_item_status(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        item_id=item_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.delete(
    "/{work_order_id}/checklist-items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate checklist item",
)
def deactivate_checklist_item(
    work_order_id: uuid.UUID,
    item_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("work_orders.update")
    ),
    db: Session = Depends(get_db),
) -> Response:
    """
    Soft-delete a checklist item.
    """

    service = WorkOrderChecklistService(db)

    service.deactivate_item(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        item_id=item_id,
        actor_user_id=context.membership.user_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )


@router.patch(
    "/{work_order_id}/checklist-items/{item_id}/reactivate",
    response_model=WorkOrderChecklistItemResponse,
    summary="Reactivate checklist item",
)
def reactivate_checklist_item(
    work_order_id: uuid.UUID,
    item_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("work_orders.update")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderChecklistItemResponse:
    """
    Reactivate a soft-deleted checklist item.
    """

    service = WorkOrderChecklistService(db)

    return service.reactivate_item(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        item_id=item_id,
        actor_user_id=context.membership.user_id,
    )