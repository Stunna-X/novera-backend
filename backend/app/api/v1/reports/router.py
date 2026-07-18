"""
Reports routes.

Provides organization-scoped operations, finance,
work-order performance, and quote conversion reports.
"""

from __future__ import annotations

from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy.orm import Session

from app.api.deps import (
    OrganizationContext,
    require_permission,
)
from app.database.session import get_db
from app.schemas.reports import (
    FinanceReportResponse,
    OperationsReportResponse,
    QuoteConversionReportResponse,
    WorkOrderPerformanceReportResponse,
)
from app.services.reports_service import ReportsService


router = APIRouter(
    prefix="/organizations/{organization_id}/reports",
    tags=["Reports"],
)


@router.get(
    "/operations",
    response_model=OperationsReportResponse,
    summary="Get operations report",
)
def get_operations_report(
    date_from: date | None = Query(
        default=None,
        description="Optional inclusive report start date.",
    ),
    date_to: date | None = Query(
        default=None,
        description="Optional inclusive report end date.",
    ),
    context: OrganizationContext = Depends(
        require_permission("reports.read")
    ),
    db: Session = Depends(get_db),
) -> OperationsReportResponse:
    """
    Return operational counts, closeout readiness, and assignment usage.
    """

    _validate_date_range(
        date_from=date_from,
        date_to=date_to,
    )

    service = ReportsService(db)

    return service.get_operations_report(
        organization_id=context.organization.id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/finance",
    response_model=FinanceReportResponse,
    summary="Get finance report",
)
def get_finance_report(
    date_from: date | None = Query(
        default=None,
        description="Optional inclusive report start date.",
    ),
    date_to: date | None = Query(
        default=None,
        description="Optional inclusive report end date.",
    ),
    context: OrganizationContext = Depends(
        require_permission("reports.read")
    ),
    db: Session = Depends(get_db),
) -> FinanceReportResponse:
    """
    Return invoice totals, paid totals, outstanding balances,
    and payment method totals.
    """

    _validate_date_range(
        date_from=date_from,
        date_to=date_to,
    )

    service = ReportsService(db)

    return service.get_finance_report(
        organization_id=context.organization.id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/work-orders",
    response_model=WorkOrderPerformanceReportResponse,
    summary="Get work-order performance report",
)
def get_work_order_performance_report(
    date_from: date | None = Query(
        default=None,
        description="Optional inclusive report start date.",
    ),
    date_to: date | None = Query(
        default=None,
        description="Optional inclusive report end date.",
    ),
    context: OrganizationContext = Depends(
        require_permission("reports.read")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderPerformanceReportResponse:
    """
    Return work-order completion rate, average completion hours,
    and grouped work-order counts.
    """

    _validate_date_range(
        date_from=date_from,
        date_to=date_to,
    )

    service = ReportsService(db)

    return service.get_work_order_performance_report(
        organization_id=context.organization.id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/quotes",
    response_model=QuoteConversionReportResponse,
    summary="Get quote conversion report",
)
def get_quote_conversion_report(
    date_from: date | None = Query(
        default=None,
        description="Optional inclusive report start date.",
    ),
    date_to: date | None = Query(
        default=None,
        description="Optional inclusive report end date.",
    ),
    context: OrganizationContext = Depends(
        require_permission("reports.read")
    ),
    db: Session = Depends(get_db),
) -> QuoteConversionReportResponse:
    """
    Return quote conversion counts and quote value by currency.
    """

    _validate_date_range(
        date_from=date_from,
        date_to=date_to,
    )

    service = ReportsService(db)

    return service.get_quote_conversion_report(
        organization_id=context.organization.id,
        date_from=date_from,
        date_to=date_to,
    )


def _validate_date_range(
    *,
    date_from: date | None,
    date_to: date | None,
) -> None:
    """
    Validate optional report date range.
    """

    if (
        date_from is not None
        and date_to is not None
        and date_from > date_to
    ):
        raise HTTPException(
            status_code=422,
            detail="date_from cannot be after date_to.",
        )
