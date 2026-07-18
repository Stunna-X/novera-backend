"""
Quote routes.

Provides organization-scoped endpoints for quotes, line items,
lifecycle actions, reporting, activity history, and conversion
into draft work orders.
"""

from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    Depends,
    Query,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    OrganizationContext,
    require_all_permissions,
    require_permission,
)
from app.database.session import get_db
from app.schemas.quote import (
    QuoteActivityListResponse,
    QuoteActivityType,
    QuoteConversionResponse,
    QuoteConvertRequest,
    QuoteCreate,
    QuoteLifecycleNote,
    QuoteLineItemCreate,
    QuoteLineItemUpdate,
    QuoteListResponse,
    QuoteRejectRequest,
    QuoteResponse,
    QuoteStatusType,
    QuoteSummaryResponse,
    QuoteUpdate,
)
from app.services.document_pdf_service import DocumentPDFService
from app.services.quote_service import QuoteService


router = APIRouter(
    prefix="/organizations/{organization_id}/quotes",
    tags=["Quotes"],
)


@router.post(
    "",
    response_model=QuoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create quote",
)
def create_quote(
    payload: QuoteCreate,
    context: OrganizationContext = Depends(
        require_permission("quotes.create")
    ),
    db: Session = Depends(get_db),
) -> QuoteResponse:
    """
    Create an organization-scoped draft quote.
    """

    service = QuoteService(db)

    return service.create_quote(
        organization_id=context.organization.id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.get(
    "",
    response_model=QuoteListResponse,
    summary="List quotes",
)
def list_quotes(
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
    quote_status: QuoteStatusType | None = Query(
        default=None,
        alias="status",
    ),
    customer_id: uuid.UUID | None = Query(
        default=None,
    ),
    customer_site_id: uuid.UUID | None = Query(
        default=None,
    ),
    currency: str | None = Query(
        default=None,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
    ),
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("quotes.read")
    ),
    db: Session = Depends(get_db),
) -> QuoteListResponse:
    """
    List quotes with optional search and filters.
    """

    service = QuoteService(db)

    return service.list_quotes(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        search=search,
        status_filter=quote_status,
        customer_id=customer_id,
        customer_site_id=customer_site_id,
        currency=currency,
        include_inactive=include_inactive,
    )


@router.get(
    "/summary",
    response_model=QuoteSummaryResponse,
    summary="Get quote summary",
)
def get_quote_summary(
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("quotes.read")
    ),
    db: Session = Depends(get_db),
) -> QuoteSummaryResponse:
    """
    Return quote totals separated by currency.
    """

    service = QuoteService(db)

    return service.get_summary(
        organization_id=context.organization.id,
        include_inactive=include_inactive,
    )


@router.get(
    "/{quote_id}/pdf",
    summary="Download quote PDF",
)
def download_quote_pdf(
    quote_id: uuid.UUID,
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("quotes.read")
    ),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    Download one organization quote or estimate as a PDF.
    """

    service = DocumentPDFService(db)

    pdf_bytes, filename = service.build_quote_pdf(
        organization_id=context.organization.id,
        quote_id=quote_id,
        include_inactive=include_inactive,
    )

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            ),
        },
    )


@router.get(
    "/{quote_id}",
    response_model=QuoteResponse,
    summary="Get quote",
)
def get_quote(
    quote_id: uuid.UUID,
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("quotes.read")
    ),
    db: Session = Depends(get_db),
) -> QuoteResponse:
    """
    Return one organization quote.
    """

    service = QuoteService(db)

    return service.get_quote(
        organization_id=context.organization.id,
        quote_id=quote_id,
        include_inactive=include_inactive,
    )


@router.get(
    "/{quote_id}/activities",
    response_model=QuoteActivityListResponse,
    summary="List quote activities",
)
def list_quote_activities(
    quote_id: uuid.UUID,
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
    ),
    activity_type: QuoteActivityType | None = Query(
        default=None,
    ),
    include_inactive_quote: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("quotes.read")
    ),
    db: Session = Depends(get_db),
) -> QuoteActivityListResponse:
    """
    Return the immutable quote timeline.
    """

    service = QuoteService(db)

    return service.list_activities(
        organization_id=context.organization.id,
        quote_id=quote_id,
        skip=skip,
        limit=limit,
        activity_type=activity_type,
        include_inactive_quote=(
            include_inactive_quote
        ),
    )


@router.patch(
    "/{quote_id}",
    response_model=QuoteResponse,
    summary="Update quote",
)
def update_quote(
    quote_id: uuid.UUID,
    payload: QuoteUpdate,
    context: OrganizationContext = Depends(
        require_permission("quotes.update")
    ),
    db: Session = Depends(get_db),
) -> QuoteResponse:
    """
    Update editable details on a draft quote.
    """

    service = QuoteService(db)

    return service.update_quote(
        organization_id=context.organization.id,
        quote_id=quote_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/{quote_id}/line-items",
    response_model=QuoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add quote line item",
)
def add_quote_line_item(
    quote_id: uuid.UUID,
    payload: QuoteLineItemCreate,
    context: OrganizationContext = Depends(
        require_permission("quotes.update")
    ),
    db: Session = Depends(get_db),
) -> QuoteResponse:
    """
    Add one priced line to a draft quote.
    """

    service = QuoteService(db)

    return service.add_line_item(
        organization_id=context.organization.id,
        quote_id=quote_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.patch(
    "/{quote_id}/line-items/{line_item_id}",
    response_model=QuoteResponse,
    summary="Update quote line item",
)
def update_quote_line_item(
    quote_id: uuid.UUID,
    line_item_id: uuid.UUID,
    payload: QuoteLineItemUpdate,
    context: OrganizationContext = Depends(
        require_permission("quotes.update")
    ),
    db: Session = Depends(get_db),
) -> QuoteResponse:
    """
    Update one active line on a draft quote.
    """

    service = QuoteService(db)

    return service.update_line_item(
        organization_id=context.organization.id,
        quote_id=quote_id,
        line_item_id=line_item_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.delete(
    "/{quote_id}/line-items/{line_item_id}",
    response_model=QuoteResponse,
    summary="Remove quote line item",
)
def remove_quote_line_item(
    quote_id: uuid.UUID,
    line_item_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("quotes.update")
    ),
    db: Session = Depends(get_db),
) -> QuoteResponse:
    """
    Soft-remove one active line from a draft quote.
    """

    service = QuoteService(db)

    return service.remove_line_item(
        organization_id=context.organization.id,
        quote_id=quote_id,
        line_item_id=line_item_id,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/{quote_id}/send",
    response_model=QuoteResponse,
    summary="Send quote",
)
def send_quote(
    quote_id: uuid.UUID,
    payload: QuoteLifecycleNote,
    context: OrganizationContext = Depends(
        require_permission("quotes.update")
    ),
    db: Session = Depends(get_db),
) -> QuoteResponse:
    """
    Issue a priced draft quote to the customer.
    """

    service = QuoteService(db)

    return service.send_quote(
        organization_id=context.organization.id,
        quote_id=quote_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/{quote_id}/accept",
    response_model=QuoteResponse,
    summary="Accept quote",
)
def accept_quote(
    quote_id: uuid.UUID,
    payload: QuoteLifecycleNote,
    context: OrganizationContext = Depends(
        require_permission("quotes.respond")
    ),
    db: Session = Depends(get_db),
) -> QuoteResponse:
    """
    Record customer acceptance of a sent quote.
    """

    service = QuoteService(db)

    return service.accept_quote(
        organization_id=context.organization.id,
        quote_id=quote_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/{quote_id}/reject",
    response_model=QuoteResponse,
    summary="Reject quote",
)
def reject_quote(
    quote_id: uuid.UUID,
    payload: QuoteRejectRequest,
    context: OrganizationContext = Depends(
        require_permission("quotes.respond")
    ),
    db: Session = Depends(get_db),
) -> QuoteResponse:
    """
    Record customer rejection of a sent quote.
    """

    service = QuoteService(db)

    return service.reject_quote(
        organization_id=context.organization.id,
        quote_id=quote_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/{quote_id}/expire",
    response_model=QuoteResponse,
    summary="Expire quote",
)
def expire_quote(
    quote_id: uuid.UUID,
    payload: QuoteLifecycleNote,
    context: OrganizationContext = Depends(
        require_permission("quotes.respond")
    ),
    db: Session = Depends(get_db),
) -> QuoteResponse:
    """
    Mark a sent quote expired after its validity date.
    """

    service = QuoteService(db)

    return service.expire_quote(
        organization_id=context.organization.id,
        quote_id=quote_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/{quote_id}/convert",
    response_model=QuoteConversionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Convert quote to work order",
)
def convert_quote_to_work_order(
    quote_id: uuid.UUID,
    payload: QuoteConvertRequest,
    context: OrganizationContext = Depends(
        require_all_permissions(
            "quotes.convert",
            "work_orders.create",
        )
    ),
    db: Session = Depends(get_db),
) -> QuoteConversionResponse:
    """
    Convert an accepted quote into one draft work order.
    """

    service = QuoteService(db)

    return service.convert_quote(
        organization_id=context.organization.id,
        quote_id=quote_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )