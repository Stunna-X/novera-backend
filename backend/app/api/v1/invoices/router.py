"""
Invoice routes.

Provides organization-scoped endpoints for creating invoices from
work orders, managing draft line items, issuing invoices, recording
payments, reversing payments, voiding invoices, and billing reports.
"""

from __future__ import annotations

import uuid
from datetime import date

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
from app.enums.invoice import InvoiceStatus
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceExpenseLineCreate,
    InvoiceFromCloseoutCreate,
    InvoiceIssueRequest,
    InvoiceLineItemCreate,
    InvoiceLineItemUpdate,
    InvoiceListResponse,
    InvoicePaymentCreate,
    InvoicePaymentReverse,
    InvoiceResponse,
    InvoiceSummaryResponse,
    InvoiceUpdate,
    InvoiceVoidRequest,
)
from app.services.invoice_service import InvoiceService


router = APIRouter(
    prefix="/organizations/{organization_id}",
    tags=["Invoices"],
)


@router.post(
    "/work-orders/{work_order_id}/invoices",
    response_model=InvoiceResponse,
    status_code=201,
    summary="Create work-order invoice",
)
def create_work_order_invoice(
    work_order_id: uuid.UUID,
    payload: InvoiceCreate,
    context: OrganizationContext = Depends(
        require_permission("finance.invoices.create")
    ),
    db: Session = Depends(get_db),
) -> InvoiceResponse:
    """
    Create a draft invoice from approved billable expenses,
    manual line items, or both.
    """

    service = InvoiceService(db)

    return service.create_invoice(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/work-orders/{work_order_id}/invoices/from-closeout",
    response_model=InvoiceResponse,
    status_code=201,
    summary="Create final invoice from approved closeout",
)
def create_work_order_invoice_from_closeout(
    work_order_id: uuid.UUID,
    payload: InvoiceFromCloseoutCreate,
    context: OrganizationContext = Depends(
        require_permission("finance.invoices.create")
    ),
    db: Session = Depends(get_db),
) -> InvoiceResponse:
    service = InvoiceService(db)

    return service.create_invoice_from_closeout(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )



@router.get(
    "/invoices",
    response_model=InvoiceListResponse,
    summary="List invoices",
)
def list_invoices(
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
        max_length=200,
    ),
    invoice_status: InvoiceStatus | None = Query(
        default=None,
        alias="status",
    ),
    currency: str | None = Query(
        default=None,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
    ),
    customer_id: uuid.UUID | None = Query(
        default=None,
    ),
    work_order_id: uuid.UUID | None = Query(
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
        require_permission("finance.invoices.read")
    ),
    db: Session = Depends(get_db),
) -> InvoiceListResponse:
    """
    List organization invoices with optional search, status,
    currency, customer, work-order, and date filters.
    """

    service = InvoiceService(db)

    return service.list_invoices(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        search=search,
        invoice_status=invoice_status,
        currency=currency,
        customer_id=customer_id,
        work_order_id=work_order_id,
        date_from=date_from,
        date_to=date_to,
        include_inactive=include_inactive,
    )


@router.get(
    "/invoices/summary",
    response_model=InvoiceSummaryResponse,
    summary="Get invoice summary",
)
def get_invoice_summary(
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
        require_permission("finance.invoices.read")
    ),
    db: Session = Depends(get_db),
) -> InvoiceSummaryResponse:
    """
    Return organization invoice totals grouped separately by
    currency.
    """

    service = InvoiceService(db)

    return service.get_summary(
        organization_id=context.organization.id,
        date_from=date_from,
        date_to=date_to,
        include_inactive=include_inactive,
    )


@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get invoice",
)
def get_invoice(
    invoice_id: uuid.UUID,
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("finance.invoices.read")
    ),
    db: Session = Depends(get_db),
) -> InvoiceResponse:
    """
    Return one organization-scoped invoice with line items
    and payment history.
    """

    service = InvoiceService(db)

    return service.get_invoice(
        organization_id=context.organization.id,
        invoice_id=invoice_id,
        include_inactive=include_inactive,
    )


