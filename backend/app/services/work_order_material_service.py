"""
Business logic for work-order material readiness.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.inventory import InventoryItem
from app.models.purchase_requisition import PurchaseRequisition
from app.models.work_order import WorkOrder
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_material import (
    WorkOrderMaterialRequirement,
)
from app.repositories.purchase_requisition import (
    PurchaseRequisitionRepository,
)
from app.repositories.work_order import WorkOrderRepository
from app.repositories.work_order_activity import (
    WorkOrderActivityRepository,
)
from app.repositories.work_order_material import (
    WorkOrderMaterialRepository,
)
from app.schemas.purchase_requisition import (
    CreatePurchaseRequisitionSchema,
    PurchaseRequisitionLineCreate,
    PurchaseRequisitionResponse,
)
from app.schemas.work_order_material import (
    WorkOrderMaterialCreate,
    WorkOrderMaterialItemSummary,
    WorkOrderMaterialListResponse,
    WorkOrderMaterialPurchaseRequestCreate,
    WorkOrderMaterialPurchaseRequestResponse,
    WorkOrderMaterialResponse,
    WorkOrderMaterialUpdate,
)
from app.services.purchase_requisition_service import (
    PurchaseRequisitionService,
)


QUANTITY_QUANTIZER = Decimal("0.001")
COST_QUANTIZER = Decimal("0.01")
PERCENT_QUANTIZER = Decimal("0.01")

TERMINAL_WORK_ORDER_STATUSES = {
    "completed",
    "cancelled",
}

SHORTAGE_REQUEST_SOURCE = "work_order_material_shortage"
OPEN_SHORTAGE_REQUEST_STATUSES = {
    "draft",
    "submitted",
    "approved",
}


class WorkOrderMaterialService:
    """Manage planned job materials and calculate live coverage."""

    def __init__(self, db: Session):
        self.db = db
        self.work_orders = WorkOrderRepository(db)
        self.materials = WorkOrderMaterialRepository(db)
        self.activities = WorkOrderActivityRepository(db)
        self.purchase_requisitions = (
            PurchaseRequisitionRepository(db)
        )
        self.procurement = PurchaseRequisitionService(db)

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


    @staticmethod
    def _source_requirement_ids(
        requisition: PurchaseRequisition,
    ) -> list[uuid.UUID]:
        values = (requisition.details or {}).get(
            "source_requirement_ids",
            [],
        )
        result: list[uuid.UUID] = []

        for value in values:
            try:
                result.append(uuid.UUID(str(value)))
            except (TypeError, ValueError, AttributeError):
                continue

        if result:
            return result

        for line in requisition.line_items:
            value = (line.details or {}).get(
                "source_requirement_id"
            )

            if value is None:
                continue

            try:
                result.append(uuid.UUID(str(value)))
            except (TypeError, ValueError, AttributeError):
                continue

        return result

    def _find_open_shortage_request(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
    ) -> PurchaseRequisition | None:
        candidates = (
            self.purchase_requisitions.list_for_organization(
                organization_id,
                skip=0,
                limit=200,
                work_order_id=work_order_id,
                include_inactive=False,
            )
        )

        for requisition in candidates:
            if requisition.status not in (
                OPEN_SHORTAGE_REQUEST_STATUSES
            ):
                continue

            if (requisition.details or {}).get(
                "source"
            ) == SHORTAGE_REQUEST_SOURCE:
                return requisition

        return None

    @staticmethod
    def _purchase_request_response(
        requisition: PurchaseRequisition,
        *,
        created: bool,
        source_requirement_ids: list[uuid.UUID],
    ) -> WorkOrderMaterialPurchaseRequestResponse:
        return WorkOrderMaterialPurchaseRequestResponse(
            created=created,
            shortage_line_count=len(source_requirement_ids),
            source_requirement_ids=source_requirement_ids,
            requisition=(
                PurchaseRequisitionResponse.model_validate(
                    requisition
                )
            ),
        )

    @staticmethod
    def _shortage_request_line(
        item: WorkOrderMaterialResponse,
        *,
        position: int,
        generated_at: str,
    ) -> PurchaseRequisitionLineCreate:
        """Build one procurement line from a live shortage."""

        return PurchaseRequisitionLineCreate(
            inventory_item_id=item.inventory_item_id,
            description=item.item.name,
            quantity=item.missing_quantity,
            unit_of_measure=item.item.unit_of_measure,
            estimated_unit_cost=item.estimated_unit_cost,
            position=position,
            notes=item.notes,
            details={
                "source": SHORTAGE_REQUEST_SOURCE,
                "source_requirement_id": str(item.id),
                "required_quantity": str(
                    item.required_quantity
                ),
                "covered_quantity": str(
                    item.covered_quantity
                ),
                "missing_quantity": str(
                    item.missing_quantity
                ),
                "coverage_percentage": str(
                    item.coverage_percentage
                ),
                "readiness_status": (
                    item.readiness_status
                ),
                "generated_at": generated_at,
            },
        )

    def _sync_draft_shortage_request(
        self,
        organization_id: uuid.UUID,
        work_order: WorkOrder,
        requisition: PurchaseRequisition,
        shortages: list[WorkOrderMaterialResponse],
        payload: WorkOrderMaterialPurchaseRequestCreate,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> PurchaseRequisition:
        """Refresh a generated draft with current shortages and costs."""

        if requisition.status != "draft":
            return requisition

        currencies = {
            item.currency.upper()
            for item in shortages
        }

        if len(currencies) != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Current shortages use multiple currencies. "
                    "Create separate purchase requests for each "
                    "currency."
                ),
            )

        generated_at = datetime.now(UTC).isoformat()
        source_ids = [item.id for item in shortages]
        generated_lines = [
            line
            for line in list(requisition.line_items)
            if (line.details or {}).get("source")
            == SHORTAGE_REQUEST_SOURCE
        ]
        preserved_lines = [
            line
            for line in requisition.line_items
            if line not in generated_lines
        ]
        used_positions = {
            int(line.position)
            for line in preserved_lines
        }

        try:
            for line in generated_lines:
                requisition.line_items.remove(line)
                self.purchase_requisitions.delete_line_item(
                    line
                )

            next_position = 0

            for shortage in shortages:
                while next_position in used_positions:
                    next_position += 1

                line_payload = self._shortage_request_line(
                    shortage,
                    position=next_position,
                    generated_at=generated_at,
                )
                line = self.procurement._build_line(
                    organization_id,
                    line_payload,
                    position=next_position,
                )
                line.requisition_id = requisition.id
                created_line = (
                    self.purchase_requisitions.add_line_item(
                        line
                    )
                )
                requisition.line_items.append(created_line)
                used_positions.add(next_position)
                next_position += 1

            requested_delivery_date = (
                payload.requested_delivery_date
            )

            if (
                requested_delivery_date is None
                and work_order.scheduled_start is not None
            ):
                requested_delivery_date = (
                    work_order.scheduled_start.date()
                )

            details = dict(requisition.details or {})
            details.update(payload.details)
            details.update(
                {
                    "source": SHORTAGE_REQUEST_SOURCE,
                    "source_work_order_id": str(work_order.id),
                    "source_requirement_ids": [
                        str(value)
                        for value in source_ids
                    ],
                    "refreshed_at": generated_at,
                    "shortage_line_count": len(shortages),
                }
            )

            requisition.title = (
                "Missing materials for "
                f"{work_order.work_order_number}"
            )
            requisition.description = (
                "Automatically generated from live material "
                f"shortages for {work_order.title}."
            )
            requisition.priority = work_order.priority
            requisition.currency = next(iter(currencies))
            requisition.requested_delivery_date = (
                requested_delivery_date
            )
            requisition.justification = (
                payload.justification
                or requisition.justification
                or "Required to cover current job material shortages."
            )

            if payload.notes is not None:
                requisition.notes = payload.notes

            requisition.details = details

            self.procurement._recalculate_total(
                requisition
            )
            self.purchase_requisitions.update(
                requisition
            )
            self.procurement._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action=(
                    "purchase_requisition_shortage_refreshed"
                ),
                requisition=requisition,
                summary=(
                    "Generated material-shortage request refreshed."
                ),
                details={
                    "source_requirement_ids": [
                        str(value)
                        for value in source_ids
                    ],
                    "shortage_line_count": len(shortages),
                    "total_estimated_amount": (
                        requisition.total_estimated_amount
                    ),
                },
            )
            self.db.commit()

            refreshed = (
                self.purchase_requisitions.get_for_organization(
                    organization_id=organization_id,
                    requisition_id=requisition.id,
                )
            )

            if refreshed is None:
                raise HTTPException(
                    status_code=(
                        status.HTTP_404_NOT_FOUND
                    ),
                    detail=(
                        "The refreshed purchase request "
                        "could not be loaded."
                    ),
                )

            return refreshed

        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The generated purchase request could not "
                    "be refreshed because its lines conflict."
                ),
            ) from exc
        except SQLAlchemyError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

    def request_missing_materials(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        payload: WorkOrderMaterialPurchaseRequestCreate,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> WorkOrderMaterialPurchaseRequestResponse:
        """Create or refresh one idempotent shortage requisition."""

        work_order = self._get_work_order_or_404(
            organization_id,
            work_order_id,
        )
        self._ensure_work_order_mutable(work_order)

        readiness = self.list_requirements(
            organization_id,
            work_order_id,
            skip=0,
            limit=200,
        )
        shortages = [
            item
            for item in readiness.items
            if item.missing_quantity > Decimal("0.000")
        ]

        if not shortages:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This job has no current material shortage "
                    "to request."
                ),
            )

        currencies = {
            item.currency.upper()
            for item in shortages
        }

        if len(currencies) != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Current shortages use multiple currencies. "
                    "Create separate purchase requests for each "
                    "currency."
                ),
            )

        existing = self._find_open_shortage_request(
            organization_id,
            work_order_id,
        )

        if existing is not None:
            refreshed = self._sync_draft_shortage_request(
                organization_id,
                work_order,
                existing,
                shortages,
                payload,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
            )
            source_ids = self._source_requirement_ids(
                refreshed
            )

            if not source_ids:
                source_ids = [
                    item.id
                    for item in shortages
                ]

            return self._purchase_request_response(
                refreshed,
                created=False,
                source_requirement_ids=source_ids,
            )

        source_ids = [item.id for item in shortages]
        generated_at = datetime.now(UTC).isoformat()
        header_details = dict(payload.details)
        header_details.update(
            {
                "source": SHORTAGE_REQUEST_SOURCE,
                "source_work_order_id": str(work_order.id),
                "source_requirement_ids": [
                    str(value)
                    for value in source_ids
                ],
                "generated_at": generated_at,
                "shortage_line_count": len(shortages),
            }
        )

        requested_delivery_date = (
            payload.requested_delivery_date
        )

        if (
            requested_delivery_date is None
            and work_order.scheduled_start is not None
        ):
            requested_delivery_date = (
                work_order.scheduled_start.date()
            )

        lines = [
            self._shortage_request_line(
                item,
                position=index,
                generated_at=generated_at,
            )
            for index, item in enumerate(shortages)
        ]

        requisition = self.procurement.create_requisition(
            organization_id=organization_id,
            payload=CreatePurchaseRequisitionSchema(
                title=(
                    "Missing materials for "
                    f"{work_order.work_order_number}"
                ),
                description=(
                    "Automatically generated from live material "
                    f"shortages for {work_order.title}."
                ),
                priority=work_order.priority,
                currency=next(iter(currencies)),
                work_order_id=work_order.id,
                requested_delivery_date=(
                    requested_delivery_date
                ),
                justification=(
                    payload.justification
                    or "Required to cover current job material shortages."
                ),
                notes=payload.notes,
                details=header_details,
                line_items=lines,
            ),
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
        )

        return self._purchase_request_response(
            requisition,
            created=True,
            source_requirement_ids=source_ids,
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
