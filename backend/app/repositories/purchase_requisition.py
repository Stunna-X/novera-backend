"""Tenant-scoped persistence for purchase requisitions."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.purchase_requisition import (
    PurchaseRequisition,
    PurchaseRequisitionLineItem,
)


class PurchaseRequisitionRepository:
    """Persistence operations that never commit transactions."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _response_options():
        return (
            selectinload(PurchaseRequisition.line_items),
            joinedload(PurchaseRequisition.preferred_supplier),
            joinedload(PurchaseRequisition.work_order),
            joinedload(PurchaseRequisition.delivery_location),
            joinedload(PurchaseRequisition.created_by),
            joinedload(PurchaseRequisition.submitted_by),
            joinedload(PurchaseRequisition.approved_by),
            joinedload(PurchaseRequisition.rejected_by),
            joinedload(PurchaseRequisition.cancelled_by),
        )

    def create(
        self,
        requisition: PurchaseRequisition,
    ) -> PurchaseRequisition:
        requisition.requisition_number = (
            requisition.requisition_number.strip().upper()
        )
        requisition.title = requisition.title.strip()
        requisition.currency = requisition.currency.strip().upper()

        self.db.add(requisition)
        self.db.flush()
        return requisition

    def update(
        self,
        requisition: PurchaseRequisition,
    ) -> PurchaseRequisition:
        requisition.requisition_number = (
            requisition.requisition_number.strip().upper()
        )
        requisition.title = requisition.title.strip()
        requisition.currency = requisition.currency.strip().upper()

        self.db.add(requisition)
        self.db.flush()
        return requisition

    def get_for_organization(
        self,
        organization_id: uuid.UUID,
        requisition_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> PurchaseRequisition | None:
        query = (
            self.db.query(PurchaseRequisition)
            .options(*self._response_options())
            .populate_existing()
            .filter(
                PurchaseRequisition.id == requisition_id,
                PurchaseRequisition.organization_id
                == organization_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                PurchaseRequisition.is_active.is_(True)
            )

        if for_update:
            query = query.with_for_update(
                of=PurchaseRequisition,
            )

        return query.first()

    def list_for_organization(
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
    ) -> list[PurchaseRequisition]:
        query = (
            self.db.query(PurchaseRequisition)
            .options(*self._response_options())
            .populate_existing()
            .filter(
                PurchaseRequisition.organization_id
                == organization_id
            )
        )

        query = self._apply_filters(
            query=query,
            search=search,
            status_filter=status_filter,
            priority=priority,
            preferred_supplier_id=preferred_supplier_id,
            work_order_id=work_order_id,
            include_inactive=include_inactive,
        )

        return (
            query.order_by(
                PurchaseRequisition.created_at.desc()
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None = None,
        status_filter: str | None = None,
        priority: str | None = None,
        preferred_supplier_id: uuid.UUID | None = None,
        work_order_id: uuid.UUID | None = None,
        include_inactive: bool = False,
    ) -> int:
        query = (
            self.db.query(func.count(PurchaseRequisition.id))
            .filter(
                PurchaseRequisition.organization_id
                == organization_id
            )
        )

        query = self._apply_filters(
            query=query,
            search=search,
            status_filter=status_filter,
            priority=priority,
            preferred_supplier_id=preferred_supplier_id,
            work_order_id=work_order_id,
            include_inactive=include_inactive,
        )

        return int(query.scalar() or 0)

    @staticmethod
    def _apply_filters(
        *,
        query,
        search: str | None,
        status_filter: str | None,
        priority: str | None,
        preferred_supplier_id: uuid.UUID | None,
        work_order_id: uuid.UUID | None,
        include_inactive: bool,
    ):
        if not include_inactive:
            query = query.filter(
                PurchaseRequisition.is_active.is_(True)
            )

        if status_filter:
            query = query.filter(
                PurchaseRequisition.status == status_filter
            )

        if priority:
            query = query.filter(
                PurchaseRequisition.priority == priority
            )

        if preferred_supplier_id:
            query = query.filter(
                PurchaseRequisition.preferred_supplier_id
                == preferred_supplier_id
            )

        if work_order_id:
            query = query.filter(
                PurchaseRequisition.work_order_id
                == work_order_id
            )

        normalized_search = search.strip() if search else None

        if normalized_search:
            pattern = f"%{normalized_search}%"
            query = query.filter(
                or_(
                    PurchaseRequisition.requisition_number.ilike(
                        pattern
                    ),
                    PurchaseRequisition.title.ilike(pattern),
                    PurchaseRequisition.description.ilike(pattern),
                    PurchaseRequisition.justification.ilike(pattern),
                )
            )

        return query

    def number_exists(
        self,
        organization_id: uuid.UUID,
        requisition_number: str,
    ) -> bool:
        normalized = requisition_number.strip().upper()

        return (
            self.db.query(PurchaseRequisition.id)
            .filter(
                PurchaseRequisition.organization_id
                == organization_id,
                func.upper(
                    PurchaseRequisition.requisition_number
                ) == normalized,
            )
            .first()
            is not None
        )

    def get_line_item(
        self,
        organization_id: uuid.UUID,
        requisition_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> PurchaseRequisitionLineItem | None:
        query = (
            self.db.query(PurchaseRequisitionLineItem)
            .join(
                PurchaseRequisition,
                PurchaseRequisition.id
                == PurchaseRequisitionLineItem.requisition_id,
            )
            .filter(
                PurchaseRequisitionLineItem.id == line_item_id,
                PurchaseRequisitionLineItem.requisition_id
                == requisition_id,
                PurchaseRequisition.organization_id
                == organization_id,
            )
        )

        if for_update:
            query = query.with_for_update(
                of=PurchaseRequisitionLineItem,
            )

        return query.first()

    def next_position(
        self,
        requisition_id: uuid.UUID,
    ) -> int:
        highest = (
            self.db.query(
                func.max(PurchaseRequisitionLineItem.position)
            )
            .filter(
                PurchaseRequisitionLineItem.requisition_id
                == requisition_id
            )
            .scalar()
        )

        return int(highest or -1) + 1

    def add_line_item(
        self,
        line_item: PurchaseRequisitionLineItem,
    ) -> PurchaseRequisitionLineItem:
        self.db.add(line_item)
        self.db.flush()
        return line_item

    def update_line_item(
        self,
        line_item: PurchaseRequisitionLineItem,
    ) -> PurchaseRequisitionLineItem:
        self.db.add(line_item)
        self.db.flush()
        return line_item

    def delete_line_item(
        self,
        line_item: PurchaseRequisitionLineItem,
    ) -> None:
        self.db.delete(line_item)
        self.db.flush()
