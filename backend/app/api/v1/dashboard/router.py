"""
Dashboard routes.

Provides organization-scoped operational and commercial analytics
for the Novera dashboard.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    OrganizationContext,
    require_permission,
)
from app.database.session import get_db
from app.schemas.dashboard import (
    DashboardFinanceResponse,
    DashboardOverviewResponse,
    DashboardTeamResponse,
    DashboardWorkOrdersResponse,
)
from app.services.dashboard_service import DashboardService


router = APIRouter(
    prefix="/organizations/{organization_id}/dashboard",
    tags=["Dashboard"],
)


@router.get(
    "/overview",
    response_model=DashboardOverviewResponse,
    summary="Get dashboard overview",
)
def get_dashboard_overview(
    context: OrganizationContext = Depends(
        require_permission("dashboard.read")
    ),
    db: Session = Depends(get_db),
) -> DashboardOverviewResponse:
    """
    Return high-level operational, quote, closeout, and invoice metrics.

    Requires:
    - work_orders.read
    """

    service = DashboardService(db)

    return service.get_overview(
        organization_id=context.organization.id,
    )


@router.get(
    "/work-orders",
    response_model=DashboardWorkOrdersResponse,
    summary="Get work-order dashboard analytics",
)
def get_work_order_dashboard(
    start: datetime | None = Query(
        default=None,
        description="Optional schedule window start.",
    ),
    end: datetime | None = Query(
        default=None,
        description="Optional schedule window end.",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
    ),
    context: OrganizationContext = Depends(
        require_permission("dashboard.read")
    ),
    db: Session = Depends(get_db),
) -> DashboardWorkOrdersResponse:
    """
    Return status counts, priority counts, upcoming jobs, and recent completions.

    Requires:
    - work_orders.read
    """

    service = DashboardService(db)

    return service.get_work_orders(
        organization_id=context.organization.id,
        start=start,
        end=end,
        limit=limit,
    )


@router.get(
    "/finance",
    response_model=DashboardFinanceResponse,
    summary="Get finance dashboard analytics",
)
def get_finance_dashboard(
    context: OrganizationContext = Depends(
        require_permission("dashboard.read")
    ),
    db: Session = Depends(get_db),
) -> DashboardFinanceResponse:
    """
    Return quote and invoice financial metrics.

    Requires:
    - work_orders.read
    """

    service = DashboardService(db)

    return service.get_finance(
        organization_id=context.organization.id,
    )


@router.get(
    "/team",
    response_model=DashboardTeamResponse,
    summary="Get team and asset dashboard analytics",
)
def get_team_dashboard(
    limit: int = Query(
        default=25,
        ge=1,
        le=100,
    ),
    context: OrganizationContext = Depends(
        require_permission("dashboard.read")
    ),
    db: Session = Depends(get_db),
) -> DashboardTeamResponse:
    """
    Return workforce and asset availability and workload metrics.

    Requires:
    - work_orders.read
    """

    service = DashboardService(db)

    return service.get_team(
        organization_id=context.organization.id,
        limit=limit,
    )
