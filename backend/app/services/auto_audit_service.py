"""
Automatic audit event service.

Records business/security audit events inside the same database
transaction as the business action that triggered them.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.request_context import get_request_audit_context
from app.models.membership import Membership
from app.schemas.audit_log import AuditLogCreate
from app.services.audit_log_service import AuditLogService


class AutoAuditService:
    """
    Convenience wrapper for common audit events.
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db
        self.audit_logs = AuditLogService(db)

    @staticmethod
    def _value(value: Any) -> str | None:
        """
        Convert simple values to JSON-safe strings.
        """

        if value is None:
            return None

        return str(value)

    @staticmethod
    def _iso(value: Any) -> str | None:
        """
        Convert datetime/date-like values to ISO strings.
        """

        if value is None:
            return None

        if hasattr(value, "isoformat"):
            return value.isoformat()

        return str(value)

    def _actor_membership_id(
        self,
        *,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
    ) -> uuid.UUID | None:
        """
        Resolve the actor's organization membership ID.

        Automatic audit events usually receive only actor_user_id
        from business services. This lookup enriches the audit log
        with the matching membership for the organization.
        """

        if actor_user_id is None:
            return None

        return (
            self.db.query(Membership.id)
            .filter(
                Membership.organization_id == organization_id,
                Membership.user_id == actor_user_id,
            )
            .scalar()
        )

    def _record(
        self,
        *,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None,
        summary: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Record one audit event without committing.
        """

        request_context = get_request_audit_context()

        self.audit_logs.record_event(
            organization_id=organization_id,
            payload=AuditLogCreate(
                actor_user_id=actor_user_id,
                actor_membership_id=self._actor_membership_id(
                    organization_id=organization_id,
                    actor_user_id=actor_user_id,
                ),
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                summary=summary,
                status="success",
                request_method=(
                    request_context.method
                    if request_context is not None
                    else "SYSTEM"
                ),
                request_path=(
                    request_context.path
                    if request_context is not None
                    else "/system/business-event"
                ),
                ip_address=(
                    request_context.ip_address
                    if request_context is not None
                    else None
                ),
                user_agent=(
                    request_context.user_agent
                    if request_context is not None
                    else None
                ),
                details=details or {},
            ),
            commit=False,
        )

    def quote_accepted(
        self,
        *,
        organization_id: uuid.UUID,
        quote,
        actor_user_id: uuid.UUID,
    ) -> None:
        self._record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="quote.accepted",
            entity_type="quote",
            entity_id=quote.id,
            summary=f"Quote {quote.quote_number} accepted.",
            details={
                "quote_id": str(quote.id),
                "quote_number": quote.quote_number,
                "customer_id": self._value(quote.customer_id),
                "currency": quote.currency,
                "total_amount": self._value(quote.total_amount),
                "status": quote.status,
            },
        )

    def quote_converted(
        self,
        *,
        organization_id: uuid.UUID,
        quote,
        work_order,
        actor_user_id: uuid.UUID,
    ) -> None:
        self._record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="quote.converted",
            entity_type="quote",
            entity_id=quote.id,
            summary=(
                f"Quote {quote.quote_number} converted "
                f"to work order {work_order.work_order_number}."
            ),
            details={
                "quote_id": str(quote.id),
                "quote_number": quote.quote_number,
                "work_order_id": str(work_order.id),
                "work_order_number": work_order.work_order_number,
                "currency": quote.currency,
                "total_amount": self._value(quote.total_amount),
                "status": quote.status,
            },
        )

    def work_order_scheduled(
        self,
        *,
        organization_id: uuid.UUID,
        work_order,
        actor_user_id: uuid.UUID,
    ) -> None:
        self._record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="work_order.scheduled",
            entity_type="work_order",
            entity_id=work_order.id,
            summary=(
                f"Work order {work_order.work_order_number} scheduled."
            ),
            details={
                "work_order_id": str(work_order.id),
                "work_order_number": work_order.work_order_number,
                "status": work_order.status,
                "scheduled_start": self._iso(
                    work_order.scheduled_start
                ),
                "scheduled_end": self._iso(
                    work_order.scheduled_end
                ),
            },
        )

    def work_order_dispatched(
        self,
        *,
        organization_id: uuid.UUID,
        work_order,
        actor_user_id: uuid.UUID,
    ) -> None:
        self._record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="work_order.dispatched",
            entity_type="work_order",
            entity_id=work_order.id,
            summary=(
                f"Work order {work_order.work_order_number} dispatched."
            ),
            details={
                "work_order_id": str(work_order.id),
                "work_order_number": work_order.work_order_number,
                "status": work_order.status,
                "scheduled_start": self._iso(
                    work_order.scheduled_start
                ),
                "scheduled_end": self._iso(
                    work_order.scheduled_end
                ),
            },
        )

    def work_order_status_changed(
        self,
        *,
        organization_id: uuid.UUID,
        work_order,
        actor_user_id: uuid.UUID,
        previous_status: str,
    ) -> None:
        self._record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="work_order.status_changed",
            entity_type="work_order",
            entity_id=work_order.id,
            summary=(
                f"Work order {work_order.work_order_number} "
                f"changed from {previous_status} to {work_order.status}."
            ),
            details={
                "work_order_id": str(work_order.id),
                "work_order_number": work_order.work_order_number,
                "from_status": previous_status,
                "to_status": work_order.status,
            },
        )

    def closeout_approved(
        self,
        *,
        organization_id: uuid.UUID,
        work_order,
        closeout,
        actor_user_id: uuid.UUID,
    ) -> None:
        self._record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="closeout.approved",
            entity_type="work_order_closeout",
            entity_id=closeout.id,
            summary=(
                f"Closeout approved for work order "
                f"{work_order.work_order_number}."
            ),
            details={
                "closeout_id": str(closeout.id),
                "work_order_id": str(work_order.id),
                "work_order_number": work_order.work_order_number,
                "status": closeout.status,
                "is_invoice_ready": closeout.is_invoice_ready,
            },
        )

    def closeout_invoice_ready(
        self,
        *,
        organization_id: uuid.UUID,
        work_order,
        closeout,
        actor_user_id: uuid.UUID,
    ) -> None:
        self._record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="closeout.invoice_ready",
            entity_type="work_order_closeout",
            entity_id=closeout.id,
            summary=(
                f"Closeout for work order "
                f"{work_order.work_order_number} marked invoice-ready."
            ),
            details={
                "closeout_id": str(closeout.id),
                "work_order_id": str(work_order.id),
                "work_order_number": work_order.work_order_number,
                "status": closeout.status,
                "is_invoice_ready": closeout.is_invoice_ready,
            },
        )

    def invoice_created(
        self,
        *,
        organization_id: uuid.UUID,
        invoice,
        actor_user_id: uuid.UUID,
        source: str,
    ) -> None:
        self._record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="invoice.created",
            entity_type="invoice",
            entity_id=invoice.id,
            summary=f"Invoice {invoice.invoice_number} created.",
            details={
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "work_order_id": self._value(invoice.work_order_id),
                "customer_id": self._value(invoice.customer_id),
                "source": source,
                "currency": invoice.currency,
                "total_amount": self._value(invoice.total_amount),
                "status": invoice.status,
            },
        )

    def invoice_issued(
        self,
        *,
        organization_id: uuid.UUID,
        invoice,
        actor_user_id: uuid.UUID,
    ) -> None:
        self._record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="invoice.issued",
            entity_type="invoice",
            entity_id=invoice.id,
            summary=f"Invoice {invoice.invoice_number} issued.",
            details={
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "work_order_id": self._value(invoice.work_order_id),
                "customer_id": self._value(invoice.customer_id),
                "currency": invoice.currency,
                "total_amount": self._value(invoice.total_amount),
                "balance_due": self._value(invoice.balance_due),
                "status": invoice.status,
                "due_date": self._iso(invoice.due_date),
            },
        )

    def invoice_payment_recorded(
        self,
        *,
        organization_id: uuid.UUID,
        invoice,
        payment,
        actor_user_id: uuid.UUID,
        previous_status: str,
    ) -> None:
        self._record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="invoice.payment_recorded",
            entity_type="invoice",
            entity_id=invoice.id,
            summary=(
                f"Payment recorded for invoice "
                f"{invoice.invoice_number}."
            ),
            details={
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "payment_id": str(payment.id),
                "amount": self._value(payment.amount),
                "currency": payment.currency,
                "payment_method": payment.payment_method,
                "reference_number": payment.reference_number,
                "from_status": previous_status,
                "to_status": invoice.status,
                "amount_paid": self._value(invoice.amount_paid),
                "balance_due": self._value(invoice.balance_due),
            },
        )

    def invoice_payment_reversed(
        self,
        *,
        organization_id: uuid.UUID,
        invoice,
        payment,
        actor_user_id: uuid.UUID,
        previous_status: str,
    ) -> None:
        self._record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="invoice.payment_reversed",
            entity_type="invoice",
            entity_id=invoice.id,
            summary=(
                f"Payment reversed for invoice "
                f"{invoice.invoice_number}."
            ),
            details={
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "payment_id": str(payment.id),
                "amount": self._value(payment.amount),
                "currency": payment.currency,
                "from_status": previous_status,
                "to_status": invoice.status,
                "amount_paid": self._value(invoice.amount_paid),
                "balance_due": self._value(invoice.balance_due),
            },
        )

    def notification_created(
        self,
        *,
        organization_id: uuid.UUID,
        notification,
        actor_user_id: uuid.UUID | None,
    ) -> None:
        self._record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="notification.created",
            entity_type="notification",
            entity_id=notification.id,
            summary=f"Notification '{notification.title}' created.",
            details={
                "notification_id": str(notification.id),
                "recipient_user_id": str(notification.recipient_user_id),
                "notification_type": notification.notification_type,
                "priority": notification.priority,
                "entity_type": notification.entity_type,
                "entity_id": self._value(notification.entity_id),
            },
        )
