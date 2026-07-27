"""Organization-scoped supplier bill and three-way match routes."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import OrganizationContext, require_permission
from app.database.session import get_db
from app.schemas.supplier_bill import (
    ApproveSupplierBillSchema,
    CreateSupplierBillSchema,
    MatchSupplierBillSchema,
    SubmitSupplierBillSchema,
    SupplierBillLineCreate,
    SupplierBillLineUpdate,
    SupplierBillListResponse,
    SupplierBillMatchStatus,
    SupplierBillMatchSummaryResponse,
    SupplierBillResponse,
    SupplierBillStatus,
    UpdateSupplierBillSchema,
    VoidSupplierBillSchema,
)
from app.services.supplier_bill_service import SupplierBillService


router = APIRouter(
    prefix="/organizations/{organization_id}/supplier-bills",
    tags=["Supplier Bills"],
)


@router.post(
    "",
    response_model=SupplierBillResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create supplier bill",
)
def create_supplier_bill(
    payload: CreateSupplierBillSchema,
    context: OrganizationContext = Depends(
        require_permission("supplier_bills.create")
    ),
    db: Session = Depends(get_db),
) -> SupplierBillResponse:
    return SupplierBillService(db).create_supplier_bill(
        organization_id=context.organization.id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.get(
    "",
    response_model=SupplierBillListResponse,
    summary="List supplier bills",
)
def list_supplier_bills(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    search: str | None = Query(default=None, min_length=1, max_length=200),
    supplier_bill_status: SupplierBillStatus | None = Query(
        default=None,
        alias="status",
    ),
    match_status: SupplierBillMatchStatus | None = Query(default=None),
    supplier_id: uuid.UUID | None = Query(default=None),
    purchase_order_id: uuid.UUID | None = Query(default=None),
    invoice_from: date | None = Query(default=None),
    invoice_to: date | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    context: OrganizationContext = Depends(
        require_permission("supplier_bills.read")
    ),
    db: Session = Depends(get_db),
) -> SupplierBillListResponse:
    return SupplierBillService(db).list_supplier_bills(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        search=search,
        status_filter=supplier_bill_status,
        match_status_filter=match_status,
        supplier_id=supplier_id,
        purchase_order_id=purchase_order_id,
        invoice_from=invoice_from,
        invoice_to=invoice_to,
        include_inactive=include_inactive,
    )


@router.get(
    "/{supplier_bill_id}",
    response_model=SupplierBillResponse,
    summary="Get supplier bill",
)
def get_supplier_bill(
    supplier_bill_id: uuid.UUID,
    include_inactive: bool = Query(default=False),
    context: OrganizationContext = Depends(
        require_permission("supplier_bills.read")
    ),
    db: Session = Depends(get_db),
) -> SupplierBillResponse:
    return SupplierBillService(db).get_supplier_bill(
        organization_id=context.organization.id,
        supplier_bill_id=supplier_bill_id,
        include_inactive=include_inactive,
    )


@router.patch(
    "/{supplier_bill_id}",
    response_model=SupplierBillResponse,
    summary="Update supplier bill",
)
def update_supplier_bill(
    supplier_bill_id: uuid.UUID,
    payload: UpdateSupplierBillSchema,
    context: OrganizationContext = Depends(
        require_permission("supplier_bills.update")
    ),
    db: Session = Depends(get_db),
) -> SupplierBillResponse:
    return SupplierBillService(db).update_supplier_bill(
        organization_id=context.organization.id,
        supplier_bill_id=supplier_bill_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{supplier_bill_id}/line-items",
    response_model=SupplierBillResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add supplier bill line",
)
def add_supplier_bill_line(
    supplier_bill_id: uuid.UUID,
    payload: SupplierBillLineCreate,
    context: OrganizationContext = Depends(
        require_permission("supplier_bills.update")
    ),
    db: Session = Depends(get_db),
) -> SupplierBillResponse:
    return SupplierBillService(db).add_line_item(
        organization_id=context.organization.id,
        supplier_bill_id=supplier_bill_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.patch(
    "/{supplier_bill_id}/line-items/{line_item_id}",
    response_model=SupplierBillResponse,
    summary="Update supplier bill line",
)
def update_supplier_bill_line(
    supplier_bill_id: uuid.UUID,
    line_item_id: uuid.UUID,
    payload: SupplierBillLineUpdate,
    context: OrganizationContext = Depends(
        require_permission("supplier_bills.update")
    ),
    db: Session = Depends(get_db),
) -> SupplierBillResponse:
    return SupplierBillService(db).update_line_item(
        organization_id=context.organization.id,
        supplier_bill_id=supplier_bill_id,
        line_item_id=line_item_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.delete(
    "/{supplier_bill_id}/line-items/{line_item_id}",
    response_model=SupplierBillResponse,
    summary="Remove supplier bill line",
)
def delete_supplier_bill_line(
    supplier_bill_id: uuid.UUID,
    line_item_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("supplier_bills.update")
    ),
    db: Session = Depends(get_db),
) -> SupplierBillResponse:
    return SupplierBillService(db).delete_line_item(
        organization_id=context.organization.id,
        supplier_bill_id=supplier_bill_id,
        line_item_id=line_item_id,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{supplier_bill_id}/submit",
    response_model=SupplierBillResponse,
    summary="Submit supplier bill",
)
def submit_supplier_bill(
    supplier_bill_id: uuid.UUID,
    payload: SubmitSupplierBillSchema,
    context: OrganizationContext = Depends(
        require_permission("supplier_bills.submit")
    ),
    db: Session = Depends(get_db),
) -> SupplierBillResponse:
    return SupplierBillService(db).submit_supplier_bill(
        organization_id=context.organization.id,
        supplier_bill_id=supplier_bill_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{supplier_bill_id}/match",
    response_model=SupplierBillResponse,
    summary="Run supplier bill three-way match",
)
def match_supplier_bill(
    supplier_bill_id: uuid.UUID,
    payload: MatchSupplierBillSchema,
    context: OrganizationContext = Depends(
        require_permission("supplier_bills.match")
    ),
    db: Session = Depends(get_db),
) -> SupplierBillResponse:
    return SupplierBillService(db).run_three_way_match(
        organization_id=context.organization.id,
        supplier_bill_id=supplier_bill_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.get(
    "/{supplier_bill_id}/match-summary",
    response_model=SupplierBillMatchSummaryResponse,
    summary="Get supplier bill match summary",
)
def get_supplier_bill_match_summary(
    supplier_bill_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("supplier_bills.read")
    ),
    db: Session = Depends(get_db),
) -> SupplierBillMatchSummaryResponse:
    return SupplierBillService(db).get_match_summary(
        organization_id=context.organization.id,
        supplier_bill_id=supplier_bill_id,
    )


@router.post(
    "/{supplier_bill_id}/approve",
    response_model=SupplierBillResponse,
    summary="Approve supplier bill",
)
def approve_supplier_bill(
    supplier_bill_id: uuid.UUID,
    payload: ApproveSupplierBillSchema,
    context: OrganizationContext = Depends(
        require_permission("supplier_bills.approve")
    ),
    db: Session = Depends(get_db),
) -> SupplierBillResponse:
    return SupplierBillService(db).approve_supplier_bill(
        organization_id=context.organization.id,
        supplier_bill_id=supplier_bill_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{supplier_bill_id}/void",
    response_model=SupplierBillResponse,
    summary="Void supplier bill",
)
def void_supplier_bill(
    supplier_bill_id: uuid.UUID,
    payload: VoidSupplierBillSchema,
    context: OrganizationContext = Depends(
        require_permission("supplier_bills.void")
    ),
    db: Session = Depends(get_db),
) -> SupplierBillResponse:
    return SupplierBillService(db).void_supplier_bill(
        organization_id=context.organization.id,
        supplier_bill_id=supplier_bill_id,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )
