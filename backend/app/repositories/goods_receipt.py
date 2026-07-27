"""Tenant-scoped persistence for goods receipts."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.goods_receipt import (
    GoodsReceipt,
    GoodsReceiptLineItem,
)


class GoodsReceiptRepository:
    """Persistence operations that never commit transactions."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _response_options():
        return (
            selectinload(GoodsReceipt.line_items),
            joinedload(GoodsReceipt.purchase_order),
            joinedload(GoodsReceipt.supplier),
            joinedload(GoodsReceipt.receiving_location),
            joinedload(GoodsReceipt.created_by),
            joinedload(GoodsReceipt.posted_by),
            joinedload(GoodsReceipt.cancelled_by),
        )

    @staticmethod
    def _normalize(receipt: GoodsReceipt) -> None:
        receipt.goods_receipt_number = (
            receipt.goods_receipt_number.strip().upper()
        )
        receipt.status = receipt.status.strip().lower()
        receipt.supplier_delivery_note = (
            receipt.supplier_delivery_note.strip()
            if receipt.supplier_delivery_note
            else None
        )
        receipt.carrier_name = (
            receipt.carrier_name.strip()
            if receipt.carrier_name
            else None
        )
        receipt.vehicle_reference = (
            receipt.vehicle_reference.strip()
            if receipt.vehicle_reference
            else None
        )
        receipt.notes = receipt.notes.strip() if receipt.notes else None
        receipt.cancellation_reason = (
            receipt.cancellation_reason.strip()
            if receipt.cancellation_reason
            else None
        )

    @staticmethod
    def _normalize_line(line: GoodsReceiptLineItem) -> None:
        line.description = line.description.strip()
        line.unit_of_measure = line.unit_of_measure.strip().lower()
        line.currency = line.currency.strip().upper()
        line.rejection_reason = (
            line.rejection_reason.strip()
            if line.rejection_reason
            else None
        )
        line.damage_notes = (
            line.damage_notes.strip()
            if line.damage_notes
            else None
        )

    def create(self, receipt: GoodsReceipt) -> GoodsReceipt:
        self._normalize(receipt)
        self.db.add(receipt)
        self.db.flush()
        return receipt

    def update(self, receipt: GoodsReceipt) -> GoodsReceipt:
        self._normalize(receipt)
        self.db.add(receipt)
        self.db.flush()
        return receipt

    def get_for_organization(
        self,
        organization_id: uuid.UUID,
        goods_receipt_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> GoodsReceipt | None:
        query = (
            self.db.query(GoodsReceipt)
            .options(*self._response_options())
            .populate_existing()
            .filter(
                GoodsReceipt.id == goods_receipt_id,
                GoodsReceipt.organization_id == organization_id,
            )
        )

        if not include_inactive:
            query = query.filter(GoodsReceipt.is_active.is_(True))

        if for_update:
            query = query.with_for_update(of=GoodsReceipt)

        return query.first()

    def list_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        status_filter: str | None = None,
        purchase_order_id: uuid.UUID | None = None,
        supplier_id: uuid.UUID | None = None,
        receiving_location_id: uuid.UUID | None = None,
        received_from: datetime | None = None,
        received_to: datetime | None = None,
        include_inactive: bool = False,
    ) -> list[GoodsReceipt]:
        query = (
            self.db.query(GoodsReceipt)
            .options(*self._response_options())
            .populate_existing()
            .filter(GoodsReceipt.organization_id == organization_id)
        )

        query = self._apply_filters(
            query=query,
            search=search,
            status_filter=status_filter,
            purchase_order_id=purchase_order_id,
            supplier_id=supplier_id,
            receiving_location_id=receiving_location_id,
            received_from=received_from,
            received_to=received_to,
            include_inactive=include_inactive,
        )

        return (
            query.order_by(
                GoodsReceipt.received_at.desc().nullslast(),
                GoodsReceipt.created_at.desc(),
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
        purchase_order_id: uuid.UUID | None = None,
        supplier_id: uuid.UUID | None = None,
        receiving_location_id: uuid.UUID | None = None,
        received_from: datetime | None = None,
        received_to: datetime | None = None,
        include_inactive: bool = False,
    ) -> int:
        query = self.db.query(func.count(GoodsReceipt.id)).filter(
            GoodsReceipt.organization_id == organization_id
        )

        query = self._apply_filters(
            query=query,
            search=search,
            status_filter=status_filter,
            purchase_order_id=purchase_order_id,
            supplier_id=supplier_id,
            receiving_location_id=receiving_location_id,
            received_from=received_from,
            received_to=received_to,
            include_inactive=include_inactive,
        )

        return int(query.scalar() or 0)

    @staticmethod
    def _apply_filters(
        *,
        query,
        search: str | None,
        status_filter: str | None,
        purchase_order_id: uuid.UUID | None,
        supplier_id: uuid.UUID | None,
        receiving_location_id: uuid.UUID | None,
        received_from: datetime | None,
        received_to: datetime | None,
        include_inactive: bool,
    ):
        if not include_inactive:
            query = query.filter(GoodsReceipt.is_active.is_(True))

        if status_filter:
            query = query.filter(GoodsReceipt.status == status_filter)

        if purchase_order_id:
            query = query.filter(
                GoodsReceipt.purchase_order_id == purchase_order_id
            )

        if supplier_id:
            query = query.filter(GoodsReceipt.supplier_id == supplier_id)

        if receiving_location_id:
            query = query.filter(
                GoodsReceipt.receiving_location_id
                == receiving_location_id
            )

        if received_from:
            query = query.filter(GoodsReceipt.received_at >= received_from)

        if received_to:
            query = query.filter(GoodsReceipt.received_at <= received_to)

        normalized_search = search.strip() if search else None

        if normalized_search:
            pattern = f"%{normalized_search}%"
            query = query.filter(
                or_(
                    GoodsReceipt.goods_receipt_number.ilike(pattern),
                    GoodsReceipt.supplier_delivery_note.ilike(pattern),
                    GoodsReceipt.carrier_name.ilike(pattern),
                    GoodsReceipt.vehicle_reference.ilike(pattern),
                    GoodsReceipt.notes.ilike(pattern),
                )
            )

        return query

    def number_exists(
        self,
        organization_id: uuid.UUID,
        goods_receipt_number: str,
    ) -> bool:
        normalized = goods_receipt_number.strip().upper()

        return (
            self.db.query(GoodsReceipt.id)
            .filter(
                GoodsReceipt.organization_id == organization_id,
                func.upper(GoodsReceipt.goods_receipt_number)
                == normalized,
            )
            .first()
            is not None
        )

    def get_line_item(
        self,
        organization_id: uuid.UUID,
        goods_receipt_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> GoodsReceiptLineItem | None:
        query = (
            self.db.query(GoodsReceiptLineItem)
            .join(
                GoodsReceipt,
                GoodsReceipt.id
                == GoodsReceiptLineItem.goods_receipt_id,
            )
            .filter(
                GoodsReceiptLineItem.id == line_item_id,
                GoodsReceiptLineItem.goods_receipt_id
                == goods_receipt_id,
                GoodsReceipt.organization_id == organization_id,
            )
        )

        if for_update:
            query = query.with_for_update(of=GoodsReceiptLineItem)

        return query.first()

    def list_line_items_for_update(
        self,
        goods_receipt_id: uuid.UUID,
    ) -> list[GoodsReceiptLineItem]:
        return (
            self.db.query(GoodsReceiptLineItem)
            .populate_existing()
            .filter(
                GoodsReceiptLineItem.goods_receipt_id
                == goods_receipt_id
            )
            .order_by(GoodsReceiptLineItem.position.asc())
            .with_for_update(of=GoodsReceiptLineItem)
            .all()
        )

    def purchase_order_line_exists(
        self,
        goods_receipt_id: uuid.UUID,
        purchase_order_line_item_id: uuid.UUID,
        *,
        exclude_line_item_id: uuid.UUID | None = None,
    ) -> bool:
        query = self.db.query(GoodsReceiptLineItem.id).filter(
            GoodsReceiptLineItem.goods_receipt_id == goods_receipt_id,
            GoodsReceiptLineItem.purchase_order_line_item_id
            == purchase_order_line_item_id,
        )

        if exclude_line_item_id is not None:
            query = query.filter(
                GoodsReceiptLineItem.id != exclude_line_item_id
            )

        return query.first() is not None

    def next_position(self, goods_receipt_id: uuid.UUID) -> int:
        highest = (
            self.db.query(func.max(GoodsReceiptLineItem.position))
            .filter(
                GoodsReceiptLineItem.goods_receipt_id
                == goods_receipt_id
            )
            .scalar()
        )

        return int(highest or -1) + 1

    def add_line_item(
        self,
        line_item: GoodsReceiptLineItem,
    ) -> GoodsReceiptLineItem:
        self._normalize_line(line_item)
        self.db.add(line_item)
        self.db.flush()
        return line_item

    def update_line_item(
        self,
        line_item: GoodsReceiptLineItem,
    ) -> GoodsReceiptLineItem:
        self._normalize_line(line_item)
        self.db.add(line_item)
        self.db.flush()
        return line_item

    def delete_line_item(
        self,
        line_item: GoodsReceiptLineItem,
    ) -> None:
        self.db.delete(line_item)
        self.db.flush()