@router.patch(
    "/invoices/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Update draft invoice",
)
def update_invoice(
    invoice_id: uuid.UUID,
    payload: InvoiceUpdate,
    context: OrganizationContext = Depends(
        require_permission("finance.invoices.update")
    ),
    db: Session = Depends(get_db),
) -> InvoiceResponse:
    """
    Update editable draft-invoice fields and recalculate totals.
    """

    service = InvoiceService(db)

    return service.update_invoice(
        organization_id=context.organization.id,
        invoice_id=invoice_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/invoices/{invoice_id}/line-items/manual",
    response_model=InvoiceResponse,
    status_code=201,
    summary="Add manual invoice line",
)
def add_manual_invoice_line(
    invoice_id: uuid.UUID,
    payload: InvoiceLineItemCreate,
    context: OrganizationContext = Depends(
        require_permission("finance.invoices.update")
    ),
    db: Session = Depends(get_db),
) -> InvoiceResponse:
    """
    Add a manually priced line item to a draft invoice.
    """

    service = InvoiceService(db)

    return service.add_manual_line_item(
        organization_id=context.organization.id,
        invoice_id=invoice_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/invoices/{invoice_id}/line-items/expense",
    response_model=InvoiceResponse,
    status_code=201,
    summary="Add expense invoice line",
)
def add_expense_invoice_line(
    invoice_id: uuid.UUID,
    payload: InvoiceExpenseLineCreate,
    context: OrganizationContext = Depends(
        require_permission("finance.invoices.update")
    ),
    db: Session = Depends(get_db),
) -> InvoiceResponse:
    """
    Add one active approved billable expense to a draft invoice.
    """

    service = InvoiceService(db)

    return service.add_expense_line_item(
        organization_id=context.organization.id,
        invoice_id=invoice_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.patch(
    "/invoices/{invoice_id}/line-items/{line_item_id}",
    response_model=InvoiceResponse,
    summary="Update manual invoice line",
)
def update_invoice_line(
    invoice_id: uuid.UUID,
    line_item_id: uuid.UUID,
    payload: InvoiceLineItemUpdate,
    context: OrganizationContext = Depends(
        require_permission("finance.invoices.update")
    ),
    db: Session = Depends(get_db),
) -> InvoiceResponse:
    """
    Update a manual line item while the invoice remains draft.
    Expense-generated lines cannot be edited manually.
    """

    service = InvoiceService(db)

    return service.update_line_item(
        organization_id=context.organization.id,
        invoice_id=invoice_id,
        line_item_id=line_item_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.delete(
    "/invoices/{invoice_id}/line-items/{line_item_id}",
    response_model=InvoiceResponse,
    summary="Remove invoice line",
)
def remove_invoice_line(
    invoice_id: uuid.UUID,
    line_item_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("finance.invoices.update")
    ),
    db: Session = Depends(get_db),
) -> InvoiceResponse:
    """
    Soft-remove a line item from a draft invoice and return
    the recalculated invoice.
    """

    service = InvoiceService(db)

    return service.remove_line_item(
        organization_id=context.organization.id,
        invoice_id=invoice_id,
        line_item_id=line_item_id,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/invoices/{invoice_id}/issue",
    response_model=InvoiceResponse,
    summary="Issue invoice",
)
def issue_invoice(
    invoice_id: uuid.UUID,
    payload: InvoiceIssueRequest,
    context: OrganizationContext = Depends(
        require_permission("finance.invoices.issue")
    ),
    db: Session = Depends(get_db),
) -> InvoiceResponse:
    """
    Lock and issue a completed draft invoice.
    """

    service = InvoiceService(db)

    return service.issue_invoice(
        organization_id=context.organization.id,
        invoice_id=invoice_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/invoices/{invoice_id}/payments",
    response_model=InvoiceResponse,
    status_code=201,
    summary="Record invoice payment",
)
def record_invoice_payment(
    invoice_id: uuid.UUID,
    payload: InvoicePaymentCreate,
    context: OrganizationContext = Depends(
        require_permission("finance.payments.record")
    ),
    db: Session = Depends(get_db),
) -> InvoiceResponse:
    """
    Record a partial or full payment against an issued invoice.
    """

    service = InvoiceService(db)

    return service.record_payment(
        organization_id=context.organization.id,
        invoice_id=invoice_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/invoices/{invoice_id}/payments/{payment_id}/reverse",
    response_model=InvoiceResponse,
    summary="Reverse invoice payment",
)
def reverse_invoice_payment(
    invoice_id: uuid.UUID,
    payment_id: uuid.UUID,
    payload: InvoicePaymentReverse,
    context: OrganizationContext = Depends(
        require_permission("finance.payments.reverse")
    ),
    db: Session = Depends(get_db),
) -> InvoiceResponse:
    """
    Reverse an incorrect payment while retaining the audit trail.
    """

    service = InvoiceService(db)

    return service.reverse_payment(
        organization_id=context.organization.id,
        invoice_id=invoice_id,
        payment_id=payment_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/invoices/{invoice_id}/void",
    response_model=InvoiceResponse,
    summary="Void invoice",
)
def void_invoice(
    invoice_id: uuid.UUID,
    payload: InvoiceVoidRequest,
    context: OrganizationContext = Depends(
        require_permission("finance.invoices.void")
    ),
    db: Session = Depends(get_db),
) -> InvoiceResponse:
    """
    Void an issued invoice after all active payments have been
    reversed.
    """

    service = InvoiceService(db)

    return service.void_invoice(
        organization_id=context.organization.id,
        invoice_id=invoice_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )