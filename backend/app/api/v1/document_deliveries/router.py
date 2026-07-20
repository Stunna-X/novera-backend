"""
Document delivery routes.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    OrganizationContext,
    require_permission,
)
from app.database.session import get_db
from app.schemas.document_delivery import (
    DeliveryStatus,
    DocumentDeliveryListResponse,
    DocumentDeliveryResponse,
    DocumentDeliverySendRequest,
    DocumentType,
)
from app.services.document_delivery_service import (
    DocumentDeliveryService,
)


router = APIRouter(
    prefix="/organizations/{organization_id}",
    tags=["Document Deliveries"],
)


@router.post(
    "/invoices/{invoice_id}/send",
    response_model=DocumentDeliveryResponse,
    status_code=201,
    summary="Queue invoice email delivery",
)
def send_invoice_document(
    invoice_id: uuid.UUID,
    payload: DocumentDeliverySendRequest,
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("document_deliveries.send")
    ),
    db: Session = Depends(get_db),
) -> DocumentDeliveryResponse:
    """
    Queue an invoice email and create its delivery record.
    """

    service = DocumentDeliveryService(db)

    return service.send_invoice(
        organization_id=context.organization.id,
        invoice_id=invoice_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
        actor_membership_id=context.membership.id,
        include_inactive=include_inactive,
    )


@router.post(
    "/quotes/{quote_id}/send-delivery",
    response_model=DocumentDeliveryResponse,
    status_code=201,
    summary="Queue quote email delivery",
)
def send_quote_document(
    quote_id: uuid.UUID,
    payload: DocumentDeliverySendRequest,
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("document_deliveries.send")
    ),
    db: Session = Depends(get_db),
) -> DocumentDeliveryResponse:
    """
    Queue a quote email and create its delivery record.

    This is separate from the quote-lifecycle send operation.
    """

    service = DocumentDeliveryService(db)

    return service.send_quote(
        organization_id=context.organization.id,
        quote_id=quote_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
        actor_membership_id=context.membership.id,
        include_inactive=include_inactive,
    )


@router.get(
    "/document-deliveries",
    response_model=DocumentDeliveryListResponse,
    summary="List document deliveries",
)
def list_document_deliveries(
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
    ),
    document_type: DocumentType | None = Query(
        default=None,
    ),
    document_id: uuid.UUID | None = Query(
        default=None,
    ),
    delivery_status: DeliveryStatus | None = Query(
        default=None,
        alias="status",
    ),
    recipient_email: str | None = Query(
        default=None,
        max_length=320,
    ),
    context: OrganizationContext = Depends(
        require_permission("document_deliveries.read")
    ),
    db: Session = Depends(get_db),
) -> DocumentDeliveryListResponse:
    """
    List tracked document-delivery records.
    """

    service = DocumentDeliveryService(db)

    return service.list_deliveries(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        document_type=document_type,
        document_id=document_id,
        delivery_status=delivery_status,
        recipient_email=recipient_email,
    )


@router.get(
    "/document-deliveries/{delivery_id}",
    response_model=DocumentDeliveryResponse,
    summary="Get document delivery",
)
def get_document_delivery(
    delivery_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("document_deliveries.read")
    ),
    db: Session = Depends(get_db),
) -> DocumentDeliveryResponse:
    """
    Return one document-delivery record.
    """

    service = DocumentDeliveryService(db)

    return service.get_delivery(
        organization_id=context.organization.id,
        delivery_id=delivery_id,
    )