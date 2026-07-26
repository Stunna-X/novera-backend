"""
Scheduling routes.

Provides organization-scoped endpoints for dispatch calendar,
schedule conflict checks, work-order scheduling, and dispatch.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from sqlalchemy.orm import Session

from app.api.deps import (
    OrganizationContext,
    require_permission,
)
from app.database.session import get_db
from app.schemas.scheduling import (
    DispatchWorkOrderSchema,
    ScheduleCalendarResponse,
    ScheduleConflictCheckSchema,
    ScheduleConflictResponse,
    ScheduleStatus,
    ScheduleWorkOrderResponse,
    ScheduleWorkOrderSchema,
)
from app.services.scheduling_service import SchedulingService


router = APIRouter(
    prefix="/organizations/{organization_id}/schedule",
    tags=["Scheduling"],
)


@router.get(
    "/work-orders",
    response_model=ScheduleCalendarResponse,
    summary="List schedule calendar work orders",
)
def list_schedule_calendar(
    start: datetime = Query(
        ...,
        description="Calendar window start.",
    ),
    end: datetime = Query(
        ...,
        description="Calendar window end.",
    ),
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
    ),
    status_filter: ScheduleStatus | None = Query(
        default=None,
        alias="status",
    ),
    workforce_profile_id: uuid.UUID | None = Query(
        default=None,
    ),
    asset_id: uuid.UUID | None = Query(
        default=None,
    ),
    customer_id: uuid.UUID | None = Query(
        default=None,
    ),
    customer_site_id: uuid.UUID | None = Query(
        default=None,
    ),
    include_unscheduled: bool = Query(
        default=False,
    ),
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("scheduling.read")
    ),
    db: Session = Depends(get_db),
) -> ScheduleCalendarResponse:
    """
    Return scheduled work orders for a calendar window.
    """

    service = SchedulingService(db)

    return service.list_calendar(
        organization_id=context.organization.id,
        start=start,
        end=end,
        skip=skip,
        limit=limit,
        status_filter=status_filter,
        workforce_profile_id=workforce_profile_id,
        asset_id=asset_id,
        customer_id=customer_id,
        customer_site_id=customer_site_id,
        include_unscheduled=include_unscheduled,
        include_inactive=include_inactive,
    )


@router.post(
    "/work-orders/conflicts",
    response_model=ScheduleConflictResponse,
    summary="Check schedule conflicts",
)
def check_schedule_conflicts(
    payload: ScheduleConflictCheckSchema,
    context: OrganizationContext = Depends(
        require_permission("scheduling.read")
    ),
    db: Session = Depends(get_db),
) -> ScheduleConflictResponse:
    """
    Check whether workforce or assets are already booked in
    the requested time window.
    """

    service = SchedulingService(db)

    return service.check_conflicts(
        organization_id=context.organization.id,
        payload=payload,
    )


@router.patch(
    "/work-orders/{work_order_id}",
    response_model=ScheduleWorkOrderResponse,
    summary="Schedule work order",
)
def schedule_work_order(
    work_order_id: uuid.UUID,
    payload: ScheduleWorkOrderSchema,
    context: OrganizationContext = Depends(
        require_permission("scheduling.update")
    ),
    db: Session = Depends(get_db),
) -> ScheduleWorkOrderResponse:
    """
    Schedule a work order and optionally replace its workforce
    and asset assignments.
    """

    service = SchedulingService(db)

    return service.schedule_work_order(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/work-orders/{work_order_id}/dispatch",
    response_model=ScheduleWorkOrderResponse,
    summary="Dispatch scheduled work order",
)
def dispatch_work_order(
    work_order_id: uuid.UUID,
    payload: DispatchWorkOrderSchema,
    context: OrganizationContext = Depends(
        require_permission("scheduling.dispatch")
    ),
    db: Session = Depends(get_db),
) -> ScheduleWorkOrderResponse:
    """
    Dispatch a scheduled work order after conflict checks.
    """

    service = SchedulingService(db)

    return service.dispatch_work_order(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )
