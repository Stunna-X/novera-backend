"""Organization-scoped supplier-payment and AP settlement routes."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import OrganizationContext, require_permission
from app.database.session import get_db
from app.schemas.supplier_payment import (
    SupplierPayableListResponse,
    SupplierPaymentCreate,
    SupplierPaymentListResponse,
    SupplierPaymentResponse,
    SupplierPaymentReverse,
    SupplierPaymentStatus,
)
from app.services.supplier_payment_service import SupplierPaymentService


router = APIRouter(
    prefix="/organizations/{organization_id}/supplier-payments",
    tags=["Supplier Payments"],
)


@router.post(
    "",
    response_model=SupplierPaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Post supplier payment",
)
def create_supplier_payment(
    payload: SupplierPaymentCreate,
    context: OrganizationContext = Depends(
        require_permission("supplier_payments.create")
    ),
    db: Session = Depends(get_db),
) -> SupplierPaymentResponse:
    return SupplierPaymentService(db).record_payment(
        organization_id=context.organization.id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.get(
    "",
    response_model=SupplierPaymentListResponse,
    summary="List supplier payments",
)
def list_supplier_payments(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    supplier_id: uuid.UUID | None = Query(default=None),
    payment_status: SupplierPaymentStatus | None = Query(
        default=None,
        alias="status",
    ),
    payment_from: date | None = Query(default=None),
    payment_to: date | None = Query(default=None),
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
    ),
    context: OrganizationContext = Depends(
        require_permission("supplier_payments.read")
    ),
    db: Session = Depends(get_db),
) -> SupplierPaymentListResponse:
    return SupplierPaymentService(db).list_payments(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        supplier_id=supplier_id,
        status_filter=payment_status,
        payment_from=payment_from,
        payment_to=payment_to,
        search=search,
    )


@router.get(
    "/payables",
    response_model=SupplierPayableListResponse,
    summary="List approved supplier-bill balances",
)
def list_supplier_payables(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    supplier_id: uuid.UUID | None = Query(default=None),
    context: OrganizationContext = Depends(
        require_permission("supplier_payments.read")
    ),
    db: Session = Depends(get_db),
) -> SupplierPayableListResponse:
    return SupplierPaymentService(db).list_payables(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        supplier_id=supplier_id,
    )


@router.get(
    "/{supplier_payment_id}",
    response_model=SupplierPaymentResponse,
    summary="Get supplier payment",
)
def get_supplier_payment(
    supplier_payment_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("supplier_payments.read")
    ),
    db: Session = Depends(get_db),
) -> SupplierPaymentResponse:
    return SupplierPaymentService(db).get_payment(
        organization_id=context.organization.id,
        supplier_payment_id=supplier_payment_id,
    )


@router.post(
    "/{supplier_payment_id}/reverse",
    response_model=SupplierPaymentResponse,
    summary="Reverse supplier payment",
)
def reverse_supplier_payment(
    supplier_payment_id: uuid.UUID,
    payload: SupplierPaymentReverse,
    context: OrganizationContext = Depends(
        require_permission("supplier_payments.reverse")
    ),
    db: Session = Depends(get_db),
) -> SupplierPaymentResponse:
    return SupplierPaymentService(db).reverse_payment(
        organization_id=context.organization.id,
        supplier_payment_id=supplier_payment_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )
