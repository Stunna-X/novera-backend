"""Tenant-scoped persistence for purchase orders."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.purchase_order import (
    PurchaseOrder,
    PurchaseOrderLineItem,
)


class PurchaseOrderRepository:
    """Persistence operations that never commit transactions."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _response_options():
        return (
            selectinload(PurchaseOrder.line_items),
            joinedload(PurchaseOrder.source_requisition),
            joinedload(PurchaseOrder.supplier),
            joinedload(PurchaseOrder.delivery_location),
            joinedload(PurchaseOrder.created_by),
            joinedload(PurchaseOrder.issued_by),
            joinedload(PurchaseOrder.acknowledged_by),
            joinedload(PurchaseOrder.cancelled_by),
            joinedload(PurchaseOrder.closed_by),
        )

    def create(
        self,
        purchase_order: PurchaseOrder,
    ) -> PurchaseOrder:
        purchase_order.purchase_order_number = (
            purchase_order.purchase_order_number.strip().upper()
        )
        purchase_order.title = purchase_order.title.strip()
        purchase_order.currency = (
            purchase_order.currency.strip().upper()
        )
        purchase_order.supplier_name = (
            purchase_order.supplier_name.strip()
        )

        self.db.add(purchase_order)
        self.db.flush()
        return purchase_order

    def update(
        self,
        purchase_order: PurchaseOrder,
    ) -> PurchaseOrder:
        purchase_order.purchase_order_number = (
            purchase_order.purchase_order_number.strip().upper()
        )
        purchase_order.title = purchase_order.title.strip()
        purchase_order.currency = (
            purchase_order.currency.strip().upper()
        )
        purchase_order.supplier_name = (
            purchase_order.supplier_name.strip()
        )

        self.db.add(purchase_order)
        self.db.flush()
        return purchase_order

    def get_for_organization(
        self,
        organization_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> PurchaseOrder | None:
        query = (
            self.db.query(PurchaseOrder)
            .options(*self._response_options())
            .populate_existing()
            .filter(
                PurchaseOrder.id == purchase_order_id,
                PurchaseOrder.organization_id == organization_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                PurchaseOrder.is_active.is_(True)
            )

        if for_update:
            query = query.with_for_update(
                of=PurchaseOrder,
            )

        return query.first()

    def get_by_source_requisition(
        self,
        organization_id: uuid.UUID,
        source_requisition_id: uuid.UUID,
    ) -> PurchaseOrder | None:
        return (
            self.db.query(PurchaseOrder)
            .options(*self._response_options())
            .filter(
                PurchaseOrder.organization_id == organization_id,
                PurchaseOrder.source_requisition_id
                == source_requisition_id,
            )
            .first()
        )

    def list_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        status_filter: str | None = None,
        supplier_id: uuid.UUID | None = None,
        source_requisition_id: uuid.UUID | None = None,
        expected_from: date | None = None,
        expected_to: date | None = None,
        include_inactive: bool = False,
    ) -> list[PurchaseOrder]:
        query = (
            self.db.query(PurchaseOrder)
            .options(*self._response_options())
            .populate_existing()
            .filter(
                PurchaseOrder.organization_id == organization_id
            )
        )

        query = self._apply_filters(
            query=query,
            search=search,
            status_filter=status_filter,
            supplier_id=supplier_id,
            source_requisition_id=source_requisition_id,
            expected_from=expected_from,
            expected_to=expected_to,
            include_inactive=include_inactive,
        )

        return (
            query.order_by(PurchaseOrder.created_at.desc())
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
        supplier_id: uuid.UUID | None = None,
        source_requisition_id: uuid.UUID | None = None,
        expected_from: date | None = None,
        expected_to: date | None = None,
        include_inactive: bool = False,
    ) -> int:
        query = (
            self.db.query(func.count(PurchaseOrder.id))
            .filter(
                PurchaseOrder.organization_id == organization_id
            )
        )

        query = self._apply_filters(
            query=query,
            search=search,
            status_filter=status_filter,
            supplier_id=supplier_id,
            source_requisition_id=source_requisition_id,
            expected_from=expected_from,
            expected_to=expected_to,
            include_inactive=include_inactive,
        )

        return int(query.scalar() or 0)

    @staticmethod
    def _apply_filters(
        *,
        query,
        search: str | None,
        status_filter: str | None,
        supplier_id: uuid.UUID | None,
        source_requisition_id: uuid.UUID | None,
        expected_from: date | None,
        expected_to: date | None,
        include_inactive: bool,
    ):
        if not include_inactive:
            query = query.filter(
                PurchaseOrder.is_active.is_(True)
            )

        if status_filter:
            query = query.filter(
                PurchaseOrder.status == status_filter
            )

        if supplier_id:
            query = query.filter(
                PurchaseOrder.supplier_id == supplier_id
            )

        if source_requisition_id:
            query = query.filter(
                PurchaseOrder.source_requisition_id
                == source_requisition_id
            )

        if expected_from:
            query = query.filter(
                PurchaseOrder.expected_delivery_date
                >= expected_from
            )

        if expected_to:
            query = query.filter(
                PurchaseOrder.expected_delivery_date <= expected_to
            )

        normalized_search = search.strip() if search else None

        if normalized_search:
            pattern = f"%{normalized_search}%"
            query = query.filter(
                or_(
                    PurchaseOrder.purchase_order_number.ilike(
                        pattern
                    ),
                    PurchaseOrder.title.ilike(pattern),
                    PurchaseOrder.supplier_name.ilike(pattern),
                    PurchaseOrder.supplier_reference.ilike(pattern),
                )
            )

        return query

    def number_exists(
        self,
        organization_id: uuid.UUID,
        purchase_order_number: str,
    ) -> bool:
        normalized = purchase_order_number.strip().upper()

        return (
            self.db.query(PurchaseOrder.id)
            .filter(
                PurchaseOrder.organization_id == organization_id,
                func.upper(PurchaseOrder.purchase_order_number)
                == normalized,
            )
            .first()
            is not None
        )

    def get_line_item(
        self,
        organization_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> PurchaseOrderLineItem | None:
        query = (
            self.db.query(PurchaseOrderLineItem)
            .join(
                PurchaseOrder,
                PurchaseOrder.id
                == PurchaseOrderLineItem.purchase_order_id,
            )
            .filter(
                PurchaseOrderLineItem.id == line_item_id,
                PurchaseOrderLineItem.purchase_order_id
                == purchase_order_id,
                PurchaseOrder.organization_id == organization_id,
            )
        )

        if for_update:
            query = query.with_for_update(
                of=PurchaseOrderLineItem,
            )

        return query.first()

    def next_position(
        self,
        purchase_order_id: uuid.UUID,
    ) -> int:
        highest = (
            self.db.query(func.max(PurchaseOrderLineItem.position))
            .filter(
                PurchaseOrderLineItem.purchase_order_id
                == purchase_order_id
            )
            .scalar()
        )

        return int(highest or -1) + 1

    def add_line_item(
        self,
        line_item: PurchaseOrderLineItem,
    ) -> PurchaseOrderLineItem:
        self.db.add(line_item)
        self.db.flush()
        return line_item

    def update_line_item(
        self,
        line_item: PurchaseOrderLineItem,
    ) -> PurchaseOrderLineItem:
        self.db.add(line_item)
        self.db.flush()
        return line_item

    def delete_line_item(
        self,
        line_item: PurchaseOrderLineItem,
    ) -> None:
        self.db.delete(line_item)
        self.db.flush()
