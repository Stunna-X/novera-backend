"""Tenant-scoped procurement reporting and spend analytics routes."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import OrganizationContext, require_permission
from app.database.session import get_db
from app.schemas.procurement_analytics import (
    AccountsPayableResponse,
    MatchExceptionResponse,
    PaymentHistoryResponse,
    ProcurementOverviewResponse,
    PurchaseOrderCommitmentResponse,
    ReceiptVarianceResponse,
    SupplierSpendResponse,
)
from app.services.procurement_analytics_service import (
    ProcurementAnalyticsService,
)


router = APIRouter(
    prefix="/organizations/{organization_id}/procurement-analytics",
    tags=["Procurement Analytics"],
)


def _service(db: Session) -> ProcurementAnalyticsService:
    return ProcurementAnalyticsService(db)


@router.get(
    "/overview",
    response_model=ProcurementOverviewResponse,
    summary="Get procurement overview",
)
def get_procurement_overview(
    as_of_date: date | None = Query(default=None),
    payment_date_from: date | None = Query(default=None),
    payment_date_to: date | None = Query(default=None),
    context: OrganizationContext = Depends(
        require_permission("procurement_analytics.read")
    ),
    db: Session = Depends(get_db),
) -> ProcurementOverviewResponse:
    return _service(db).get_overview(
        organization_id=context.organization.id,
        as_of_date=as_of_date,
        payment_date_from=payment_date_from,
        payment_date_to=payment_date_to,
    )


@router.get(
    "/supplier-spend",
    response_model=SupplierSpendResponse,
    summary="Get supplier spend analytics",
)
def get_supplier_spend(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    supplier_id: uuid.UUID | None = Query(default=None),
    currency: str | None = Query(
        default=None,
        min_length=3,
        max_length=3,
    ),
    limit: int = Query(default=100, ge=1, le=500),
    context: OrganizationContext = Depends(
        require_permission("procurement_analytics.read")
    ),
    db: Session = Depends(get_db),
) -> SupplierSpendResponse:
    return _service(db).get_supplier_spend(
        organization_id=context.organization.id,
        date_from=date_from,
        date_to=date_to,
        supplier_id=supplier_id,
        currency=currency,
        limit=limit,
    )


@router.get(
    "/purchase-order-commitments",
    response_model=PurchaseOrderCommitmentResponse,
    summary="List open purchase-order commitments",
)
def get_purchase_order_commitments(
    supplier_id: uuid.UUID | None = Query(default=None),
    currency: str | None = Query(
        default=None,
        min_length=3,
        max_length=3,
    ),
    limit: int = Query(default=100, ge=1, le=500),
    context: OrganizationContext = Depends(
        require_permission("procurement_analytics.read")
    ),
    db: Session = Depends(get_db),
) -> PurchaseOrderCommitmentResponse:
    return _service(db).get_commitments(
        organization_id=context.organization.id,
        supplier_id=supplier_id,
        currency=currency,
        limit=limit,
    )


@router.get(
    "/accounts-payable",
    response_model=AccountsPayableResponse,
    summary="List outstanding supplier payables",
)
def get_accounts_payable(
    as_of_date: date | None = Query(default=None),
    supplier_id: uuid.UUID | None = Query(default=None),
    currency: str | None = Query(
        default=None,
        min_length=3,
        max_length=3,
    ),
    limit: int = Query(default=100, ge=1, le=500),
    context: OrganizationContext = Depends(
        require_permission("procurement_analytics.read")
    ),
    db: Session = Depends(get_db),
) -> AccountsPayableResponse:
    return _service(db).get_payables(
        organization_id=context.organization.id,
        as_of_date=as_of_date,
        supplier_id=supplier_id,
        currency=currency,
        overdue_only=False,
        limit=limit,
    )


@router.get(
    "/overdue-bills",
    response_model=AccountsPayableResponse,
    summary="List overdue supplier bills",
)
def get_overdue_bills(
    as_of_date: date | None = Query(default=None),
    supplier_id: uuid.UUID | None = Query(default=None),
    currency: str | None = Query(
        default=None,
        min_length=3,
        max_length=3,
    ),
    limit: int = Query(default=100, ge=1, le=500),
    context: OrganizationContext = Depends(
        require_permission("procurement_analytics.read")
    ),
    db: Session = Depends(get_db),
) -> AccountsPayableResponse:
    return _service(db).get_payables(
        organization_id=context.organization.id,
        as_of_date=as_of_date,
        supplier_id=supplier_id,
        currency=currency,
        overdue_only=True,
        limit=limit,
    )


@router.get(
    "/match-exceptions",
    response_model=MatchExceptionResponse,
    summary="List three-way-match exceptions",
)
def get_match_exceptions(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    supplier_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    context: OrganizationContext = Depends(
        require_permission("procurement_analytics.read")
    ),
    db: Session = Depends(get_db),
) -> MatchExceptionResponse:
    return _service(db).get_match_exceptions(
        organization_id=context.organization.id,
        date_from=date_from,
        date_to=date_to,
        supplier_id=supplier_id,
        limit=limit,
    )


@router.get(
    "/receipt-variances",
    response_model=ReceiptVarianceResponse,
    summary="List receipt rejection and damage variances",
)
def get_receipt_variances(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    supplier_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    context: OrganizationContext = Depends(
        require_permission("procurement_analytics.read")
    ),
    db: Session = Depends(get_db),
) -> ReceiptVarianceResponse:
    return _service(db).get_receipt_variances(
        organization_id=context.organization.id,
        date_from=date_from,
        date_to=date_to,
        supplier_id=supplier_id,
        limit=limit,
    )


@router.get(
    "/payment-history",
    response_model=PaymentHistoryResponse,
    summary="Get supplier payment history",
)
def get_payment_history(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    supplier_id: uuid.UUID | None = Query(default=None),
    currency: str | None = Query(
        default=None,
        min_length=3,
        max_length=3,
    ),
    include_reversed: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
    context: OrganizationContext = Depends(
        require_permission("procurement_analytics.read")
    ),
    db: Session = Depends(get_db),
) -> PaymentHistoryResponse:
    return _service(db).get_payment_history(
        organization_id=context.organization.id,
        date_from=date_from,
        date_to=date_to,
        supplier_id=supplier_id,
        currency=currency,
        include_reversed=include_reversed,
        limit=limit,
    )
