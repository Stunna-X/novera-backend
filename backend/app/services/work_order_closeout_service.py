"""Work-order closeout service.

Handles closeout report submission, customer sign-off,
invoice-readiness, and audit trail recording.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.work_order import WorkOrder
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_closeout import WorkOrderCloseout
from app.repositories.work_order import WorkOrderRepository
from app.repositories.work_order_activity import (
    WorkOrderActivityRepository,
)
from app.repositories.work_order_closeout import (
    WorkOrderCloseoutRepository,
)
from app.services.auto_notification_service import AutoNotificationService
from app.schemas.work_order_closeout import (
    ApproveWorkOrderCloseoutSchema,
    MarkCloseoutInvoiceReadySchema,
    RejectWorkOrderCloseoutSchema,
    SubmitWorkOrderCloseoutSchema,
    UpdateWorkOrderCloseoutSchema,
    WorkOrderCloseoutResponse,
)


class WorkOrderCloseoutService:
    """Business logic for work-order closeouts."""

    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.work_orders = WorkOrderRepository(db)
        self.closeouts = WorkOrderCloseoutRepository(db)
        self.activities = WorkOrderActivityRepository(db)
        self.auto_notifications = AutoNotificationService(db)

    @staticmethod
    def _now() -> datetime:
        """Return a timezone-aware UTC timestamp."""

        return datetime.now(UTC)

    @staticmethod
    def _build_response(
        closeout: WorkOrderCloseout,
    ) -> WorkOrderCloseoutResponse:
        """Convert a closeout model into an API response."""

        return WorkOrderCloseoutResponse(
            id=closeout.id,
            organization_id=closeout.organization_id,
            work_order_id=closeout.work_order_id,
            created_by_user_id=closeout.created_by_user_id,
            submitted_by_user_id=(
                closeout.submitted_by_user_id
            ),
            approved_by_user_id=(
                closeout.approved_by_user_id
            ),
            rejected_by_user_id=(
                closeout.rejected_by_user_id
            ),
            invoice_ready_by_user_id=(
                closeout.invoice_ready_by_user_id
            ),
            status=closeout.status,
            completion_summary=closeout.completion_summary,
            work_performed=closeout.work_performed,
            materials_used=closeout.materials_used,
            customer_notes=closeout.customer_notes,
            internal_notes=closeout.internal_notes,
            customer_name=closeout.customer_name,
            customer_email=closeout.customer_email,
            customer_phone=closeout.customer_phone,
            customer_title=closeout.customer_title,
            customer_signature_url=(
                closeout.customer_signature_url
            ),
            customer_rating=closeout.customer_rating,
            customer_feedback=closeout.customer_feedback,
            rejection_reason=closeout.rejection_reason,
            submitted_at=closeout.submitted_at,
            approved_at=closeout.approved_at,
            rejected_at=closeout.rejected_at,
            invoice_ready_at=closeout.invoice_ready_at,
            is_invoice_ready=closeout.is_invoice_ready,
            created_at=closeout.created_at,
            updated_at=closeout.updated_at,
        )

    def _record_activity(
        self,
        *,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        activity_type: str,
        summary: str,
        from_status: str | None = None,
        to_status: str | None = None,
        note: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> WorkOrderActivity:
        """Record a work-order timeline entry."""

        activity = WorkOrderActivity(
            organization_id=organization_id,
            work_order_id=work_order_id,
            actor_user_id=actor_user_id,
            activity_type=activity_type,
            summary=summary,
            from_status=from_status,
            to_status=to_status,
            note=note,
            details=details or {},
        )

        return self.activities.create_activity(
            activity
        )

    def _get_work_order_or_404(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
    ) -> WorkOrder:
        """Retrieve a work order or raise 404."""

        work_order = self.work_orders.get_for_organization(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        if work_order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work order not found.",
            )

        return work_order

    def _get_closeout_or_404(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> WorkOrderCloseout:
        """Retrieve a closeout or raise 404."""

        closeout = self.closeouts.get_for_work_order(
            organization_id=organization_id,
            work_order_id=work_order_id,
            for_update=for_update,
        )

        if closeout is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work-order closeout not found.",
            )

        return closeout

    @staticmethod
    def _ensure_completed(
        work_order: WorkOrder,
    ) -> None:
        """Ensure a work order has been completed."""

        if work_order.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only completed work orders can be "
                    "submitted for closeout."
                ),
            )

    @staticmethod
    def _ensure_not_approved(
        closeout: WorkOrderCloseout,
    ) -> None:
        """Prevent edits after approval."""

        if closeout.status == "approved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Approved closeouts cannot be edited "
                    "or resubmitted."
                ),
            )

    def submit_closeout(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        payload: SubmitWorkOrderCloseoutSchema,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderCloseoutResponse:
        """Create or resubmit a closeout report."""

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        self._ensure_completed(
            work_order
        )

        closeout = self.closeouts.get_for_work_order(
            organization_id=organization_id,
            work_order_id=work_order_id,
            for_update=True,
        )

        closeout_data = payload.model_dump(
            exclude={"note"}
        )

        now = self._now()

        if closeout is None:
            closeout = WorkOrderCloseout(
                organization_id=organization_id,
                work_order_id=work_order_id,
                created_by_user_id=actor_user_id,
                submitted_by_user_id=actor_user_id,
                status="submitted",
                submitted_at=now,
                **closeout_data,
            )

            try:
                closeout = self.closeouts.create_closeout(
                    closeout
                )
            except IntegrityError as exc:
                self.db.rollback()

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This work order already has "
                        "a closeout record."
                    ),
                ) from exc

            from_status = None

        else:
            self._ensure_not_approved(
                closeout
            )

            from_status = closeout.status

            for field_name, field_value in closeout_data.items():
                setattr(
                    closeout,
                    field_name,
                    field_value,
                )

            closeout.status = "submitted"
            closeout.submitted_by_user_id = actor_user_id
            closeout.submitted_at = now
            closeout.rejection_reason = None
            closeout.rejected_by_user_id = None
            closeout.rejected_at = None

            closeout = self.closeouts.update_closeout(
                closeout
            )

        self._record_activity(
            organization_id=organization_id,
            work_order_id=work_order_id,
            actor_user_id=actor_user_id,
            activity_type="closeout_submitted",
            summary=(
                f"Work order {work_order.work_order_number} "
                "submitted for customer closeout."
            ),
            from_status=from_status,
            to_status="submitted",
            note=payload.note,
            details={
                "closeout_id": str(closeout.id),
                "is_invoice_ready": closeout.is_invoice_ready,
            },
        )

        return self._build_response(
            closeout
        )

    def get_closeout(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
    ) -> WorkOrderCloseoutResponse:
        """Return the closeout for a work order."""

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        closeout = self._get_closeout_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        return self._build_response(
            closeout
        )

    def update_closeout(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        payload: UpdateWorkOrderCloseoutSchema,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderCloseoutResponse:
        """Update a submitted or rejected closeout."""

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        closeout = self._get_closeout_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            for_update=True,
        )

        self._ensure_not_approved(
            closeout
        )

        update_data = payload.model_dump(
            exclude_unset=True,
            exclude={"note"},
        )

        if not update_data:
            return self._build_response(
                closeout
            )

        for field_name, field_value in update_data.items():
            setattr(
                closeout,
                field_name,
                field_value,
            )

        closeout = self.closeouts.update_closeout(
            closeout
        )

        self._record_activity(
            organization_id=organization_id,
            work_order_id=work_order_id,
            actor_user_id=actor_user_id,
            activity_type="closeout_updated",
            summary=(
                f"Work order {work_order.work_order_number} "
                "closeout report updated."
            ),
            note=payload.note,
            details={
                "closeout_id": str(closeout.id),
                "changed_fields": sorted(update_data.keys()),
            },
        )

        return self._build_response(
            closeout
        )

    def approve_closeout(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        payload: ApproveWorkOrderCloseoutSchema,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderCloseoutResponse:
        """Approve a closeout and capture customer sign-off."""

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        closeout = self._get_closeout_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            for_update=True,
        )

        if closeout.status != "submitted":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only submitted closeouts can be "
                    "approved."
                ),
            )

        now = self._now()
        from_status = closeout.status

        closeout.status = "approved"
        closeout.approved_by_user_id = actor_user_id
        closeout.approved_at = now

        closeout.customer_name = payload.customer_name
        closeout.customer_email = (
            str(payload.customer_email)
            if payload.customer_email
            else None
        )
        closeout.customer_phone = payload.customer_phone
        closeout.customer_title = payload.customer_title
        closeout.customer_signature_url = (
            payload.customer_signature_url
        )
        closeout.customer_rating = payload.customer_rating
        closeout.customer_feedback = payload.customer_feedback

        closeout.rejection_reason = None
        closeout.rejected_by_user_id = None
        closeout.rejected_at = None

        if payload.ready_for_invoice:
            closeout.is_invoice_ready = True
            closeout.invoice_ready_at = now
            closeout.invoice_ready_by_user_id = actor_user_id

        closeout = self.closeouts.update_closeout(
            closeout
        )

        self._record_activity(
            organization_id=organization_id,
            work_order_id=work_order_id,
            actor_user_id=actor_user_id,
            activity_type="closeout_approved",
            summary=(
                f"Work order {work_order.work_order_number} "
                "closeout approved by customer."
            ),
            from_status=from_status,
            to_status="approved",
            note=payload.note,
            details={
                "closeout_id": str(closeout.id),
                "customer_name": closeout.customer_name,
                "customer_rating": closeout.customer_rating,
                "is_invoice_ready": closeout.is_invoice_ready,
            },
        )

        # Auto notification: closeout approved.
        self.auto_notifications.notify_closeout_approved(
            organization_id=organization_id,
            closeout=closeout,
            work_order=work_order,
            actor_user_id=actor_user_id,
        )

        if closeout.is_invoice_ready:
            self.auto_notifications.notify_closeout_invoice_ready(
                organization_id=organization_id,
                closeout=closeout,
                work_order=work_order,
                actor_user_id=actor_user_id,
            )

        self.db.commit()

        return self._build_response(
            closeout
        )

    def reject_closeout(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        payload: RejectWorkOrderCloseoutSchema,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderCloseoutResponse:
        """Reject a submitted closeout."""

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        closeout = self._get_closeout_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            for_update=True,
        )

        if closeout.status != "submitted":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only submitted closeouts can be "
                    "rejected."
                ),
            )

        now = self._now()
        from_status = closeout.status

        closeout.status = "rejected"
        closeout.rejected_by_user_id = actor_user_id
        closeout.rejected_at = now
        closeout.rejection_reason = payload.rejection_reason
        closeout.is_invoice_ready = False
        closeout.invoice_ready_at = None
        closeout.invoice_ready_by_user_id = None

        closeout = self.closeouts.update_closeout(
            closeout
        )

        self._record_activity(
            organization_id=organization_id,
            work_order_id=work_order_id,
            actor_user_id=actor_user_id,
            activity_type="closeout_rejected",
            summary=(
                f"Work order {work_order.work_order_number} "
                "closeout rejected."
            ),
            from_status=from_status,
            to_status="rejected",
            note=payload.note or payload.rejection_reason,
            details={
                "closeout_id": str(closeout.id),
                "rejection_reason": closeout.rejection_reason,
            },
        )

        return self._build_response(
            closeout
        )

    def mark_invoice_ready(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        payload: MarkCloseoutInvoiceReadySchema,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderCloseoutResponse:
        """Mark an approved closeout as ready for final invoice."""

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        closeout = self._get_closeout_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            for_update=True,
        )

        if closeout.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only approved closeouts can be marked "
                    "invoice-ready."
                ),
            )

        if closeout.is_invoice_ready:
            return self._build_response(
                closeout
            )

        now = self._now()

        closeout.is_invoice_ready = True
        closeout.invoice_ready_at = now
        closeout.invoice_ready_by_user_id = actor_user_id

        closeout = self.closeouts.update_closeout(
            closeout
        )

        self._record_activity(
            organization_id=organization_id,
            work_order_id=work_order_id,
            actor_user_id=actor_user_id,
            activity_type="closeout_invoice_ready",
            summary=(
                f"Work order {work_order.work_order_number} "
                "marked ready for final invoice."
            ),
            note=payload.note,
            details={
                "closeout_id": str(closeout.id),
                "is_invoice_ready": True,
            },
        )

        # Auto notification: closeout invoice ready.
        self.auto_notifications.notify_closeout_invoice_ready(
            organization_id=organization_id,
            closeout=closeout,
            work_order=work_order,
            actor_user_id=actor_user_id,
        )

        self.db.commit()

        return self._build_response(
            closeout
        )

