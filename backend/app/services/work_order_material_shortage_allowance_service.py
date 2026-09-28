"""
Business logic for work-order material shortage allowances.

A shortage allowance is an authorization record only. It does not
modify physical inventory, reservations, material requirements,
consumption, or procurement.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.work_order import WorkOrder
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_material import (
    WorkOrderMaterialRequirement,
)
from app.models.work_order_material_shortage_allowance import (
    WorkOrderMaterialShortageAllowance,
)
from app.repositories.work_order import WorkOrderRepository
from app.repositories.work_order_activity import (
    WorkOrderActivityRepository,
)
from app.repositories.work_order_material import (
    WorkOrderMaterialRepository,
)
from app.repositories.work_order_material_shortage_allowance import (
    WorkOrderMaterialShortageAllowanceRepository,
)
from app.schemas.work_order_material_shortage_allowance import (
    WorkOrderMaterialShortageAllowanceApprove,
    WorkOrderMaterialShortageAllowanceCancel,
    WorkOrderMaterialShortageAllowanceCreate,
    WorkOrderMaterialShortageAllowanceListResponse,
    WorkOrderMaterialShortageAllowanceReject,
    WorkOrderMaterialShortageAllowanceResponse,
    WorkOrderMaterialShortageAllowanceUpdate,
)


QUANTITY_QUANTIZER = Decimal("0.001")

TERMINAL_WORK_ORDER_STATUSES = {
    "completed",
    "cancelled",
}

ALLOWANCE_STATUS_DRAFT = "draft"
ALLOWANCE_STATUS_SUBMITTED = "submitted"
ALLOWANCE_STATUS_APPROVED = "approved"
ALLOWANCE_STATUS_REJECTED = "rejected"
ALLOWANCE_STATUS_CANCELLED = "cancelled"


class WorkOrderMaterialShortageAllowanceService:
    """
    Manage authorization to proceed despite a material shortage.

    Allowances never change physical inventory readiness. The live
    shortage returned by this service is always calculated from the
    underlying material requirement, stock, and reservations.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.work_orders = WorkOrderRepository(db)
        self.allowances = (
            WorkOrderMaterialShortageAllowanceRepository(db)
        )
        self.materials = WorkOrderMaterialRepository(db)
        self.activities = WorkOrderActivityRepository(db)

    # ------------------------------------------------------------------
    # Quantity helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _quantize_quantity(
        value: Decimal,
    ) -> Decimal:
        return Decimal(value).quantize(
            QUANTITY_QUANTIZER,
            rounding=ROUND_HALF_UP,
        )

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def _get_work_order_or_404(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrder:
        work_order = self.work_orders.get_for_organization(
            organization_id=organization_id,
            work_order_id=work_order_id,
            include_inactive=include_inactive,
        )

        if work_order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work order not found.",
            )

        return work_order

    def _get_requirement_or_404(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        requirement_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> WorkOrderMaterialRequirement:
        requirement = self.materials.get_for_work_order(
            organization_id=organization_id,
            work_order_id=work_order_id,
            requirement_id=requirement_id,
            include_inactive=include_inactive,
            for_update=for_update,
        )

        if requirement is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work-order material not found.",
            )

        return requirement

    def _get_allowance_or_404(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        allowance_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> WorkOrderMaterialShortageAllowance:
        allowance = self.allowances.get_for_work_order(
            organization_id=organization_id,
            work_order_id=work_order_id,
            allowance_id=allowance_id,
            include_inactive=include_inactive,
            for_update=for_update,
        )

        if allowance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Material shortage allowance not found.",
            )

        return allowance

    # ------------------------------------------------------------------
    # Work-order guards
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_work_order_mutable(
        work_order: WorkOrder,
    ) -> None:
        if not work_order.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Material shortage allowances cannot be "
                    "changed on an inactive work order."
                ),
            )

        if work_order.status in TERMINAL_WORK_ORDER_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Material shortage allowances cannot be "
                    "changed after the work order is completed "
                    "or cancelled."
                ),
            )

    # ------------------------------------------------------------------
    # Live shortage calculation
    # ------------------------------------------------------------------

    def _live_shortage(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        requirement: WorkOrderMaterialRequirement,
    ) -> dict[str, Decimal]:
        """
        Calculate the current physical shortage.

        This intentionally mirrors the readiness calculation used by
        WorkOrderMaterialService.

        An approved allowance is NOT deducted from the shortage.
        """

        stock_totals = self.materials.get_stock_totals(
            organization_id,
            {requirement.inventory_item_id},
        )

        reservation_totals = (
            self.materials.get_work_order_reservation_totals(
                organization_id,
                work_order_id,
                {requirement.inventory_item_id},
            )
        )

        stock = stock_totals.get(
            requirement.inventory_item_id,
            {},
        )

        quantity_on_hand = self._quantize_quantity(
            Decimal(
                stock.get(
                    "quantity_on_hand",
                    0,
                )
            )
        )

        quantity_reserved = self._quantize_quantity(
            Decimal(
                stock.get(
                    "quantity_reserved",
                    0,
                )
            )
        )

        available_quantity = self._quantize_quantity(
            max(
                quantity_on_hand - quantity_reserved,
                Decimal("0"),
            )
        )

        reserved_for_work_order = self._quantize_quantity(
            reservation_totals.get(
                requirement.inventory_item_id,
                Decimal("0"),
            )
        )

        required_quantity = self._quantize_quantity(
            requirement.required_quantity
        )

        covered_quantity = self._quantize_quantity(
            min(
                required_quantity,
                available_quantity
                + reserved_for_work_order,
            )
        )

        missing_quantity = self._quantize_quantity(
            max(
                required_quantity - covered_quantity,
                Decimal("0"),
            )
        )

        return {
            "required_quantity": required_quantity,
            "quantity_on_hand": quantity_on_hand,
            "quantity_reserved": quantity_reserved,
            "available_quantity": available_quantity,
            "reserved_for_work_order": reserved_for_work_order,
            "covered_quantity": covered_quantity,
            "missing_quantity": missing_quantity,
        }

    def _ensure_current_shortage(
        self,
        shortage: dict[str, Decimal],
    ) -> Decimal:
        missing_quantity = shortage["missing_quantity"]

        if missing_quantity <= Decimal("0.000"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "There is no current material shortage "
                    "to authorize."
                ),
            )

        return missing_quantity

    def _ensure_requested_quantity_within_shortage(
        self,
        requested_quantity: Decimal,
        shortage: dict[str, Decimal],
    ) -> Decimal:
        requested_quantity = self._quantize_quantity(
            requested_quantity
        )

        missing_quantity = self._ensure_current_shortage(
            shortage
        )

        if requested_quantity > missing_quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The requested allowance quantity exceeds "
                    "the current material shortage. "
                    f"Current shortage: {missing_quantity}."
                ),
            )

        return requested_quantity

    # ------------------------------------------------------------------
    # Activity
    # ------------------------------------------------------------------

    def _record_activity(
        self,
        *,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        summary: str,
        operation: str,
        allowance: WorkOrderMaterialShortageAllowance,
        from_status: str | None = None,
        to_status: str | None = None,
        note: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "operation": operation,
            "allowance_id": str(allowance.id),
            "material_requirement_id": str(
                allowance.work_order_material_requirement_id
            ),
            "requested_quantity": str(
                allowance.requested_quantity
            ),
            "approved_quantity": str(
                allowance.approved_quantity
            ),
            "status": allowance.status,
        }

        if details:
            payload.update(details)

        self.activities.create_activity(
            WorkOrderActivity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                activity_type=operation,
                summary=summary,
                from_status=from_status,
                to_status=to_status,
                note=note,
                details=payload,
            )
        )

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_response(
        allowance: WorkOrderMaterialShortageAllowance,
        *,
        current_missing_quantity: Decimal,
    ) -> WorkOrderMaterialShortageAllowanceResponse:
        requirement = allowance.work_order_material_requirement

        return WorkOrderMaterialShortageAllowanceResponse(
            id=allowance.id,
            organization_id=allowance.organization_id,
            work_order_id=allowance.work_order_id,
            work_order_material_requirement_id=(
                allowance.work_order_material_requirement_id
            ),
            inventory_item_id=requirement.inventory_item_id,
            required_quantity=(
                Decimal(requirement.required_quantity).quantize(
                    QUANTITY_QUANTIZER,
                    rounding=ROUND_HALF_UP,
                )
            ),
            current_missing_quantity=(
                current_missing_quantity.quantize(
                    QUANTITY_QUANTIZER,
                    rounding=ROUND_HALF_UP,
                )
            ),
            requested_quantity=(
                Decimal(allowance.requested_quantity).quantize(
                    QUANTITY_QUANTIZER,
                    rounding=ROUND_HALF_UP,
                )
            ),
            approved_quantity=(
                Decimal(allowance.approved_quantity).quantize(
                    QUANTITY_QUANTIZER,
                    rounding=ROUND_HALF_UP,
                )
            ),
            status=allowance.status,
            reason=allowance.reason,
            notes=allowance.notes,
            created_by_user_id=allowance.created_by_user_id,
            submitted_by_user_id=allowance.submitted_by_user_id,
            approved_by_user_id=allowance.approved_by_user_id,
            rejected_by_user_id=allowance.rejected_by_user_id,
            cancelled_by_user_id=allowance.cancelled_by_user_id,
            submitted_at=allowance.submitted_at,
            approved_at=allowance.approved_at,
            rejected_at=allowance.rejected_at,
            cancelled_at=allowance.cancelled_at,
            rejection_reason=allowance.rejection_reason,
            cancellation_reason=allowance.cancellation_reason,
            details=dict(allowance.details or {}),
            is_active=allowance.is_active,
            created_at=allowance.created_at,
            updated_at=allowance.updated_at,
        )

    def _reload_response(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        allowance_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrderMaterialShortageAllowanceResponse:
        allowance = self._get_allowance_or_404(
            organization_id,
            work_order_id,
            allowance_id,
            include_inactive=include_inactive,
        )

        requirement = self._get_requirement_or_404(
            organization_id,
            work_order_id,
            allowance.work_order_material_requirement_id,
            include_inactive=False,
        )

        shortage = self._live_shortage(
            organization_id,
            work_order_id,
            requirement,
        )

        return self._build_response(
            allowance,
            current_missing_quantity=shortage[
                "missing_quantity"
            ],
        )

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_allowance(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        requirement_id: uuid.UUID,
        payload: WorkOrderMaterialShortageAllowanceCreate,
        *,
        actor_user_id: uuid.UUID | None,
    ) -> WorkOrderMaterialShortageAllowanceResponse:
        """
        Create one draft allowance for a material requirement.
        """

        work_order = self._get_work_order_or_404(
            organization_id,
            work_order_id,
        )
        self._ensure_work_order_mutable(work_order)

        requirement = self._get_requirement_or_404(
            organization_id,
            work_order_id,
            requirement_id,
            for_update=True,
        )

        existing = self.allowances.get_for_requirement(
            organization_id=organization_id,
            work_order_id=work_order_id,
            requirement_id=requirement.id,
            include_inactive=True,
            for_update=True,
        )

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A material shortage allowance already "
                    "exists for this material requirement."
                ),
            )

        shortage = self._live_shortage(
            organization_id,
            work_order_id,
            requirement,
        )

        requested_quantity = (
            self._ensure_requested_quantity_within_shortage(
                payload.requested_quantity,
                shortage,
            )
        )

        allowance = WorkOrderMaterialShortageAllowance(
            organization_id=organization_id,
            work_order_id=work_order_id,
            work_order_material_requirement_id=requirement.id,
            requested_quantity=requested_quantity,
            approved_quantity=Decimal("0.000"),
            status=ALLOWANCE_STATUS_DRAFT,
            reason=payload.reason,
            notes=payload.notes,
            created_by_user_id=actor_user_id,
            details=dict(payload.details),
            is_active=True,
        )

        try:
            self.allowances.create(allowance)

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                summary=(
                    "Material shortage allowance created."
                ),
                operation=(
                    "material_shortage_allowance_created"
                ),
                allowance=allowance,
                to_status=ALLOWANCE_STATUS_DRAFT,
                note=payload.reason,
                details={
                    "current_missing_quantity": str(
                        shortage["missing_quantity"]
                    ),
                },
            )

            self.db.commit()

        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A material shortage allowance already "
                    "exists for this material requirement."
                ),
            ) from exc
        except SQLAlchemyError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

        return self._reload_response(
            organization_id,
            work_order_id,
            allowance.id,
        )

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_allowances(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        allowance_status: str | None = None,
        include_inactive: bool = False,
        include_inactive_work_order: bool = False,
    ) -> WorkOrderMaterialShortageAllowanceListResponse:
        """
        List allowances for a work order.

        current_missing_quantity is recalculated from live physical
        readiness for every returned allowance.
        """

        self._get_work_order_or_404(
            organization_id,
            work_order_id,
            include_inactive=include_inactive_work_order,
        )

        allowances = self.allowances.list_for_work_order(
            organization_id,
            work_order_id,
            skip=skip,
            limit=limit,
            allowance_status=allowance_status,
            include_inactive=include_inactive,
        )

        total = self.allowances.count_for_work_order(
            organization_id,
            work_order_id,
            allowance_status=allowance_status,
            include_inactive=include_inactive,
        )

        items: list[
            WorkOrderMaterialShortageAllowanceResponse
        ] = []

        for allowance in allowances:
            requirement = (
                allowance.work_order_material_requirement
            )

            shortage = self._live_shortage(
                organization_id,
                work_order_id,
                requirement,
            )

            items.append(
                self._build_response(
                    allowance,
                    current_missing_quantity=shortage[
                        "missing_quantity"
                    ],
                )
            )

        return WorkOrderMaterialShortageAllowanceListResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )

    # ------------------------------------------------------------------
    # Get
    # ------------------------------------------------------------------

    def get_allowance(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        allowance_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        include_inactive_work_order: bool = False,
    ) -> WorkOrderMaterialShortageAllowanceResponse:
        self._get_work_order_or_404(
            organization_id,
            work_order_id,
            include_inactive=include_inactive_work_order,
        )

        return self._reload_response(
            organization_id,
            work_order_id,
            allowance_id,
            include_inactive=include_inactive,
        )

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_allowance(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        allowance_id: uuid.UUID,
        payload: WorkOrderMaterialShortageAllowanceUpdate,
        *,
        actor_user_id: uuid.UUID | None,
    ) -> WorkOrderMaterialShortageAllowanceResponse:
        """
        Update a draft or rejected allowance.

        A rejected allowance returns to draft when edited. Rejection
        metadata is cleared and it must be submitted again.
        """

        work_order = self._get_work_order_or_404(
            organization_id,
            work_order_id,
        )
        self._ensure_work_order_mutable(work_order)

        allowance = self._get_allowance_or_404(
            organization_id,
            work_order_id,
            allowance_id,
            for_update=True,
        )

        if allowance.status not in {
            ALLOWANCE_STATUS_DRAFT,
            ALLOWANCE_STATUS_REJECTED,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only draft or rejected material shortage "
                    "allowances can be updated."
                ),
            )

        requirement = self._get_requirement_or_404(
            organization_id,
            work_order_id,
            allowance.work_order_material_requirement_id,
            for_update=True,
        )

        changes = payload.model_dump(
            exclude_unset=True
        )

        requested_quantity = (
            allowance.requested_quantity
        )

        if "requested_quantity" in changes:
            requested_quantity = changes[
                "requested_quantity"
            ]

        shortage = self._live_shortage(
            organization_id,
            work_order_id,
            requirement,
        )

        requested_quantity = (
            self._ensure_requested_quantity_within_shortage(
                requested_quantity,
                shortage,
            )
        )

        previous_status = allowance.status

        allowance.requested_quantity = requested_quantity

        if "reason" in changes:
            allowance.reason = changes["reason"]

        if "notes" in changes:
            allowance.notes = changes["notes"]

        if "details" in changes:
            allowance.details = (
                changes["details"]
                if changes["details"] is not None
                else {}
            )

        if previous_status == ALLOWANCE_STATUS_REJECTED:
            allowance.status = ALLOWANCE_STATUS_DRAFT
            allowance.approved_quantity = Decimal(
                "0.000"
            )
            allowance.rejected_by_user_id = None
            allowance.rejected_at = None
            allowance.rejection_reason = None

        try:
            self.allowances.update(allowance)

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                summary=(
                    "Material shortage allowance updated."
                ),
                operation=(
                    "material_shortage_allowance_updated"
                ),
                allowance=allowance,
                from_status=previous_status,
                to_status=allowance.status,
                details={
                    "changed_fields": sorted(changes),
                    "current_missing_quantity": str(
                        shortage["missing_quantity"]
                    ),
                },
            )

            self.db.commit()

        except SQLAlchemyError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

        return self._reload_response(
            organization_id,
            work_order_id,
            allowance.id,
        )

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def submit_allowance(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        allowance_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None,
    ) -> WorkOrderMaterialShortageAllowanceResponse:
        """
        Submit a draft allowance for approval.

        The live shortage is checked again at submission time.
        """

        work_order = self._get_work_order_or_404(
            organization_id,
            work_order_id,
        )
        self._ensure_work_order_mutable(work_order)

        allowance = self._get_allowance_or_404(
            organization_id,
            work_order_id,
            allowance_id,
            for_update=True,
        )

        if allowance.status != ALLOWANCE_STATUS_DRAFT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only draft material shortage allowances "
                    "can be submitted."
                ),
            )

        requirement = self._get_requirement_or_404(
            organization_id,
            work_order_id,
            allowance.work_order_material_requirement_id,
            for_update=True,
        )

        shortage = self._live_shortage(
            organization_id,
            work_order_id,
            requirement,
        )

        self._ensure_requested_quantity_within_shortage(
            allowance.requested_quantity,
            shortage,
        )

        previous_status = allowance.status
        now = datetime.now(UTC)

        allowance.status = ALLOWANCE_STATUS_SUBMITTED
        allowance.submitted_by_user_id = actor_user_id
        allowance.submitted_at = now

        allowance.rejected_by_user_id = None
        allowance.rejected_at = None
        allowance.rejection_reason = None

        try:
            self.allowances.update(allowance)

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                summary=(
                    "Material shortage allowance submitted "
                    "for approval."
                ),
                operation=(
                    "material_shortage_allowance_submitted"
                ),
                allowance=allowance,
                from_status=previous_status,
                to_status=ALLOWANCE_STATUS_SUBMITTED,
                details={
                    "current_missing_quantity": str(
                        shortage["missing_quantity"]
                    ),
                },
            )

            self.db.commit()

        except SQLAlchemyError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

        return self._reload_response(
            organization_id,
            work_order_id,
            allowance.id,
        )

    # ------------------------------------------------------------------
    # Approve
    # ------------------------------------------------------------------

    def approve_allowance(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        allowance_id: uuid.UUID,
        payload: WorkOrderMaterialShortageAllowanceApprove,
        *,
        actor_user_id: uuid.UUID | None,
    ) -> WorkOrderMaterialShortageAllowanceResponse:
        """
        Approve a submitted allowance.

        Approval re-checks the live shortage while the allowance and
        requirement are locked. No inventory or reservation state is
        changed.
        """

        work_order = self._get_work_order_or_404(
            organization_id,
            work_order_id,
        )
        self._ensure_work_order_mutable(work_order)

        allowance = self._get_allowance_or_404(
            organization_id,
            work_order_id,
            allowance_id,
            for_update=True,
        )

        if allowance.status != ALLOWANCE_STATUS_SUBMITTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only submitted material shortage "
                    "allowances can be approved."
                ),
            )

        requirement = self._get_requirement_or_404(
            organization_id,
            work_order_id,
            allowance.work_order_material_requirement_id,
            for_update=True,
        )

        shortage = self._live_shortage(
            organization_id,
            work_order_id,
            requirement,
        )

        current_missing_quantity = (
            self._ensure_current_shortage(shortage)
        )

        requested_quantity = self._quantize_quantity(
            allowance.requested_quantity
        )

        approved_quantity = self._quantize_quantity(
            payload.approved_quantity
        )

        if approved_quantity > requested_quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Approved quantity cannot exceed the "
                    "requested allowance quantity."
                ),
            )

        if approved_quantity > current_missing_quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The approved allowance quantity exceeds "
                    "the current material shortage. "
                    f"Current shortage: "
                    f"{current_missing_quantity}."
                ),
            )

        previous_status = allowance.status
        now = datetime.now(UTC)

        allowance.approved_quantity = approved_quantity
        allowance.status = ALLOWANCE_STATUS_APPROVED
        allowance.approved_by_user_id = actor_user_id
        allowance.approved_at = now

        try:
            self.allowances.update(allowance)

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                summary=(
                    "Material shortage allowance approved."
                ),
                operation=(
                    "material_shortage_allowance_approved"
                ),
                allowance=allowance,
                from_status=previous_status,
                to_status=ALLOWANCE_STATUS_APPROVED,
                details={
                    "approved_quantity": str(
                        approved_quantity
                    ),
                    "current_missing_quantity": str(
                        current_missing_quantity
                    ),
                },
            )

            self.db.commit()

        except SQLAlchemyError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

        return self._reload_response(
            organization_id,
            work_order_id,
            allowance.id,
        )

    # ------------------------------------------------------------------
    # Reject
    # ------------------------------------------------------------------

    def reject_allowance(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        allowance_id: uuid.UUID,
        payload: WorkOrderMaterialShortageAllowanceReject,
        *,
        actor_user_id: uuid.UUID | None,
    ) -> WorkOrderMaterialShortageAllowanceResponse:
        """
        Reject a submitted allowance.

        A rejected allowance remains editable and can later return to
        draft through the update workflow.
        """

        work_order = self._get_work_order_or_404(
            organization_id,
            work_order_id,
        )
        self._ensure_work_order_mutable(work_order)

        allowance = self._get_allowance_or_404(
            organization_id,
            work_order_id,
            allowance_id,
            for_update=True,
        )

        if allowance.status != ALLOWANCE_STATUS_SUBMITTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only submitted material shortage "
                    "allowances can be rejected."
                ),
            )

        previous_status = allowance.status
        now = datetime.now(UTC)

        allowance.status = ALLOWANCE_STATUS_REJECTED
        allowance.rejected_by_user_id = actor_user_id
        allowance.rejected_at = now
        allowance.rejection_reason = (
            payload.rejection_reason
        )
        allowance.approved_quantity = Decimal(
            "0.000"
        )

        try:
            self.allowances.update(allowance)

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                summary=(
                    "Material shortage allowance rejected."
                ),
                operation=(
                    "material_shortage_allowance_rejected"
                ),
                allowance=allowance,
                from_status=previous_status,
                to_status=ALLOWANCE_STATUS_REJECTED,
                note=payload.rejection_reason,
                details={
                    "rejection_reason": (
                        payload.rejection_reason
                    ),
                },
            )

            self.db.commit()

        except SQLAlchemyError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

        return self._reload_response(
            organization_id,
            work_order_id,
            allowance.id,
        )

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def cancel_allowance(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        allowance_id: uuid.UUID,
        payload: WorkOrderMaterialShortageAllowanceCancel,
        *,
        actor_user_id: uuid.UUID | None,
    ) -> WorkOrderMaterialShortageAllowanceResponse:
        """
        Cancel or revoke an allowance.

        Draft, submitted, and approved allowances may be cancelled.
        Cancellation is terminal and makes the allowance inactive.
        """

        work_order = self._get_work_order_or_404(
            organization_id,
            work_order_id,
        )
        self._ensure_work_order_mutable(work_order)

        allowance = self._get_allowance_or_404(
            organization_id,
            work_order_id,
            allowance_id,
            for_update=True,
        )

        if allowance.status not in {
            ALLOWANCE_STATUS_DRAFT,
            ALLOWANCE_STATUS_SUBMITTED,
            ALLOWANCE_STATUS_APPROVED,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only draft, submitted, or approved "
                    "material shortage allowances can be "
                    "cancelled."
                ),
            )

        previous_status = allowance.status
        now = datetime.now(UTC)

        allowance.status = ALLOWANCE_STATUS_CANCELLED
        allowance.is_active = False
        allowance.cancelled_by_user_id = actor_user_id
        allowance.cancelled_at = now
        allowance.cancellation_reason = (
            payload.cancellation_reason
        )

        try:
            self.allowances.update(allowance)

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                summary=(
                    "Material shortage allowance cancelled."
                ),
                operation=(
                    "material_shortage_allowance_cancelled"
                ),
                allowance=allowance,
                from_status=previous_status,
                to_status=ALLOWANCE_STATUS_CANCELLED,
                note=payload.cancellation_reason,
                details={
                    "cancellation_reason": (
                        payload.cancellation_reason
                    ),
                },
            )

            self.db.commit()

        except SQLAlchemyError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

        return self._reload_response(
            organization_id,
            work_order_id,
            allowance.id,
            include_inactive=True,
        )