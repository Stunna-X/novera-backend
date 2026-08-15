"""
Purchase requisition business logic.

Workflow changes, line-item mutations, totals, and immutable audit
records are committed atomically.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.inventory import InventoryItem, InventoryLocation
from app.models.purchase_requisition import (
    PurchaseRequisition,
    PurchaseRequisitionLineItem,
)
from app.models.supplier import Supplier
from app.models.work_order import WorkOrder
from app.repositories.purchase_requisition import (
    PurchaseRequisitionRepository,
)
from app.schemas.audit_log import AuditLogCreate
from app.schemas.purchase_requisition import (
    CancelPurchaseRequisitionSchema,
    CreatePurchaseRequisitionSchema,
    PurchaseRequisitionLineCreate,
    PurchaseRequisitionLineUpdate,
    PurchaseRequisitionListResponse,
    RejectPurchaseRequisitionSchema,
    UpdatePurchaseRequisitionSchema,
)
from app.services.audit_log_service import AuditLogService


EDITABLE_STATUSES = {"draft", "rejected"}
CANCELLABLE_STATUSES = {
    "draft",
    "submitted",
    "approved",
    "rejected",
}


class PurchaseRequisitionService:
    """Handle organization-scoped purchase requisitions."""

    def __init__(self, db: Session):
        self.db = db
        self.requisitions = PurchaseRequisitionRepository(db)
        self.audit_logs = AuditLogService(db)

    def _get_or_404(
        self,
        organization_id: uuid.UUID,
        requisition_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> PurchaseRequisition:
        requisition = self.requisitions.get_for_organization(
            organization_id,
            requisition_id,
            include_inactive=include_inactive,
            for_update=for_update,
        )

        if requisition is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase requisition not found.",
            )

        return requisition

    def _get_line_or_404(
        self,
        organization_id: uuid.UUID,
        requisition_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> PurchaseRequisitionLineItem:
        line_item = self.requisitions.get_line_item(
            organization_id,
            requisition_id,
            line_item_id,
            for_update=for_update,
        )

        if line_item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase requisition line item not found.",
            )

        return line_item

    @staticmethod
    def _ensure_editable(
        requisition: PurchaseRequisition,
    ) -> None:
        if requisition.status not in EDITABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only draft or rejected purchase requisitions "
                    "can be edited."
                ),
            )

    def _validate_supplier(
        self,
        organization_id: uuid.UUID,
        supplier_id: uuid.UUID | None,
    ) -> None:
        if supplier_id is None:
            return

        exists = (
            self.db.query(Supplier.id)
            .filter(
                Supplier.id == supplier_id,
                Supplier.organization_id == organization_id,
                Supplier.is_active.is_(True),
            )
            .first()
        )

        if exists is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Preferred supplier not found.",
            )

    def _validate_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID | None,
    ) -> None:
        if work_order_id is None:
            return

        exists = (
            self.db.query(WorkOrder.id)
            .filter(
                WorkOrder.id == work_order_id,
                WorkOrder.organization_id == organization_id,
                WorkOrder.is_active.is_(True),
            )
            .first()
        )

        if exists is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work order not found.",
            )

    def _validate_location(
        self,
        organization_id: uuid.UUID,
        location_id: uuid.UUID | None,
    ) -> None:
        if location_id is None:
            return

        exists = (
            self.db.query(InventoryLocation.id)
            .filter(
                InventoryLocation.id == location_id,
                InventoryLocation.organization_id
                == organization_id,
                InventoryLocation.is_active.is_(True),
            )
            .first()
        )

        if exists is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inventory delivery location not found.",
            )

    def _validate_inventory_item(
        self,
        organization_id: uuid.UUID,
        item_id: uuid.UUID | None,
    ) -> None:
        if item_id is None:
            return

        exists = (
            self.db.query(InventoryItem.id)
            .filter(
                InventoryItem.id == item_id,
                InventoryItem.organization_id == organization_id,
                InventoryItem.is_active.is_(True),
            )
            .first()
        )

        if exists is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inventory item not found.",
            )

    def _validate_header_references(
        self,
        organization_id: uuid.UUID,
        *,
        preferred_supplier_id: uuid.UUID | None,
        work_order_id: uuid.UUID | None,
        delivery_location_id: uuid.UUID | None,
    ) -> None:
        self._validate_supplier(
            organization_id,
            preferred_supplier_id,
        )
        self._validate_work_order(
            organization_id,
            work_order_id,
        )
        self._validate_location(
            organization_id,
            delivery_location_id,
        )

    def _validate_line_references(
        self,
        organization_id: uuid.UUID,
        *,
        inventory_item_id: uuid.UUID | None,
        preferred_supplier_id: uuid.UUID | None,
    ) -> None:
        self._validate_inventory_item(
            organization_id,
            inventory_item_id,
        )
        self._validate_supplier(
            organization_id,
            preferred_supplier_id,
        )

    @staticmethod
    def _line_total(
        quantity: Decimal,
        unit_cost: Decimal,
    ) -> Decimal:
        return (quantity * unit_cost).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _recalculate_total(
        requisition: PurchaseRequisition,
    ) -> None:
        requisition.total_estimated_amount = sum(
            (
                line.line_total
                for line in requisition.line_items
            ),
            start=Decimal("0.00"),
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, uuid.UUID):
            return str(value)

        if isinstance(value, Decimal):
            return str(value)

        if isinstance(value, (date, datetime)):
            return value.isoformat()

        if isinstance(value, dict):
            return {
                str(key): PurchaseRequisitionService._json_safe(
                    nested
                )
                for key, nested in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            return [
                PurchaseRequisitionService._json_safe(nested)
                for nested in value
            ]

        return value

    def _record_audit(
        self,
        *,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
        action: str,
        requisition: PurchaseRequisition,
        summary: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.audit_logs.record_event(
            organization_id=organization_id,
            payload=AuditLogCreate(
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action=action,
                entity_type="purchase_requisition",
                entity_id=requisition.id,
                summary=summary,
                status="success",
                details=self._json_safe(details or {}),
            ),
            commit=False,
        )

    def _rollback_conflict(
        self,
        exc: IntegrityError,
    ) -> None:
        self.db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The purchase requisition conflicts with an "
                "existing organization record."
            ),
        ) from exc

    @staticmethod
    def _generated_number() -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%d")
        suffix = uuid.uuid4().hex[:8].upper()
        return f"PR-{timestamp}-{suffix}"

    def _build_line(
        self,
        organization_id: uuid.UUID,
        payload: PurchaseRequisitionLineCreate,
        *,
        position: int,
    ) -> PurchaseRequisitionLineItem:
        data = payload.model_dump()
        self._validate_line_references(
            organization_id,
            inventory_item_id=data.get("inventory_item_id"),
            preferred_supplier_id=data.get(
                "preferred_supplier_id"
            ),
        )

        quantity = data["quantity"]
        unit_cost = data["estimated_unit_cost"]

        return PurchaseRequisitionLineItem(
            inventory_item_id=data.get("inventory_item_id"),
            preferred_supplier_id=data.get(
                "preferred_supplier_id"
            ),
            description=data["description"],
            quantity=quantity,
            unit_of_measure=data["unit_of_measure"],
            estimated_unit_cost=unit_cost,
            line_total=self._line_total(
                quantity,
                unit_cost,
            ),
            position=position,
            notes=data.get("notes"),
            details=data.get("details") or {},
        )

    def create_requisition(
        self,
        organization_id: uuid.UUID,
        payload: CreatePurchaseRequisitionSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseRequisition:
        data = payload.model_dump(exclude={"line_items"})
        line_payloads = payload.line_items
        requisition_number = (
            data.pop("requisition_number", None)
            or self._generated_number()
        )

        if self.requisitions.number_exists(
            organization_id,
            requisition_number,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another purchase requisition already uses "
                    "this number."
                ),
            )

        self._validate_header_references(
            organization_id,
            preferred_supplier_id=data.get(
                "preferred_supplier_id"
            ),
            work_order_id=data.get("work_order_id"),
            delivery_location_id=data.get(
                "delivery_location_id"
            ),
        )

        requisition = PurchaseRequisition(
            organization_id=organization_id,
            requisition_number=requisition_number,
            created_by_user_id=actor_user_id,
            **data,
        )

        used_positions: set[int] = set()
        next_position = 0

        for line_payload in line_payloads:
            position = line_payload.position

            if position is None:
                while next_position in used_positions:
                    next_position += 1
                position = next_position

            used_positions.add(position)
            next_position = max(next_position, position + 1)
            requisition.line_items.append(
                self._build_line(
                    organization_id,
                    line_payload,
                    position=position,
                )
            )

        self._recalculate_total(requisition)

        try:
            created = self.requisitions.create(requisition)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="purchase_requisition_created",
                requisition=created,
                summary="Purchase requisition created.",
                details={
                    "line_count": len(created.line_items),
                    "total_estimated_amount": (
                        created.total_estimated_amount
                    ),
                },
            )
            self.db.commit()
            self.db.refresh(created)
            return self._get_or_404(
                organization_id,
                created.id,
            )

        except IntegrityError as exc:
            self._rollback_conflict(exc)

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def list_requisitions(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        status_filter: str | None = None,
        priority: str | None = None,
        preferred_supplier_id: uuid.UUID | None = None,
        work_order_id: uuid.UUID | None = None,
        include_inactive: bool = False,
    ) -> PurchaseRequisitionListResponse:
        items = self.requisitions.list_for_organization(
            organization_id,
            skip=skip,
            limit=limit,
            search=search,
            status_filter=status_filter,
            priority=priority,
            preferred_supplier_id=preferred_supplier_id,
            work_order_id=work_order_id,
            include_inactive=include_inactive,
        )
        total = self.requisitions.count_for_organization(
            organization_id,
            search=search,
            status_filter=status_filter,
            priority=priority,
            preferred_supplier_id=preferred_supplier_id,
            work_order_id=work_order_id,
            include_inactive=include_inactive,
        )

        return PurchaseRequisitionListResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_requisition(
        self,
        organization_id: uuid.UUID,
        requisition_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> PurchaseRequisition:
        return self._get_or_404(
            organization_id,
            requisition_id,
            include_inactive=include_inactive,
        )

    def update_requisition(
        self,
        organization_id: uuid.UUID,
        requisition_id: uuid.UUID,
        payload: UpdatePurchaseRequisitionSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseRequisition:
        requisition = self._get_or_404(
            organization_id,
            requisition_id,
            for_update=True,
        )
        self._ensure_editable(requisition)
        update_data = payload.model_dump(exclude_unset=True)

        if not update_data:
            return requisition

        self._validate_header_references(
            organization_id,
            preferred_supplier_id=update_data.get(
                "preferred_supplier_id",
                requisition.preferred_supplier_id,
            ),
            work_order_id=update_data.get(
                "work_order_id",
                requisition.work_order_id,
            ),
            delivery_location_id=update_data.get(
                "delivery_location_id",
                requisition.delivery_location_id,
            ),
        )

        for field_name, value in update_data.items():
            setattr(requisition, field_name, value)

        try:
            updated = self.requisitions.update(requisition)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="purchase_requisition_updated",
                requisition=updated,
                summary="Purchase requisition updated.",
                details={
                    "changed_fields": sorted(update_data),
                },
            )
            self.db.commit()
            return self._get_or_404(
                organization_id,
                requisition_id,
            )

        except IntegrityError as exc:
            self._rollback_conflict(exc)

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def add_line_item(
        self,
        organization_id: uuid.UUID,
        requisition_id: uuid.UUID,
        payload: PurchaseRequisitionLineCreate,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseRequisition:
        requisition = self._get_or_404(
            organization_id,
            requisition_id,
            for_update=True,
        )
        self._ensure_editable(requisition)
        position = (
            payload.position
            if payload.position is not None
            else self.requisitions.next_position(requisition.id)
        )
        line_item = self._build_line(
            organization_id,
            payload,
            position=position,
        )
        line_item.requisition_id = requisition.id

        try:
            created_line = self.requisitions.add_line_item(
                line_item
            )
            requisition.line_items.append(created_line)
            self._recalculate_total(requisition)
            self.requisitions.update(requisition)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="purchase_requisition_line_added",
                requisition=requisition,
                summary="Purchase requisition line added.",
                details={
                    "line_item_id": created_line.id,
                    "position": created_line.position,
                    "line_total": created_line.line_total,
                },
            )
            self.db.commit()
            return self._get_or_404(
                organization_id,
                requisition_id,
            )

        except IntegrityError as exc:
            self._rollback_conflict(exc)

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def update_line_item(
        self,
        organization_id: uuid.UUID,
        requisition_id: uuid.UUID,
        line_item_id: uuid.UUID,
        payload: PurchaseRequisitionLineUpdate,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseRequisition:
        requisition = self._get_or_404(
            organization_id,
            requisition_id,
            for_update=True,
        )
        self._ensure_editable(requisition)
        line_item = self._get_line_or_404(
            organization_id,
            requisition_id,
            line_item_id,
            for_update=True,
        )
        update_data = payload.model_dump(exclude_unset=True)

        if not update_data:
            return requisition

        self._validate_line_references(
            organization_id,
            inventory_item_id=update_data.get(
                "inventory_item_id",
                line_item.inventory_item_id,
            ),
            preferred_supplier_id=update_data.get(
                "preferred_supplier_id",
                line_item.preferred_supplier_id,
            ),
        )

        for field_name, value in update_data.items():
            setattr(line_item, field_name, value)

        line_item.line_total = self._line_total(
            line_item.quantity,
            line_item.estimated_unit_cost,
        )

        try:
            self.requisitions.update_line_item(line_item)
            self._recalculate_total(requisition)
            self.requisitions.update(requisition)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="purchase_requisition_line_updated",
                requisition=requisition,
                summary="Purchase requisition line updated.",
                details={
                    "line_item_id": line_item.id,
                    "changed_fields": sorted(update_data),
                    "line_total": line_item.line_total,
                },
            )
            self.db.commit()
            return self._get_or_404(
                organization_id,
                requisition_id,
            )

        except IntegrityError as exc:
            self._rollback_conflict(exc)

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def delete_line_item(
        self,
        organization_id: uuid.UUID,
        requisition_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseRequisition:
        requisition = self._get_or_404(
            organization_id,
            requisition_id,
            for_update=True,
        )
        self._ensure_editable(requisition)
        line_item = self._get_line_or_404(
            organization_id,
            requisition_id,
            line_item_id,
            for_update=True,
        )
        removed_total = line_item.line_total

        try:
            requisition.line_items.remove(line_item)
            self.requisitions.delete_line_item(line_item)
            self._recalculate_total(requisition)
            self.requisitions.update(requisition)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="purchase_requisition_line_removed",
                requisition=requisition,
                summary="Purchase requisition line removed.",
                details={
                    "line_item_id": line_item_id,
                    "removed_line_total": removed_total,
                },
            )
            self.db.commit()
            return self._get_or_404(
                organization_id,
                requisition_id,
            )

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def submit_requisition(
        self,
        organization_id: uuid.UUID,
        requisition_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseRequisition:
        requisition = self._get_or_404(
            organization_id,
            requisition_id,
            for_update=True,
        )

        if requisition.status not in EDITABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only draft or rejected purchase requisitions "
                    "can be submitted."
                ),
            )

        if not requisition.line_items:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A purchase requisition must contain at least "
                    "one line item before submission."
                ),
            )

        previous_status = requisition.status
        requisition.status = "submitted"
        requisition.submitted_at = datetime.now(UTC)
        requisition.submitted_by_user_id = actor_user_id
        requisition.rejected_at = None
        requisition.rejected_by_user_id = None
        requisition.rejection_reason = None

        return self._commit_status_change(
            organization_id=organization_id,
            requisition=requisition,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            action="purchase_requisition_submitted",
            summary="Purchase requisition submitted for approval.",
            from_status=previous_status,
        )

    def approve_requisition(
        self,
        organization_id: uuid.UUID,
        requisition_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseRequisition:
        requisition = self._get_or_404(
            organization_id,
            requisition_id,
            for_update=True,
        )

        if requisition.status != "submitted":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only submitted purchase requisitions can be "
                    "approved."
                ),
            )

        requisition.status = "approved"
        requisition.approved_at = datetime.now(UTC)
        requisition.approved_by_user_id = actor_user_id

        return self._commit_status_change(
            organization_id=organization_id,
            requisition=requisition,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            action="purchase_requisition_approved",
            summary="Purchase requisition approved.",
            from_status="submitted",
        )

    def reject_requisition(
        self,
        organization_id: uuid.UUID,
        requisition_id: uuid.UUID,
        payload: RejectPurchaseRequisitionSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseRequisition:
        requisition = self._get_or_404(
            organization_id,
            requisition_id,
            for_update=True,
        )

        if requisition.status != "submitted":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only submitted purchase requisitions can be "
                    "rejected."
                ),
            )

        requisition.status = "rejected"
        requisition.rejected_at = datetime.now(UTC)
        requisition.rejected_by_user_id = actor_user_id
        requisition.rejection_reason = payload.reason

        return self._commit_status_change(
            organization_id=organization_id,
            requisition=requisition,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            action="purchase_requisition_rejected",
            summary="Purchase requisition rejected.",
            from_status="submitted",
            details={"reason": payload.reason},
        )

    def cancel_requisition(
        self,
        organization_id: uuid.UUID,
        requisition_id: uuid.UUID,
        payload: CancelPurchaseRequisitionSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseRequisition:
        requisition = self._get_or_404(
            organization_id,
            requisition_id,
            for_update=True,
        )

        if requisition.status not in CANCELLABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This purchase requisition cannot be cancelled "
                    "in its current status."
                ),
            )

        previous_status = requisition.status
        requisition.status = "cancelled"
        requisition.cancelled_at = datetime.now(UTC)
        requisition.cancelled_by_user_id = actor_user_id
        requisition.cancellation_reason = payload.reason

        return self._commit_status_change(
            organization_id=organization_id,
            requisition=requisition,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            action="purchase_requisition_cancelled",
            summary="Purchase requisition cancelled.",
            from_status=previous_status,
            details={"reason": payload.reason},
        )

    def _commit_status_change(
        self,
        *,
        organization_id: uuid.UUID,
        requisition: PurchaseRequisition,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
        action: str,
        summary: str,
        from_status: str,
        details: dict[str, Any] | None = None,
    ) -> PurchaseRequisition:
        try:
            self.requisitions.update(requisition)
            audit_details = {
                "from_status": from_status,
                "to_status": requisition.status,
            }
            audit_details.update(details or {})
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action=action,
                requisition=requisition,
                summary=summary,
                details=audit_details,
            )
            self.db.commit()
            return self._get_or_404(
                organization_id,
                requisition.id,
            )

        except IntegrityError as exc:
            self._rollback_conflict(exc)

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise
