"""
Work-order routes.

Provides organization-scoped endpoints for work orders,
activities, status transitions, workforce, and assets.
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
from app.schemas.work_order import (
    ChangeWorkOrderStatusSchema,
    CreateWorkOrderSchema,
    UpdateWorkOrderSchema,
    WorkOrderListResponse,
    WorkOrderPriority,
    WorkOrderResponse,
    WorkOrderStatus,
)
from app.schemas.work_order_activity import (
    WorkOrderActivityListResponse,
    WorkOrderActivityType,
)
from app.services.work_order_activity_service import (
    WorkOrderActivityService,
)
from app.services.work_order_service import WorkOrderService


router = APIRouter(
    prefix="/organizations/{organization_id}/work-orders",
    tags=["Work Orders"],
)


@router.post(
    "",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create work order",
)
def create_work_order(
    payload: CreateWorkOrderSchema,
    context: OrganizationContext = Depends(
        require_permission("work_orders.create")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderResponse:
    """
    Create an organization work order.
    """

    service = WorkOrderService(db)

    return service.create_work_order(
        organization_id=context.organization.id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.get(
    "",
    response_model=WorkOrderListResponse,
    summary="List work orders",
)
def list_work_orders(
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
        max_length=200,
    ),
    work_order_status: WorkOrderStatus | None = Query(
        default=None,
        alias="status",
    ),
    priority: WorkOrderPriority | None = Query(
        default=None,
    ),
    customer_id: uuid.UUID | None = Query(
        default=None,
    ),
    customer_site_id: uuid.UUID | None = Query(
        default=None,
    ),
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("work_orders.read")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderListResponse:
    """
    List organization work orders.
    """

    service = WorkOrderService(db)

    return service.list_work_orders(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        search=search,
        status_filter=work_order_status,
        priority=priority,
        customer_id=customer_id,
        customer_site_id=customer_site_id,
        include_inactive=include_inactive,
    )


@router.get(
    "/{work_order_id}",
    response_model=WorkOrderResponse,
    summary="Get work order",
)
def get_work_order(
    work_order_id: uuid.UUID,
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("work_orders.read")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderResponse:
    """
    Return one work order.
    """

    service = WorkOrderService(db)

    return service.get_work_order(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        include_inactive=include_inactive,
    )


@router.get(
    "/{work_order_id}/activities",
    response_model=WorkOrderActivityListResponse,
    summary="List work-order activities",
)
def list_work_order_activities(
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
    activity_type: WorkOrderActivityType | None = Query(
        default=None,
    ),
    include_inactive_work_order: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("work_orders.read")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderActivityListResponse:
    """
    Return the work-order operational timeline.
    """

    service = WorkOrderActivityService(db)

    return service.list_activities(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        skip=skip,
        limit=limit,
        activity_type=activity_type,
        include_inactive_work_order=(
            include_inactive_work_order
        ),
    )


@router.patch(
    "/{work_order_id}",
    response_model=WorkOrderResponse,
    summary="Update work order",
)
def update_work_order(
    work_order_id: uuid.UUID,
    payload: UpdateWorkOrderSchema,
    context: OrganizationContext = Depends(
        require_permission("work_orders.update")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderResponse:
    """
    Update work-order details.
    """

    service = WorkOrderService(db)

    return service.update_work_order(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.patch(
    "/{work_order_id}/status",
    response_model=WorkOrderResponse,
    summary="Change work-order status",
)
def change_work_order_status(
    work_order_id: uuid.UUID,
    payload: ChangeWorkOrderStatusSchema,
    context: OrganizationContext = Depends(
        require_permission("work_orders.status")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderResponse:
    """
    Change work-order operational status.
    """

    service = WorkOrderService(db)

    return service.change_status(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.delete(
    "/{work_order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate work order",
)
def deactivate_work_order(
    work_order_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("work_orders.delete")
    ),
    db: Session = Depends(get_db),
) -> Response:
    """
    Soft-delete a work order.
    """

    service = WorkOrderService(db)

    service.deactivate_work_order(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        actor_user_id=context.membership.user_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )


@router.patch(
    "/{work_order_id}/reactivate",
    response_model=WorkOrderResponse,
    summary="Reactivate work order",
)
def reactivate_work_order(
    work_order_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("work_orders.update")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderResponse:
    """
    Reactivate a work order.
    """

    service = WorkOrderService(db)

    return service.reactivate_work_order(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/{work_order_id}/workforce/{workforce_profile_id}",
    response_model=WorkOrderResponse,
    summary="Assign workforce member",
)
def assign_workforce_member(
    work_order_id: uuid.UUID,
    workforce_profile_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("work_orders.assign")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderResponse:
    """
    Assign a workforce member to a work order.
    """

    service = WorkOrderService(db)

    return service.assign_workforce(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        workforce_profile_id=workforce_profile_id,
        actor_user_id=context.membership.user_id,
    )


@router.delete(
    "/{work_order_id}/workforce/{workforce_profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove workforce member",
)
def remove_workforce_member(
    work_order_id: uuid.UUID,
    workforce_profile_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("work_orders.assign")
    ),
    db: Session = Depends(get_db),
) -> Response:
    """
    Remove a workforce member from a work order.
    """

    service = WorkOrderService(db)

    service.remove_workforce(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        workforce_profile_id=workforce_profile_id,
        actor_user_id=context.membership.user_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )


@router.post(
    "/{work_order_id}/assets/{asset_id}",
    response_model=WorkOrderResponse,
    summary="Assign asset",
)
def assign_asset(
    work_order_id: uuid.UUID,
    asset_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("work_orders.assign")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderResponse:
    """
    Assign an operational asset to a work order.
    """

    service = WorkOrderService(db)

    return service.assign_asset(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        asset_id=asset_id,
        actor_user_id=context.membership.user_id,
    )


@router.delete(
    "/{work_order_id}/assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove asset",
)
def remove_asset(
    work_order_id: uuid.UUID,
    asset_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("work_orders.assign")
    ),
    db: Session = Depends(get_db),
) -> Response:
    """
    Remove an operational asset from a work order.
    """

    service = WorkOrderService(db)

    service.remove_asset(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        asset_id=asset_id,
        actor_user_id=context.membership.user_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )