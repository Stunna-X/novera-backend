"""
Work-order expense routes.

Provides organization-scoped endpoints for recording,
filtering, editing, reviewing, summarizing, deactivating,
and reactivating work-order expenses.
"""

from __future__ import annotations

import uuid
from datetime import date

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
from app.enums.work_order_expense import (
    WorkOrderExpenseCategory,
    WorkOrderExpenseStatus,
)
from app.schemas.work_order_expense import (
    WorkOrderExpenseCreate,
    WorkOrderExpenseListResponse,
    WorkOrderExpenseResponse,
    WorkOrderExpenseStatusChange,
    WorkOrderExpenseSummaryResponse,
    WorkOrderExpenseUpdate,
)
from app.services.work_order_expense_service import (
    WorkOrderExpenseService,
)


router = APIRouter(
    prefix="/organizations/{organization_id}/work-orders",
    tags=["Work Order Expenses"],
)


@router.post(
    "/{work_order_id}/expenses",
    response_model=WorkOrderExpenseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create work-order expense",
)
def create_work_order_expense(
    work_order_id: uuid.UUID,
    payload: WorkOrderExpenseCreate,
    context: OrganizationContext = Depends(
        require_permission("expenses.create")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderExpenseResponse:
    """
    Record a new draft expense against a work order.
    """

    service = WorkOrderExpenseService(db)

    return service.create_expense(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.get(
    "/{work_order_id}/expenses",
    response_model=WorkOrderExpenseListResponse,
    summary="List work-order expenses",
)
def list_work_order_expenses(
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
    category: WorkOrderExpenseCategory | None = Query(
        default=None,
    ),
    expense_status: WorkOrderExpenseStatus | None = Query(
        default=None,
        alias="status",
    ),
    currency: str | None = Query(
        default=None,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
    ),
    is_billable: bool | None = Query(
        default=None,
    ),
    date_from: date | None = Query(
        default=None,
    ),
    date_to: date | None = Query(
        default=None,
    ),
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("expenses.read")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderExpenseListResponse:
    """
    List expenses with optional category, status, currency,
    billable, and date-range filters.
    """

    service = WorkOrderExpenseService(db)

    return service.list_expenses(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        skip=skip,
        limit=limit,
        category=category,
        expense_status=expense_status,
        currency=currency,
        is_billable=is_billable,
        date_from=date_from,
        date_to=date_to,
        include_inactive=include_inactive,
    )


@router.get(
    "/{work_order_id}/expenses/summary",
    response_model=WorkOrderExpenseSummaryResponse,
    summary="Get work-order expense summary",
)
def get_work_order_expense_summary(
    work_order_id: uuid.UUID,
    date_from: date | None = Query(
        default=None,
    ),
    date_to: date | None = Query(
        default=None,
    ),
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("expenses.read")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderExpenseSummaryResponse:
    """
    Return expense totals grouped separately by currency,
    category, and approval status.
    """

    service = WorkOrderExpenseService(db)

    return service.get_summary(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        date_from=date_from,
        date_to=date_to,
        include_inactive=include_inactive,
    )


@router.get(
    "/{work_order_id}/expenses/{expense_id}",
    response_model=WorkOrderExpenseResponse,
    summary="Get work-order expense",
)
def get_work_order_expense(
    work_order_id: uuid.UUID,
    expense_id: uuid.UUID,
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("expenses.read")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderExpenseResponse:
    """
    Return one organization-scoped work-order expense.
    """

    service = WorkOrderExpenseService(db)

    return service.get_expense(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        expense_id=expense_id,
        include_inactive=include_inactive,
    )


@router.patch(
    "/{work_order_id}/expenses/{expense_id}",
    response_model=WorkOrderExpenseResponse,
    summary="Update draft work-order expense",
)
def update_work_order_expense(
    work_order_id: uuid.UUID,
    expense_id: uuid.UUID,
    payload: WorkOrderExpenseUpdate,
    context: OrganizationContext = Depends(
        require_permission("expenses.update")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderExpenseResponse:
    """
    Edit an expense while it remains in draft status.
    """

    service = WorkOrderExpenseService(db)

    return service.update_expense(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        expense_id=expense_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.patch(
    "/{work_order_id}/expenses/{expense_id}/status",
    response_model=WorkOrderExpenseResponse,
    summary="Change work-order expense status",
)
def change_work_order_expense_status(
    work_order_id: uuid.UUID,
    expense_id: uuid.UUID,
    payload: WorkOrderExpenseStatusChange,
    context: OrganizationContext = Depends(
        require_permission("expenses.review")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderExpenseResponse:
    """
    Submit, approve, reject, or reopen a work-order expense.
    """

    service = WorkOrderExpenseService(db)

    return service.change_status(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        expense_id=expense_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.delete(
    "/{work_order_id}/expenses/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate work-order expense",
)
def deactivate_work_order_expense(
    work_order_id: uuid.UUID,
    expense_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("expenses.delete")
    ),
    db: Session = Depends(get_db),
) -> Response:
    """
    Soft-delete a draft or rejected expense.
    """

    service = WorkOrderExpenseService(db)

    service.deactivate_expense(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        expense_id=expense_id,
        actor_user_id=context.membership.user_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )


@router.patch(
    "/{work_order_id}/expenses/{expense_id}/reactivate",
    response_model=WorkOrderExpenseResponse,
    summary="Reactivate work-order expense",
)
def reactivate_work_order_expense(
    work_order_id: uuid.UUID,
    expense_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("expenses.update")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderExpenseResponse:
    """
    Restore a previously deactivated expense.
    """

    service = WorkOrderExpenseService(db)

    return service.reactivate_expense(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        expense_id=expense_id,
        actor_user_id=context.membership.user_id,
    )