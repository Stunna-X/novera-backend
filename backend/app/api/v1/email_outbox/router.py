"""
Email outbox routes.
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
from app.schemas.email_outbox import (
    EmailOutboxListResponse,
    EmailOutboxMarkFailedRequest,
    EmailOutboxMarkSentRequest,
    EmailOutboxResponse,
    EmailOutboxRetryRequest,
    EmailOutboxStatus,
    EmailProvider,
)
from app.services.email_outbox_service import EmailOutboxService


router = APIRouter(
    prefix="/organizations/{organization_id}/email-outbox",
    tags=["Email Outbox"],
)


@router.get(
    "",
    response_model=EmailOutboxListResponse,
    summary="List email outbox messages",
)
def list_email_outbox(
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
    ),
    status_filter: EmailOutboxStatus | None = Query(
        default=None,
        alias="status",
    ),
    provider: EmailProvider | None = Query(
        default=None,
    ),
    recipient_email: str | None = Query(
        default=None,
        max_length=320,
    ),
    document_delivery_id: uuid.UUID | None = Query(
        default=None,
    ),
    context: OrganizationContext = Depends(
        require_permission("reports.read")
    ),
    db: Session = Depends(get_db),
) -> EmailOutboxListResponse:
    """
    List queued, sent, and failed email outbox records.
    """

    service = EmailOutboxService(db)

    return service.list_outbox(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        status_filter=status_filter,
        provider=provider,
        recipient_email=recipient_email,
        document_delivery_id=document_delivery_id,
    )


@router.get(
    "/{email_outbox_id}",
    response_model=EmailOutboxResponse,
    summary="Get email outbox message",
)
def get_email_outbox_message(
    email_outbox_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("reports.read")
    ),
    db: Session = Depends(get_db),
) -> EmailOutboxResponse:
    """
    Return one email outbox record.
    """

    service = EmailOutboxService(db)

    return service.get_outbox_email(
        organization_id=context.organization.id,
        email_outbox_id=email_outbox_id,
    )


@router.post(
    "/{email_outbox_id}/mark-sent",
    response_model=EmailOutboxResponse,
    summary="Mark email outbox message sent",
    responses={
        404: {
            "description": "Email outbox message not found.",
        },
        409: {
            "description": "Invalid email outbox state transition.",
        },
    },
)
def mark_email_outbox_sent(
    email_outbox_id: uuid.UUID,
    payload: EmailOutboxMarkSentRequest,
    context: OrganizationContext = Depends(
        require_permission("reports.read")
    ),
    db: Session = Depends(get_db),
) -> EmailOutboxResponse:
    """
    Mark a queued email as sent after provider confirmation.
    """

    service = EmailOutboxService(db)

    return service.mark_sent(
        organization_id=context.organization.id,
        email_outbox_id=email_outbox_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{email_outbox_id}/mark-failed",
    response_model=EmailOutboxResponse,
    summary="Mark email outbox message failed",
    responses={
        404: {
            "description": "Email outbox message not found.",
        },
        409: {
            "description": "Invalid email outbox state transition.",
        },
    },
)
def mark_email_outbox_failed(
    email_outbox_id: uuid.UUID,
    payload: EmailOutboxMarkFailedRequest,
    context: OrganizationContext = Depends(
        require_permission("reports.read")
    ),
    db: Session = Depends(get_db),
) -> EmailOutboxResponse:
    """
    Mark an email as failed and update its document delivery.
    """

    service = EmailOutboxService(db)

    return service.mark_failed(
        organization_id=context.organization.id,
        email_outbox_id=email_outbox_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{email_outbox_id}/retry",
    response_model=EmailOutboxResponse,
    summary="Retry failed email outbox message",
    responses={
        404: {
            "description": "Email outbox message not found.",
        },
        409: {
            "description": "Invalid email outbox state transition.",
        },
    },
)
def retry_email_outbox_message(
    email_outbox_id: uuid.UUID,
    payload: EmailOutboxRetryRequest,
    context: OrganizationContext = Depends(
        require_permission("reports.read")
    ),
    db: Session = Depends(get_db),
) -> EmailOutboxResponse:
    """
    Re-queue a failed email for another attempt.
    """

    service = EmailOutboxService(db)

    return service.retry_email(
        organization_id=context.organization.id,
        email_outbox_id=email_outbox_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
        actor_membership_id=context.membership.id,
    )
