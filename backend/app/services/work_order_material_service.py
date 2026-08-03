"""
Business logic for work-order material readiness.
"""

from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.inventory import InventoryItem
from app.models.work_order import WorkOrder
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_material import (
    WorkOrderMaterialRequirement,
)
from app.repositories.work_order import WorkOrderRepository
from app.repositories.work_order_activity import (
    WorkOrderActivityRepository,
)
from app.repositories.work_order_material import (
    WorkOrderMaterialRepository,
)
from app.schemas.work_order_material import (
    WorkOrderMaterialCreate,
    WorkOrderMaterialItemSummary,
    WorkOrderMaterialListResponse,
    WorkOrderMaterialResponse,
    WorkOrderMaterialUpdate,
)


QUANTITY_QUANTIZER = Decimal("0.001")
COST_QUANTIZER = Decimal("0.01")
PERCENT_QUANTIZER = Decimal("0.01")

TERMINAL_WORK_ORDER_STATUSES = {
    "completed",
    "cancelled",
}


class WorkOrderMaterialService:
    """Manage planned job materials and calculate live coverage."""

    def __init__(self, db: Session):
        self.db = db
        self.work_orders = WorkOrderRepository(db)
        self.materials = WorkOrderMaterialRepository(db)
        self.activities = WorkOrderActivityRepository(db)

    @staticmethod
    def _quantize_quantity(value: Decimal) -> Decimal:
        return Decimal(value).quantize(
            QUANTITY_QUANTIZER,
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _quantize_cost(value: Decimal) -> Decimal:
        return Decimal(value).quantize(
            COST_QUANTIZER,
            rounding=ROUND_HALF_UP,
        )

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

    def _get_inventory_item_or_404(
        self,
        organization_id: uuid.UUID,
        inventory_item_id: uuid.UUID,
    ) -> InventoryItem:
        item = (
            self.db.query(InventoryItem)
            .filter(
                InventoryItem.id == inventory_item_id,
                InventoryItem.organization_id
                == organization_id,
                InventoryItem.is_active.is_(True),
            )
            .first()
        )

        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inventory item not found.",
            )

        return item

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

    @staticmethod
    def _ensure_work_order_mutable(
        work_order: WorkOrder,
    ) -> None:
        if not work_order.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Materials cannot be changed on an "
                    "inactive work order."
                ),
            )

        if work_order.status in TERMINAL_WORK_ORDER_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Materials cannot be changed after the "
                    "work order is completed or cancelled."
                ),
            )

    def _record_activity(
        self,
        *,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        summary: str,
        operation: str,
        requirement: WorkOrderMaterialRequirement,
        details: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "operation": operation,
            "material_requirement_id": str(requirement.id),
            "inventory_item_id": str(
                requirement.inventory_item_id
            ),
            "required_quantity": str(
                requirement.required_quantity
            ),
        }

        if details:
            payload.update(details)

        self.activities.create_activity(
            WorkOrderActivity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                activity_type="updated",
                summary=summary,
                details=payload,
            )
        )

    def _stock_context(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        requirements: list[WorkOrderMaterialRequirement],
    ) -> tuple[
        dict[uuid.UUID, dict[str, Decimal | int]],
        dict[uuid.UUID, Decimal],
    ]:
        item_ids = {
            requirement.inventory_item_id
            for requirement in requirements
        }

        return (
            self.materials.get_stock_totals(
                organization_id,
                item_ids,
            ),
            self.materials.get_work_order_reservation_totals(
                organization_id,
                work_order_id,
                item_ids,
            ),
        )

    def _build_response(
        self,
        requirement: WorkOrderMaterialRequirement,
        *,
        stock_totals: dict[
            uuid.UUID,
            dict[str, Decimal | int],
        ],
        reservation_totals: dict[uuid.UUID, Decimal],
    ) -> WorkOrderMaterialResponse:
        stock = stock_totals.get(
            requirement.inventory_item_id,
            {},
        )

        quantity_on_hand = self._quantize_quantity(
            Decimal(stock.get("quantity_on_hand", 0))
        )
        quantity_reserved = self._quantize_quantity(
            Decimal(stock.get("quantity_reserved", 0))
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

        if missing_quantity == Decimal("0.000"):
            readiness_status = "available"
        elif covered_quantity > Decimal("0.000"):
            readiness_status = "partial"
        else:
            readiness_status = "missing"

        coverage_percentage = (
            covered_quantity
            / required_quantity
            * Decimal("100")
        ).quantize(
            PERCENT_QUANTIZER,
            rounding=ROUND_HALF_UP,
        )

        item = requirement.inventory_item
        estimated_unit_cost = Decimal(
            item.default_unit_cost
        )
        estimated_line_cost = self._quantize_cost(
            required_quantity * estimated_unit_cost
        )

        return WorkOrderMaterialResponse(
            id=requirement.id,
            organization_id=requirement.organization_id,
            work_order_id=requirement.work_order_id,
            inventory_item_id=requirement.inventory_item_id,
            required_quantity=required_quantity,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=quantity_reserved,
            available_quantity=available_quantity,
            reserved_for_work_order=(
                reserved_for_work_order
            ),
            covered_quantity=covered_quantity,
            missing_quantity=missing_quantity,
            coverage_percentage=coverage_percentage,
            readiness_status=readiness_status,
            active_location_count=int(
                stock.get("active_location_count", 0)
            ),
            estimated_unit_cost=estimated_unit_cost,
            estimated_line_cost=estimated_line_cost,
            currency=item.currency,
            notes=requirement.notes,
            position=requirement.position,
            details=requirement.details,
            is_active=requirement.is_active,
            created_by_user_id=(
                requirement.created_by_user_id
            ),
            updated_by_user_id=(
                requirement.updated_by_user_id
            ),
            item=WorkOrderMaterialItemSummary.model_validate(
                item
            ),
            created_at=requirement.created_at,
            updated_at=requirement.updated_at,
        )

    def _reload_response(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        requirement_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrderMaterialResponse:
        requirement = self._get_requirement_or_404(
            organization_id,
            work_order_id,
            requirement_id,
            include_inactive=include_inactive,
        )
        stock_totals, reservation_totals = (
            self._stock_context(
                organization_id,
                work_order_id,
                [requirement],
            )
        )

        return self._build_response(
            requirement,
            stock_totals=stock_totals,
            reservation_totals=reservation_totals,
        )

    def create_requirement(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        payload: WorkOrderMaterialCreate,
        *,
        actor_user_id: uuid.UUID | None,
    ) -> WorkOrderMaterialResponse:
        work_order = self._get_work_order_or_404(
            organization_id,
            work_order_id,
        )
        self._ensure_work_order_mutable(work_order)
        item = self._get_inventory_item_or_404(
            organization_id,
            payload.inventory_item_id,
        )

        existing = self.materials.get_by_item(
            organization_id,
            work_order_id,
            payload.inventory_item_id,
            include_inactive=True,
            for_update=True,
        )

        if existing is not None and existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This inventory item is already included "
                    "in the work-order materials."
                ),
            )

        position = payload.position

        if position is None:
            position = self.materials.get_next_position(
                organization_id,
                work_order_id,
            )

        if existing is None:
            requirement = WorkOrderMaterialRequirement(
                organization_id=organization_id,
                work_order_id=work_order_id,
                inventory_item_id=item.id,
                required_quantity=payload.required_quantity,
                notes=payload.notes,
                position=position,
                details=payload.details,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
                is_active=True,
            )
            operation = "material_requirement_created"
            summary = "Material requirement added."
        else:
            requirement = existing
            requirement.required_quantity = (
                payload.required_quantity
            )
            requirement.notes = payload.notes
            requirement.position = position
            requirement.details = payload.details
            requirement.updated_by_user_id = actor_user_id
            requirement.is_active = True
            operation = "material_requirement_reactivated"
            summary = "Material requirement restored."

        try:
            if existing is None:
                self.materials.create(requirement)
            else:
                self.materials.update(requirement)

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                summary=summary,
                operation=operation,
                requirement=requirement,
            )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The material requirement conflicts with "
                    "an existing work-order material."
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
            requirement.id,
        )

    def list_requirements(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        include_inactive: bool = False,
        include_inactive_work_order: bool = False,
    ) -> WorkOrderMaterialListResponse:
        self._get_work_order_or_404(
            organization_id,
            work_order_id,
            include_inactive=include_inactive_work_order,
        )

        requirements = self.materials.list_for_work_order(
            organization_id,
            work_order_id,
            skip=skip,
            limit=limit,
            include_inactive=include_inactive,
        )
        total = self.materials.count_for_work_order(
            organization_id,
            work_order_id,
            include_inactive=include_inactive,
        )
        stock_totals, reservation_totals = (
            self._stock_context(
                organization_id,
                work_order_id,
                requirements,
            )
        )
        items = [
            self._build_response(
                requirement,
                stock_totals=stock_totals,
                reservation_totals=reservation_totals,
            )
            for requirement in requirements
        ]

        available_lines = sum(
            item.readiness_status == "available"
            for item in items
        )
        partial_lines = sum(
            item.readiness_status == "partial"
            for item in items
        )
        missing_lines = sum(
            item.readiness_status == "missing"
            for item in items
        )
        total_estimated_cost = self._quantize_cost(
            sum(
                (
                    item.estimated_line_cost
                    for item in items
                ),
                Decimal("0"),
            )
        )

        return WorkOrderMaterialListResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
            available_lines=available_lines,
            partial_lines=partial_lines,
            missing_lines=missing_lines,
            all_materials_ready=(
                total > 0
                and partial_lines == 0
                and missing_lines == 0
            ),
            total_estimated_cost=total_estimated_cost,
        )

    def get_requirement(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        requirement_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        include_inactive_work_order: bool = False,
    ) -> WorkOrderMaterialResponse:
        self._get_work_order_or_404(
            organization_id,
            work_order_id,
            include_inactive=include_inactive_work_order,
        )

        return self._reload_response(
            organization_id,
            work_order_id,
            requirement_id,
            include_inactive=include_inactive,
        )

    def update_requirement(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        requirement_id: uuid.UUID,
        payload: WorkOrderMaterialUpdate,
        *,
        actor_user_id: uuid.UUID | None,
    ) -> WorkOrderMaterialResponse:
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

        changes = payload.model_dump(exclude_unset=True)

        if "required_quantity" in changes:
            requirement.required_quantity = changes[
                "required_quantity"
            ]

        if "notes" in changes:
            requirement.notes = changes["notes"]

        if "position" in changes:
            requirement.position = changes["position"]

        if "details" in changes:
            requirement.details = changes["details"] or {}

        requirement.updated_by_user_id = actor_user_id

        try:
            self.materials.update(requirement)
            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                summary="Material requirement updated.",
                operation="material_requirement_updated",
                requirement=requirement,
                details={
                    "changed_fields": sorted(changes),
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
            requirement.id,
        )

    def deactivate_requirement(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        requirement_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None,
    ) -> None:
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
        requirement.is_active = False
        requirement.updated_by_user_id = actor_user_id

        try:
            self.materials.update(requirement)
            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                summary="Material requirement removed.",
                operation="material_requirement_deactivated",
                requirement=requirement,
            )
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

    def reactivate_requirement(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        requirement_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None,
    ) -> WorkOrderMaterialResponse:
        work_order = self._get_work_order_or_404(
            organization_id,
            work_order_id,
        )
        self._ensure_work_order_mutable(work_order)
        requirement = self._get_requirement_or_404(
            organization_id,
            work_order_id,
            requirement_id,
            include_inactive=True,
            for_update=True,
        )
        self._get_inventory_item_or_404(
            organization_id,
            requirement.inventory_item_id,
        )

        if not requirement.is_active:
            requirement.is_active = True
            requirement.updated_by_user_id = actor_user_id

            try:
                self.materials.update(requirement)
                self._record_activity(
                    organization_id=organization_id,
                    work_order_id=work_order_id,
                    actor_user_id=actor_user_id,
                    summary="Material requirement restored.",
                    operation=(
                        "material_requirement_reactivated"
                    ),
                    requirement=requirement,
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
            requirement.id,
        )
