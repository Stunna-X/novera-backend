"""
Auto-notification service.

Queues organization-scoped notifications for important business
events without committing independently. The calling service owns
the transaction.
"""

from __future__ import annotations

import uuid
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.membership import Membership
from app.models.notification import Notification
from app.models.role import Role
from app.models.work_order import (
    WorkOrder,
    WorkOrderWorkforceAssignment,
)
from app.models.workforce_profile import WorkforceProfile


MANAGER_ROLE_NAMES = {
    "owner",
    "admin",
    "operations manager",
    "supervisor",
}

FINANCE_ROLE_NAMES = {
    "owner",
    "admin",
}


class AutoNotificationService:
    """
    Creates notifications from domain events.

    This service deliberately does not commit. It only adds and
    flushes notifications so the parent business operation and
    its notifications succeed or fail together.
    """

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    @staticmethod
    def _dedupe(
        values: Iterable[uuid.UUID | None],
    ) -> list[uuid.UUID]:
        """
        Return unique UUIDs while preserving order.
        """

        seen: set[uuid.UUID] = set()
        output: list[uuid.UUID] = []

        for value in values:
            if value is None:
                continue

            if value in seen:
                continue

            seen.add(value)
            output.append(value)

        return output

    def _role_user_ids(
        self,
        *,
        organization_id: uuid.UUID,
        role_names: set[str],
    ) -> list[uuid.UUID]:
        """
        Return users whose organization role name matches.
        """

        normalized_roles = {
            role.strip().lower()
            for role in role_names
            if role.strip()
        }

        if not normalized_roles:
            return []

        rows = (
            self.db.query(
                Membership.user_id
            )
            .join(
                Role,
                Membership.role_id == Role.id,
            )
            .filter(
                Membership.organization_id == organization_id,
                func.lower(Role.name).in_(normalized_roles),
            )
            .order_by(
                Membership.created_at.asc()
            )
            .all()
        )

        return self._dedupe(
            row[0]
            for row in rows
        )

    def _assigned_work_order_user_ids(
        self,
        *,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        """
        Return users assigned to a work order through workforce
        profiles.
        """

        rows = (
            self.db.query(
                Membership.user_id
            )
            .join(
                WorkforceProfile,
                WorkforceProfile.membership_id
                == Membership.id,
            )
            .join(
                WorkOrderWorkforceAssignment,
                WorkOrderWorkforceAssignment.workforce_profile_id
                == WorkforceProfile.id,
            )
            .filter(
                Membership.organization_id == organization_id,
                WorkforceProfile.organization_id == organization_id,
                WorkOrderWorkforceAssignment.work_order_id
                == work_order_id,
            )
            .order_by(
                Membership.created_at.asc()
            )
            .all()
        )

        return self._dedupe(
            row[0]
            for row in rows
        )

    def _notify(
        self,
        *,
        organization_id: uuid.UUID,
        recipient_user_ids: Iterable[uuid.UUID | None],
        actor_user_id: uuid.UUID | None,
        notification_type: str,
        title: str,
        message: str,
        priority: str = "info",
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        action_url: str | None = None,
        payload: dict | None = None,
    ) -> None:
        """
        Queue one notification per recipient.
        """

        recipients = self._dedupe(
            recipient_user_ids
        )

        for recipient_user_id in recipients:
            self.db.add(
                Notification(
                    organization_id=organization_id,
                    recipient_user_id=recipient_user_id,
                    actor_user_id=actor_user_id,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    priority=priority,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    action_url=action_url,
                    payload=payload or {},
                    is_read=False,
                    is_archived=False,
                )
            )

        if recipients:
            self.db.flush()

    def notify_quote_accepted(
        self,
        *,
        organization_id: uuid.UUID,
        quote,
        actor_user_id: uuid.UUID,
    ) -> None:
        """
        Notify managers that a quote has been accepted.
        """

        self._notify(
            organization_id=organization_id,
            recipient_user_ids=self._role_user_ids(
                organization_id=organization_id,
                role_names=MANAGER_ROLE_NAMES,
            ),
            actor_user_id=actor_user_id,
            notification_type="quote_accepted",
            title="Quote accepted",
            message=(
                f"Quote {quote.quote_number} was accepted."
            ),
            priority="success",
            entity_type="quote",
            entity_id=quote.id,
            action_url=f"/quotes/{quote.id}",
            payload={
                "quote_number": quote.quote_number,
                "customer_id": str(quote.customer_id),
                "currency": quote.currency,
                "total_amount": str(quote.total_amount),
            },
        )

    def notify_quote_converted(
        self,
        *,
        organization_id: uuid.UUID,
        quote,
        work_order: WorkOrder,
        actor_user_id: uuid.UUID,
    ) -> None:
        """
        Notify managers that a quote became a work order.
        """

        self._notify(
            organization_id=organization_id,
            recipient_user_ids=self._role_user_ids(
                organization_id=organization_id,
                role_names=MANAGER_ROLE_NAMES,
            ),
            actor_user_id=actor_user_id,
            notification_type="quote_converted",
            title="Quote converted",
            message=(
                f"Quote {quote.quote_number} was converted "
                f"into work order {work_order.work_order_number}."
            ),
            priority="success",
            entity_type="work_order",
            entity_id=work_order.id,
            action_url=f"/work-orders/{work_order.id}",
            payload={
                "quote_id": str(quote.id),
                "quote_number": quote.quote_number,
                "work_order_id": str(work_order.id),
                "work_order_number": work_order.work_order_number,
                "currency": quote.currency,
                "total_amount": str(quote.total_amount),
            },
        )

    def notify_work_order_scheduled(
        self,
        *,
        organization_id: uuid.UUID,
        work_order: WorkOrder,
        actor_user_id: uuid.UUID,
    ) -> None:
        """
        Notify assigned workforce that a work order was scheduled.
        """

        self._notify(
            organization_id=organization_id,
            recipient_user_ids=self._assigned_work_order_user_ids(
                organization_id=organization_id,
                work_order_id=work_order.id,
            ),
            actor_user_id=actor_user_id,
            notification_type="work_order_scheduled",
            title="Work order scheduled",
            message=(
                f"Work order {work_order.work_order_number} "
                "has been scheduled."
            ),
            priority="info",
            entity_type="work_order",
            entity_id=work_order.id,
            action_url=f"/work-orders/{work_order.id}",
            payload={
                "work_order_number": work_order.work_order_number,
                "scheduled_start": (
                    work_order.scheduled_start.isoformat()
                    if work_order.scheduled_start
                    else None
                ),
                "scheduled_end": (
                    work_order.scheduled_end.isoformat()
                    if work_order.scheduled_end
                    else None
                ),
            },
        )

    def notify_work_order_dispatched(
        self,
        *,
        organization_id: uuid.UUID,
        work_order: WorkOrder,
        actor_user_id: uuid.UUID,
    ) -> None:
        """
        Notify assigned workforce that a work order was dispatched.
        """

        self._notify(
            organization_id=organization_id,
            recipient_user_ids=self._assigned_work_order_user_ids(
                organization_id=organization_id,
                work_order_id=work_order.id,
            ),
            actor_user_id=actor_user_id,
            notification_type="work_order_dispatched",
            title="Work order dispatched",
            message=(
                f"Work order {work_order.work_order_number} "
                "has been dispatched."
            ),
            priority="warning",
            entity_type="work_order",
            entity_id=work_order.id,
            action_url=f"/work-orders/{work_order.id}",
            payload={
                "work_order_number": work_order.work_order_number,
                "scheduled_start": (
                    work_order.scheduled_start.isoformat()
                    if work_order.scheduled_start
                    else None
                ),
                "scheduled_end": (
                    work_order.scheduled_end.isoformat()
                    if work_order.scheduled_end
                    else None
                ),
            },
        )

    def notify_work_order_completed(
        self,
        *,
        organization_id: uuid.UUID,
        work_order: WorkOrder,
        actor_user_id: uuid.UUID,
    ) -> None:
        """
        Notify managers that a work order was completed.
        """

        self._notify(
            organization_id=organization_id,
            recipient_user_ids=self._role_user_ids(
                organization_id=organization_id,
                role_names=MANAGER_ROLE_NAMES,
            ),
            actor_user_id=actor_user_id,
            notification_type="work_order_completed",
            title="Work order completed",
            message=(
                f"Work order {work_order.work_order_number} "
                "has been completed."
            ),
            priority="success",
            entity_type="work_order",
            entity_id=work_order.id,
            action_url=f"/work-orders/{work_order.id}",
            payload={
                "work_order_number": work_order.work_order_number,
                "actual_end": (
                    work_order.actual_end.isoformat()
                    if work_order.actual_end
                    else None
                ),
            },
        )

    def notify_closeout_approved(
        self,
        *,
        organization_id: uuid.UUID,
        closeout,
        work_order: WorkOrder,
        actor_user_id: uuid.UUID,
    ) -> None:
        """
        Notify finance users that a closeout was approved.
        """

        self._notify(
            organization_id=organization_id,
            recipient_user_ids=self._role_user_ids(
                organization_id=organization_id,
                role_names=FINANCE_ROLE_NAMES,
            ),
            actor_user_id=actor_user_id,
            notification_type="closeout_approved",
            title="Closeout approved",
            message=(
                f"Closeout for work order "
                f"{work_order.work_order_number} was approved."
            ),
            priority="success",
            entity_type="work_order_closeout",
            entity_id=closeout.id,
            action_url=f"/work-orders/{work_order.id}/closeout",
            payload={
                "work_order_id": str(work_order.id),
                "work_order_number": work_order.work_order_number,
                "closeout_id": str(closeout.id),
                "is_invoice_ready": closeout.is_invoice_ready,
            },
        )

    def notify_closeout_invoice_ready(
        self,
        *,
        organization_id: uuid.UUID,
        closeout,
        work_order: WorkOrder,
        actor_user_id: uuid.UUID,
    ) -> None:
        """
        Notify finance users that a closeout is invoice-ready.
        """

        self._notify(
            organization_id=organization_id,
            recipient_user_ids=self._role_user_ids(
                organization_id=organization_id,
                role_names=FINANCE_ROLE_NAMES,
            ),
            actor_user_id=actor_user_id,
            notification_type="closeout_invoice_ready",
            title="Closeout ready for invoice",
            message=(
                f"Work order {work_order.work_order_number} "
                "is ready for final invoice."
            ),
            priority="warning",
            entity_type="work_order_closeout",
            entity_id=closeout.id,
            action_url=f"/work-orders/{work_order.id}/closeout",
            payload={
                "work_order_id": str(work_order.id),
                "work_order_number": work_order.work_order_number,
                "closeout_id": str(closeout.id),
            },
        )

    def notify_invoice_issued(
        self,
        *,
        organization_id: uuid.UUID,
        invoice,
        actor_user_id: uuid.UUID,
    ) -> None:
        """
        Notify finance users that an invoice was issued.
        """

        self._notify(
            organization_id=organization_id,
            recipient_user_ids=self._role_user_ids(
                organization_id=organization_id,
                role_names=FINANCE_ROLE_NAMES,
            ),
            actor_user_id=actor_user_id,
            notification_type="invoice_issued",
            title="Invoice issued",
            message=(
                f"Invoice {invoice.invoice_number} "
                "has been issued."
            ),
            priority="success",
            entity_type="invoice",
            entity_id=invoice.id,
            action_url=f"/invoices/{invoice.id}",
            payload={
                "invoice_number": invoice.invoice_number,
                "customer_id": str(invoice.customer_id),
                "work_order_id": (
                    str(invoice.work_order_id)
                    if invoice.work_order_id
                    else None
                ),
                "currency": invoice.currency,
                "total_amount": str(invoice.total_amount),
                "balance_due": str(invoice.balance_due),
            },
        )

    def notify_payment_recorded(
        self,
        *,
        organization_id: uuid.UUID,
        invoice,
        payment,
        actor_user_id: uuid.UUID,
    ) -> None:
        """
        Notify finance users that a payment was recorded.
        """

        self._notify(
            organization_id=organization_id,
            recipient_user_ids=self._role_user_ids(
                organization_id=organization_id,
                role_names=FINANCE_ROLE_NAMES,
            ),
            actor_user_id=actor_user_id,
            notification_type="invoice_payment_recorded",
            title="Payment recorded",
            message=(
                f"Payment of {payment.currency} {payment.amount} "
                f"was recorded for invoice {invoice.invoice_number}."
            ),
            priority="success",
            entity_type="invoice",
            entity_id=invoice.id,
            action_url=f"/invoices/{invoice.id}",
            payload={
                "invoice_number": invoice.invoice_number,
                "payment_id": str(payment.id),
                "amount": str(payment.amount),
                "currency": payment.currency,
                "payment_method": payment.payment_method,
                "amount_paid": str(invoice.amount_paid),
                "balance_due": str(invoice.balance_due),
                "invoice_status": invoice.status,
            },
        )
