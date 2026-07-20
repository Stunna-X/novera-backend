"""
Email outbox dispatcher service.

Claims due messages atomically, sends them through configured
providers, schedules retries, recovers stale worker claims, and
synchronizes document-delivery and audit records.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.email.providers.base import (
    EmailProviderError,
    EmailSendResult,
    OutboundEmailMessage,
)
from app.email.providers.factory import (
    build_email_provider,
)
from app.models.email_outbox import EmailOutbox
from app.repositories.email_outbox import (
    EmailOutboxRepository,
)
from app.schemas.audit_log import AuditLogCreate
from app.services.audit_log_service import (
    AuditLogService,
)
from app.services.email_attachment_service import (
    EmailAttachmentBuildError,
    EmailAttachmentService,
)


class EmailDispatcherService:
    """
    Worker-facing email dispatch lifecycle.
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db
        self.emails = EmailOutboxRepository(db)
        self.attachments = EmailAttachmentService(db)
        self.audit_logs = AuditLogService(db)

    def recover_stale_sending(
        self,
        *,
        limit: int | None = None,
    ) -> int:
        """
        Recover messages left in `sending` by crashed workers.
        """

        now = datetime.now(UTC)

        stale_before = now - timedelta(
            seconds=(
                settings
                .EMAIL_OUTBOX_STALE_AFTER_SECONDS
            )
        )

        stale_messages = (
            self.emails.lock_stale_sending(
                stale_before=stale_before,
                limit=(
                    limit
                    or settings.EMAIL_OUTBOX_BATCH_SIZE
                ),
            )
        )

        for email in stale_messages:
            terminal = (
                email.attempts >= email.max_attempts
            )

            email.status = (
                "failed"
                if terminal
                else "queued"
            )

            email.failed_at = (
                now
                if terminal
                else None
            )

            email.next_attempt_at = (
                None
                if terminal
                else now
            )

            email.last_error = (
                "Recovered after a stale worker claim."
            )

            email.details = {
                **(email.details or {}),
                "stale_claim_recovered_at": (
                    now.isoformat()
                ),
                "stale_claim_terminal": terminal,
                "attempts": email.attempts,
                "max_attempts": email.max_attempts,
            }

            delivery = email.document_delivery

            if delivery is not None:
                delivery.delivery_status = (
                    "failed"
                    if terminal
                    else "queued"
                )

                delivery.details = {
                    **(delivery.details or {}),
                    "email_outbox_id": str(email.id),
                    "email_outbox_status": (
                        email.status
                    ),
                    "stale_claim_recovered_at": (
                        now.isoformat()
                    ),
                    "stale_claim_terminal": terminal,
                }

            self._record_audit_event(
                email=email,
                action=(
                    "email_outbox.stale_failed"
                    if terminal
                    else "email_outbox.stale_requeued"
                ),
                summary=(
                    "Stale email worker claim reached "
                    "its maximum attempts."
                    if terminal
                    else (
                        "Stale email worker claim was "
                        "returned to the queue."
                    )
                ),
                status_value=(
                    "failed"
                    if terminal
                    else "success"
                ),
                details={
                    "attempts": email.attempts,
                    "max_attempts": (
                        email.max_attempts
                    ),
                    "stale_before": (
                        stale_before.isoformat()
                    ),
                },
            )

        if stale_messages:
            self.db.commit()

        return len(
            stale_messages
        )

    def claim_due_batch(
        self,
        *,
        limit: int | None = None,
    ) -> list[uuid.UUID]:
        """
        Atomically claim one batch of due messages.
        """

        now = datetime.now(UTC)

        messages = self.emails.lock_due_for_dispatch(
            now=now,
            limit=(
                limit
                or settings.EMAIL_OUTBOX_BATCH_SIZE
            ),
        )

        claimed_ids: list[uuid.UUID] = []

        for email in messages:
            email.status = "sending"
            email.attempts += 1
            email.next_attempt_at = None
            email.failed_at = None

            email.details = {
                **(email.details or {}),
                "dispatch_started_at": (
                    now.isoformat()
                ),
                "dispatch_attempt": email.attempts,
                "worker_state": "sending",
            }

            delivery = email.document_delivery

            if delivery is not None:
                delivery.delivery_status = "queued"

                delivery.details = {
                    **(delivery.details or {}),
                    "email_outbox_id": str(email.id),
                    "email_outbox_status": (
                        email.status
                    ),
                    "dispatch_attempt": (
                        email.attempts
                    ),
                    "dispatch_started_at": (
                        now.isoformat()
                    ),
                }

            claimed_ids.append(
                email.id
            )

        if messages:
            self.db.commit()

        return claimed_ids

    def dispatch_claimed(
        self,
        *,
        email_outbox_id: uuid.UUID,
    ) -> bool:
        """
        Dispatch one message already claimed by a worker.

        Returns True when the provider accepts the message and
        False when the attempt is recorded as failed.
        """

        email = self.emails.get_claimed_for_dispatch(
            email_outbox_id=email_outbox_id,
        )

        if email is None:
            return False

        try:
            attachments = (
                self.attachments.build_for_outbox(
                    email
                )
            )

            provider = build_email_provider(
                email.provider
            )

            message = OutboundEmailMessage(
                from_email=email.from_email,
                from_name=email.from_name,
                reply_to_email=(
                    email.reply_to_email
                ),
                to_email=email.to_email,
                to_name=email.to_name,
                subject=email.subject,
                body_text=email.body_text,
                body_html=email.body_html,
                message_id=(
                    self._stable_message_id(email)
                ),
                attachments=attachments,
                headers={
                    "X-Novera-Outbox-ID": str(
                        email.id
                    ),
                    "X-Novera-Delivery-ID": str(
                        email.document_delivery_id
                    ),
                    "X-Novera-Organization-ID": str(
                        email.organization_id
                    ),
                },
            )

            result = provider.send(
                message
            )

        except EmailAttachmentBuildError as exc:
            return self._record_failure(
                email_outbox_id=email.id,
                reason=str(exc),
                retryable=exc.retryable,
                code=exc.code,
                error_details=exc.details,
            )

        except EmailProviderError as exc:
            return self._record_failure(
                email_outbox_id=email.id,
                reason=str(exc),
                retryable=exc.retryable,
                code=exc.code,
                error_details=exc.details,
            )

        except ValueError as exc:
            return self._record_failure(
                email_outbox_id=email.id,
                reason=str(exc),
                retryable=False,
                code="email_payload_invalid",
                error_details={
                    "error_type": type(exc).__name__,
                },
            )

        except Exception as exc:
            return self._record_failure(
                email_outbox_id=email.id,
                reason=(
                    "Unexpected email dispatch error."
                ),
                retryable=True,
                code="email_dispatch_unexpected",
                error_details={
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )

        return self._record_success(
            email=email,
            result=result,
        )

    def _record_success(
        self,
        *,
        email: EmailOutbox,
        result: EmailSendResult,
    ) -> bool:
        email.status = "sent"
        email.sent_at = result.accepted_at
        email.failed_at = None
        email.next_attempt_at = None
        email.last_error = None
        email.provider_message_id = (
            result.message_id
        )

        email_details = {
            **(email.details or {}),
        }

        for stale_key in (
            "failure",
            "failure_code",
            "failed_at",
            "last_error",
            "retry_at",
            "retry_note",
            "retry_scheduled",
            "retryable",
        ):
            email_details.pop(
                stale_key,
                None,
            )

        email.details = {
            **email_details,
            "worker_state": "sent",
            "provider_mode": "provider_dispatched",
            "provider": result.provider,
            "provider_message_id": (
                result.message_id
            ),
            "provider_accepted_at": (
                result.accepted_at.isoformat()
            ),
            "provider_result": (
                result.details
            ),
            "dispatch_attempt": email.attempts,
        }

        delivery = email.document_delivery

        if delivery is not None:
            delivery.delivery_status = "sent"
            delivery.sent_at = result.accepted_at
            delivery.provider = result.provider

            delivery_details = {
                **(delivery.details or {}),
            }

            for stale_key in (
                "attempts",
                "failed_at",
                "failure_code",
                "last_error",
                "max_attempts",
                "retry_at",
                "retry_note",
                "retry_scheduled",
                "retryable",
            ):
                delivery_details.pop(
                    stale_key,
                    None,
                )

            delivery.details = {
                **delivery_details,
                "email_outbox_id": str(email.id),
                "email_outbox_status": (
                    email.status
                ),
                "provider_mode": "provider_dispatched",
                "provider": result.provider,
                "provider_message_id": (
                    result.message_id
                ),
                "provider_accepted_at": (
                    result.accepted_at.isoformat()
                ),
                "dispatch_attempt": (
                    email.attempts
                ),
            }

        self._record_audit_event(
            email=email,
            action="email_outbox.dispatched",
            summary=(
                f"Email accepted by {result.provider} "
                f"for {email.to_email}."
            ),
            status_value="success",
            details={
                "provider": result.provider,
                "provider_message_id": (
                    result.message_id
                ),
                "dispatch_attempt": (
                    email.attempts
                ),
                "provider_result": result.details,
            },
        )

        self.db.commit()

        return True

    def _record_failure(
        self,
        *,
        email_outbox_id: uuid.UUID,
        reason: str,
        retryable: bool,
        code: str | None,
        error_details: dict[str, Any],
    ) -> bool:
        """
        Record a failed provider or attachment attempt.
        """

        self.db.rollback()

        email = self.emails.get_claimed_for_dispatch(
            email_outbox_id=email_outbox_id,
        )

        if email is None:
            return False

        now = datetime.now(UTC)

        may_retry = (
            retryable
            and email.attempts < email.max_attempts
        )

        retry_at = (
            now + timedelta(
                seconds=self._retry_delay_seconds(
                    attempts=email.attempts
                )
            )
            if may_retry
            else None
        )

        email.status = "failed"
        email.failed_at = now
        email.last_error = reason
        email.next_attempt_at = retry_at

        email.details = {
            **(email.details or {}),
            "worker_state": "failed",
            "last_error": reason,
            "failure_code": code,
            "failure": error_details,
            "retryable": retryable,
            "retry_scheduled": may_retry,
            "retry_at": (
                retry_at.isoformat()
                if retry_at
                else None
            ),
            "dispatch_attempt": email.attempts,
            "failed_at": now.isoformat(),
        }

        delivery = email.document_delivery

        if delivery is not None:
            delivery.delivery_status = "failed"

            delivery.details = {
                **(delivery.details or {}),
                "email_outbox_id": str(email.id),
                "email_outbox_status": (
                    email.status
                ),
                "last_error": reason,
                "failure_code": code,
                "retryable": retryable,
                "retry_scheduled": may_retry,
                "retry_at": (
                    retry_at.isoformat()
                    if retry_at
                    else None
                ),
                "attempts": email.attempts,
                "max_attempts": (
                    email.max_attempts
                ),
                "failed_at": now.isoformat(),
                "provider": email.provider,
            }

        self._record_audit_event(
            email=email,
            action="email_outbox.dispatch_failed",
            summary=(
                f"Email dispatch failed for "
                f"{email.to_email}."
            ),
            status_value="failed",
            details={
                "provider": email.provider,
                "reason": reason,
                "failure_code": code,
                "failure": error_details,
                "retryable": retryable,
                "retry_scheduled": may_retry,
                "retry_at": (
                    retry_at.isoformat()
                    if retry_at
                    else None
                ),
                "attempts": email.attempts,
                "max_attempts": (
                    email.max_attempts
                ),
            },
        )

        self.db.commit()

        return False

    def _record_audit_event(
        self,
        *,
        email: EmailOutbox,
        action: str,
        summary: str,
        status_value: str,
        details: dict[str, Any],
    ) -> None:
        self.audit_logs.record_event(
            organization_id=email.organization_id,
            payload=AuditLogCreate(
                actor_user_id=(
                    email.queued_by_user_id
                ),
                actor_membership_id=None,
                action=action,
                entity_type="email_outbox",
                entity_id=email.id,
                summary=summary,
                status=status_value,
                request_method="SYSTEM",
                request_path=(
                    "/system/email-outbox-worker"
                ),
                details={
                    "email_outbox_id": str(email.id),
                    "document_delivery_id": str(
                        email.document_delivery_id
                    ),
                    "recipient_email": (
                        email.to_email
                    ),
                    **details,
                },
            ),
            commit=False,
        )

    @staticmethod
    def _stable_message_id(
        email: EmailOutbox,
    ) -> str:
        """
        Generate a stable RFC Message-ID for retries.
        """

        from_domain = ""

        if "@" in email.from_email:
            from_domain = (
                email.from_email
                .rsplit("@", 1)[1]
                .strip()
                .lower()
            )

        domain = (
            from_domain
            or "novera.local"
        )

        return (
            f"novera-{email.id}@{domain}"
        )

    @staticmethod
    def _retry_delay_seconds(
        *,
        attempts: int,
    ) -> int:
        """
        Exponential retry delay capped by configuration.
        """

        exponent = max(
            attempts - 1,
            0,
        )

        delay = (
            settings.EMAIL_OUTBOX_RETRY_BASE_SECONDS
            * (2 ** exponent)
        )

        return min(
            delay,
            settings.EMAIL_OUTBOX_RETRY_MAX_SECONDS,
        )