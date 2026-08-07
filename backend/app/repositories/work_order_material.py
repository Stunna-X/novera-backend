"""
Persistence operations for work-order material requirements.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.inventory import (
    InventoryBalance,
    InventoryLocation,
    InventoryReservation,
)
from app.models.work_order_material import (
    WorkOrderMaterialRequirement,
)


ACTIVE_RESERVATION_STATUSES = {
    "active",
    "partially_consumed",
}


class WorkOrderMaterialRepository:
    """Tenant-scoped requirement and stock-readiness queries."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _response_options():
        return (
            joinedload(
                WorkOrderMaterialRequirement.inventory_item
            ),
            joinedload(
                WorkOrderMaterialRequirement.work_order
            ),
        )

    def create(
        self,
        requirement: WorkOrderMaterialRequirement,
    ) -> WorkOrderMaterialRequirement:
        self.db.add(requirement)
        self.db.flush()
        return requirement

    def update(
        self,
        requirement: WorkOrderMaterialRequirement,
    ) -> WorkOrderMaterialRequirement:
        self.db.add(requirement)
        self.db.flush()
        return requirement

    def get_for_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        requirement_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> WorkOrderMaterialRequirement | None:
        query = (
            self.db.query(WorkOrderMaterialRequirement)
            .options(*self._response_options())
            .populate_existing()
            .filter(
                WorkOrderMaterialRequirement.id
                == requirement_id,
                WorkOrderMaterialRequirement.organization_id
                == organization_id,
                WorkOrderMaterialRequirement.work_order_id
                == work_order_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrderMaterialRequirement.is_active.is_(True)
            )

        if for_update:
            query = query.with_for_update(
                of=WorkOrderMaterialRequirement,
            )

        return query.first()

    def get_by_item(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        inventory_item_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> WorkOrderMaterialRequirement | None:
        query = (
            self.db.query(WorkOrderMaterialRequirement)
            .options(*self._response_options())
            .populate_existing()
            .filter(
                WorkOrderMaterialRequirement.organization_id
                == organization_id,
                WorkOrderMaterialRequirement.work_order_id
                == work_order_id,
                WorkOrderMaterialRequirement.inventory_item_id
                == inventory_item_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrderMaterialRequirement.is_active.is_(True)
            )

        if for_update:
            query = query.with_for_update(
                of=WorkOrderMaterialRequirement,
            )

        return query.first()

    def list_for_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        include_inactive: bool = False,
    ) -> list[WorkOrderMaterialRequirement]:
        query = (
            self.db.query(WorkOrderMaterialRequirement)
            .options(*self._response_options())
            .populate_existing()
            .filter(
                WorkOrderMaterialRequirement.organization_id
                == organization_id,
                WorkOrderMaterialRequirement.work_order_id
                == work_order_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrderMaterialRequirement.is_active.is_(True)
            )

        return (
            query.order_by(
                WorkOrderMaterialRequirement.position.asc(),
                WorkOrderMaterialRequirement.created_at.asc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> int:
        query = (
            self.db.query(
                func.count(WorkOrderMaterialRequirement.id)
            )
            .filter(
                WorkOrderMaterialRequirement.organization_id
                == organization_id,
                WorkOrderMaterialRequirement.work_order_id
                == work_order_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrderMaterialRequirement.is_active.is_(True)
            )

        return int(query.scalar() or 0)

    def get_next_position(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
    ) -> int:
        current = (
            self.db.query(
                func.max(WorkOrderMaterialRequirement.position)
            )
            .filter(
                WorkOrderMaterialRequirement.organization_id
                == organization_id,
                WorkOrderMaterialRequirement.work_order_id
                == work_order_id,
                WorkOrderMaterialRequirement.is_active.is_(True),
            )
            .scalar()
        )

        return int(current or -1) + 1

    def get_stock_totals(
        self,
        organization_id: uuid.UUID,
        inventory_item_ids: set[uuid.UUID],
    ) -> dict[uuid.UUID, dict[str, Decimal | int]]:
        if not inventory_item_ids:
            return {}

        rows = (
            self.db.query(
                InventoryBalance.item_id,
                func.coalesce(
                    func.sum(InventoryBalance.quantity_on_hand),
                    0,
                ).label("quantity_on_hand"),
                func.coalesce(
                    func.sum(InventoryBalance.quantity_reserved),
                    0,
                ).label("quantity_reserved"),
                func.count(
                    func.distinct(InventoryBalance.location_id)
                ).label("active_location_count"),
            )
            .join(
                InventoryLocation,
                InventoryLocation.id
                == InventoryBalance.location_id,
            )
            .filter(
                InventoryBalance.organization_id
                == organization_id,
                InventoryBalance.item_id.in_(
                    inventory_item_ids
                ),
                InventoryLocation.organization_id
                == organization_id,
                InventoryLocation.is_active.is_(True),
            )
            .group_by(InventoryBalance.item_id)
            .all()
        )

        return {
            row.item_id: {
                "quantity_on_hand": Decimal(
                    row.quantity_on_hand or 0
                ),
                "quantity_reserved": Decimal(
                    row.quantity_reserved or 0
                ),
                "active_location_count": int(
                    row.active_location_count or 0
                ),
            }
            for row in rows
        }

    def get_work_order_reservation_totals(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        inventory_item_ids: set[uuid.UUID],
    ) -> dict[uuid.UUID, Decimal]:
        if not inventory_item_ids:
            return {}

        now = datetime.now(UTC)

        rows = (
            self.db.query(
                InventoryReservation.item_id,
                func.coalesce(
                    func.sum(
                        InventoryReservation.quantity_reserved
                        - InventoryReservation.quantity_consumed
                    ),
                    0,
                ).label("remaining_quantity"),
            )
            .filter(
                InventoryReservation.organization_id
                == organization_id,
                InventoryReservation.work_order_id
                == work_order_id,
                InventoryReservation.item_id.in_(
                    inventory_item_ids
                ),
                InventoryReservation.status.in_(
                    ACTIVE_RESERVATION_STATUSES
                ),
                InventoryReservation.is_active.is_(True),
                or_(
                    InventoryReservation.expires_at.is_(None),
                    InventoryReservation.expires_at > now,
                ),
            )
            .group_by(InventoryReservation.item_id)
            .all()
        )

        return {
            row.item_id: Decimal(
                row.remaining_quantity or 0
            )
            for row in rows
        }
