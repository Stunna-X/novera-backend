"""
Email outbox service.

Queues and manages outbound emails. This service does not send
network email itself; workers/providers will consume queued rows.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document_delivery import DocumentDelivery
from app.models.email_outbox import EmailOutbox
from app.repositories.email_outbox import EmailOutboxRepository
from app.schemas.audit_log import AuditLogCreate
from app.schemas.email_outbox import (
    EmailOutboxListResponse,
    EmailOutboxMarkFailedRequest,
    EmailOutboxMarkSentRequest,
    EmailOutboxResponse,
    EmailOutboxRetryRequest,
)
from app.services.audit_log_service import AuditLogService


class EmailOutboxService:
    """
    Business logic for email outbox records.
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db
        self.emails = EmailOutboxRepository(db)
        self.audit_logs = AuditLogService(db)

    def enqueue_for_delivery(
        self,
        *,
        delivery: DocumentDelivery,
        body_text: str,
        attachment_filename: str | None,
        actor_user_id: uuid.UUID | None,
    ) -> EmailOutbox:
        """
        Create one queued email for a document delivery record.
        """

        email = EmailOutbox(
            organization_id=delivery.organization_id,
            document_delivery_id=delivery.id,
            queued_by_user_id=actor_user_id,
            provider=settings.EMAIL_PROVIDER,
            status="queued",
            from_email=settings.EMAIL_FROM_EMAIL,
            from_name=settings.EMAIL_FROM_NAME,
            reply_to_email=settings.EMAIL_REPLY_TO_EMAIL,
            to_email=delivery.recipient_email,
            to_name=delivery.recipient_name,
            subject=delivery.subject,
            body_text=body_text,
            body_html=None,
            attachment_filename=attachment_filename,
            attempts=0,
            max_attempts=settings.EMAIL_OUTBOX_MAX_ATTEMPTS,
            next_attempt_at=datetime.now(UTC),
            queued_at=datetime.now(UTC),
            details={
                "document_type": delivery.document_type,
                "document_id": str(delivery.document_id),
                "document_number": delivery.document_number,
                "provider_mode": (
                    "queued_only_no_network_send"
                ),
            },
        )

        return self.emails.create(email)

    def list_outbox(
        self,
        *,
        organization_id: uuid.UUID,
        skip: int,
        limit: int,
        status_filter: str | None = None,
        provider: str | None = None,
        recipient_email: str | None = None,
        document_delivery_id: uuid.UUID | None = None,
    ) -> EmailOutboxListResponse:
        """
        List queued/sent/failed emails for an organization.
        """

        total = self.emails.count_for_organization(
            organization_id=organization_id,
            status_filter=status_filter,
            provider=provider,
            recipient_email=recipient_email,
            document_delivery_id=document_delivery_id,
        )

        items = self.emails.list_for_organization(
            organization_id=organization_id,
            skip=skip,
            limit=limit,
            status_filter=status_filter,
            provider=provider,
            recipient_email=recipient_email,
            document_delivery_id=document_delivery_id,
        )

        return EmailOutboxListResponse(
            items=[
                self._build_response(item)
                for item in items
            ],
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_outbox_email(
        self,
        *,
        organization_id: uuid.UUID,
        email_outbox_id: uuid.UUID,
    ) -> EmailOutboxResponse:
        """
        Return one outbox email.
        """

        email = self._get_email_or_404(
            organization_id=organization_id,
            email_outbox_id=email_outbox_id,
        )

        return self._build_response(email)

    def mark_sent(
        self,
        *,
        organization_id: uuid.UUID,
        email_outbox_id: uuid.UUID,
        payload: EmailOutboxMarkSentRequest,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> EmailOutboxResponse:
        """
        Mark an outbox email as sent after provider confirmation.
        """

        email = self._get_email_or_404(
            organization_id=organization_id,
            email_outbox_id=email_outbox_id,
        )

        if email.status not in {
            "queued",
            "sending",
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only queued or sending emails can be marked "
                    "as sent."
                ),
            )

        now = datetime.now(UTC)

        email.status = "sent"
        email.sent_at = now
        email.failed_at = None
        email.next_attempt_at = None
        email.last_error = None
        email.provider_message_id = payload.provider_message_id

        delivery = email.document_delivery
        delivery.delivery_status = "sent"
        delivery.sent_at = now
        delivery.provider = email.provider
        delivery_details = {
            **(delivery.details or {}),
        }

        for stale_key in (
            "last_error",
            "retryable",
            "retry_note",
            "failed_at",
        ):
            delivery_details.pop(stale_key, None)

        delivery.details = {
            **delivery_details,
            "email_outbox_id": str(email.id),
            "email_outbox_status": email.status,
            "provider_message_id": payload.provider_message_id,
            "sent_note": payload.note,
        }

        self._record_audit_event(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            action="email_outbox.sent",
            entity_id=email.id,
            summary=(
                f"Email outbox message sent to {email.to_email}."
            ),
            details={
                "email_outbox_id": str(email.id),
                "document_delivery_id": str(
                    email.document_delivery_id
                ),
                "provider": email.provider,
                "provider_message_id": payload.provider_message_id,
            },
        )

        self.db.commit()
        self.db.refresh(email)

        return self._build_response(email)

    def mark_failed(
        self,
        *,
        organization_id: uuid.UUID,
        email_outbox_id: uuid.UUID,
        payload: EmailOutboxMarkFailedRequest,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> EmailOutboxResponse:
        """
        Mark an outbox email as failed.
        """

        email = self._get_email_or_404(
            organization_id=organization_id,
            email_outbox_id=email_outbox_id,
        )

        if email.status not in {
            "queued",
            "sending",
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only queued or sending emails can be marked "
                    "as failed."
                ),
            )

        now = datetime.now(UTC)

        email.status = "failed"
        email.failed_at = now
        email.last_error = payload.reason
        email.attempts += 1

        if (
            payload.retryable
            and email.attempts < email.max_attempts
        ):
            email.next_attempt_at = now
        else:
            email.next_attempt_at = None

        delivery = email.document_delivery
        delivery.delivery_status = "failed"
        delivery.details = {
            **(delivery.details or {}),
            "email_outbox_id": str(email.id),
            "email_outbox_status": email.status,
            "last_error": payload.reason,
            "retryable": payload.retryable,
            "attempts": email.attempts,
            "failed_at": now.isoformat(),
            "provider": email.provider,
        }

        self._record_audit_event(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            action="email_outbox.failed",
            entity_id=email.id,
            summary=(
                f"Email outbox message failed for {email.to_email}."
            ),
            details={
                "email_outbox_id": str(email.id),
                "document_delivery_id": str(
                    email.document_delivery_id
                ),
                "provider": email.provider,
                "reason": payload.reason,
                "retryable": payload.retryable,
                "attempts": email.attempts,
            },
        )

        self.db.commit()
        self.db.refresh(email)

        return self._build_response(email)

    def retry_email(
        self,
        *,
        organization_id: uuid.UUID,
        email_outbox_id: uuid.UUID,
        payload: EmailOutboxRetryRequest,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> EmailOutboxResponse:
        """
        Re-queue a failed email for another provider attempt.
        """

        email = self._get_email_or_404(
            organization_id=organization_id,
            email_outbox_id=email_outbox_id,
        )

        if email.status not in {
            "failed",
            "cancelled",
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only failed or cancelled emails can be "
                    "queued for retry."
                ),
            )

        if email.attempts >= email.max_attempts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Email has reached the maximum retry attempts."
                ),
            )

        now = datetime.now(UTC)

        email.status = "queued"
        email.next_attempt_at = now
        email.failed_at = None
        email.last_error = None

        delivery = email.document_delivery
        delivery.delivery_status = "queued"

        delivery_details = {
            **(delivery.details or {}),
        }

        for stale_key in (
            "last_error",
            "retryable",
            "failed_at",
        ):
            delivery_details.pop(stale_key, None)

        delivery.details = {
            **delivery_details,
            "email_outbox_id": str(email.id),
            "email_outbox_status": email.status,
            "retry_note": payload.note,
            "provider": email.provider,
        }

        self._record_audit_event(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            action="email_outbox.retry_queued",
            entity_id=email.id,
            summary=(
                f"Email outbox message queued for retry "
                f"to {email.to_email}."
            ),
            details={
                "email_outbox_id": str(email.id),
                "document_delivery_id": str(
                    email.document_delivery_id
                ),
                "provider": email.provider,
                "attempts": email.attempts,
                "max_attempts": email.max_attempts,
                "note": payload.note,
            },
        )

        self.db.commit()
        self.db.refresh(email)

        return self._build_response(email)

    def _get_email_or_404(
        self,
        *,
        organization_id: uuid.UUID,
        email_outbox_id: uuid.UUID,
    ) -> EmailOutbox:
        email = self.emails.get_for_organization(
            organization_id=organization_id,
            email_outbox_id=email_outbox_id,
        )

        if email is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email outbox message not found.",
            )

        return email

    def _record_audit_event(
        self,
        *,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
        action: str,
        entity_id: uuid.UUID,
        summary: str,
        details: dict,
    ) -> None:
        self.audit_logs.record_event(
            organization_id=organization_id,
            payload=AuditLogCreate(
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action=action,
                entity_type="email_outbox",
                entity_id=entity_id,
                summary=summary,
                status="success",
                request_method="SYSTEM",
                request_path="/system/email-outbox",
                details=details,
            ),
            commit=False,
        )

    @staticmethod
    def _build_response(
        email: EmailOutbox,
    ) -> EmailOutboxResponse:
        queued_by = email.queued_by

        return EmailOutboxResponse(
            id=email.id,
            organization_id=email.organization_id,
            document_delivery_id=email.document_delivery_id,
            queued_by_user_id=email.queued_by_user_id,
            queued_by_first_name=(
                queued_by.first_name
                if queued_by
                else None
            ),
            queued_by_last_name=(
                queued_by.last_name
                if queued_by
                else None
            ),
            queued_by_email=(
                queued_by.email
                if queued_by
                else None
            ),
            provider=email.provider,
            status=email.status,
            from_email=email.from_email,
            from_name=email.from_name,
            reply_to_email=email.reply_to_email,
            to_email=email.to_email,
            to_name=email.to_name,
            subject=email.subject,
            body_text=email.body_text,
            body_html=email.body_html,
            attachment_filename=email.attachment_filename,
            attempts=email.attempts,
            max_attempts=email.max_attempts,
            next_attempt_at=email.next_attempt_at,
            queued_at=email.queued_at,
            sent_at=email.sent_at,
            failed_at=email.failed_at,
            last_error=email.last_error,
            provider_message_id=email.provider_message_id,
            details=email.details or {},
            is_active=email.is_active,
            created_at=email.created_at,
            updated_at=email.updated_at,
        )
