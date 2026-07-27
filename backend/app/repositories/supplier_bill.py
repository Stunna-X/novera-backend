"""Tenant-scoped persistence for supplier bills and match snapshots."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.goods_receipt import (
    GoodsReceipt,
    GoodsReceiptLineItem,
)
from app.models.supplier_bill import (
    SupplierBill,
    SupplierBillLineItem,
    SupplierBillMatchResult,
)


class SupplierBillRepository:
    """Persistence operations that flush but never commit."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _response_options():
        return (
            selectinload(SupplierBill.line_items).joinedload(
                SupplierBillLineItem.match_result
            ),
            selectinload(SupplierBill.match_results),
            joinedload(SupplierBill.supplier),
            joinedload(SupplierBill.purchase_order),
            joinedload(SupplierBill.created_by),
            joinedload(SupplierBill.submitted_by),
            joinedload(SupplierBill.matched_by),
            joinedload(SupplierBill.approved_by),
            joinedload(SupplierBill.voided_by),
        )

    def create(self, supplier_bill: SupplierBill) -> SupplierBill:
        supplier_bill.supplier_bill_number = (
            supplier_bill.supplier_bill_number.strip().upper()
        )
        supplier_bill.supplier_invoice_number = (
            supplier_bill.supplier_invoice_number.strip()
        )
        supplier_bill.currency = supplier_bill.currency.strip().upper()
        self.db.add(supplier_bill)
        self.db.flush()
        return supplier_bill

    def update(self, supplier_bill: SupplierBill) -> SupplierBill:
        supplier_bill.supplier_bill_number = (
            supplier_bill.supplier_bill_number.strip().upper()
        )
        supplier_bill.supplier_invoice_number = (
            supplier_bill.supplier_invoice_number.strip()
        )
        supplier_bill.currency = supplier_bill.currency.strip().upper()
        self.db.add(supplier_bill)
        self.db.flush()
        return supplier_bill

    def get_for_organization(
        self,
        organization_id: uuid.UUID,
        supplier_bill_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> SupplierBill | None:
        query = (
            self.db.query(SupplierBill)
            .options(*self._response_options())
            .populate_existing()
            .filter(
                SupplierBill.id == supplier_bill_id,
                SupplierBill.organization_id == organization_id,
            )
        )
        if not include_inactive:
            query = query.filter(SupplierBill.is_active.is_(True))
        if for_update:
            query = query.with_for_update(of=SupplierBill)
        return query.first()

    def list_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        status_filter: str | None = None,
        match_status_filter: str | None = None,
        supplier_id: uuid.UUID | None = None,
        purchase_order_id: uuid.UUID | None = None,
        invoice_from: date | None = None,
        invoice_to: date | None = None,
        include_inactive: bool = False,
    ) -> list[SupplierBill]:
        query = (
            self.db.query(SupplierBill)
            .options(*self._response_options())
            .populate_existing()
            .filter(SupplierBill.organization_id == organization_id)
        )
        query = self._apply_filters(
            query=query,
            search=search,
            status_filter=status_filter,
            match_status_filter=match_status_filter,
            supplier_id=supplier_id,
            purchase_order_id=purchase_order_id,
            invoice_from=invoice_from,
            invoice_to=invoice_to,
            include_inactive=include_inactive,
        )
        return (
            query.order_by(
                SupplierBill.invoice_date.desc(),
                SupplierBill.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_organization(
        self,
        organization_id: uuid.UUID,
        **filters,
    ) -> int:
        query = self.db.query(func.count(SupplierBill.id)).filter(
            SupplierBill.organization_id == organization_id
        )
        query = self._apply_filters(query=query, **filters)
        return int(query.scalar() or 0)

    @staticmethod
    def _apply_filters(
        *,
        query,
        search: str | None = None,
        status_filter: str | None = None,
        match_status_filter: str | None = None,
        supplier_id: uuid.UUID | None = None,
        purchase_order_id: uuid.UUID | None = None,
        invoice_from: date | None = None,
        invoice_to: date | None = None,
        include_inactive: bool = False,
    ):
        if not include_inactive:
            query = query.filter(SupplierBill.is_active.is_(True))
        if status_filter:
            query = query.filter(SupplierBill.status == status_filter)
        if match_status_filter:
            query = query.filter(
                SupplierBill.match_status == match_status_filter
            )
        if supplier_id:
            query = query.filter(SupplierBill.supplier_id == supplier_id)
        if purchase_order_id:
            query = query.filter(
                SupplierBill.purchase_order_id == purchase_order_id
            )
        if invoice_from:
            query = query.filter(SupplierBill.invoice_date >= invoice_from)
        if invoice_to:
            query = query.filter(SupplierBill.invoice_date <= invoice_to)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    SupplierBill.supplier_bill_number.ilike(pattern),
                    SupplierBill.supplier_invoice_number.ilike(pattern),
                )
            )
        return query

    def number_exists(
        self,
        organization_id: uuid.UUID,
        supplier_bill_number: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        query = self.db.query(SupplierBill.id).filter(
            SupplierBill.organization_id == organization_id,
            func.upper(SupplierBill.supplier_bill_number)
            == supplier_bill_number.strip().upper(),
        )
        if exclude_id:
            query = query.filter(SupplierBill.id != exclude_id)
        return query.first() is not None

    def supplier_invoice_exists(
        self,
        organization_id: uuid.UUID,
        supplier_id: uuid.UUID,
        supplier_invoice_number: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        query = self.db.query(SupplierBill.id).filter(
            SupplierBill.organization_id == organization_id,
            SupplierBill.supplier_id == supplier_id,
            func.lower(SupplierBill.supplier_invoice_number)
            == supplier_invoice_number.strip().lower(),
        )
        if exclude_id:
            query = query.filter(SupplierBill.id != exclude_id)
        return query.first() is not None

    def add_line_item(
        self,
        line_item: SupplierBillLineItem,
    ) -> SupplierBillLineItem:
        line_item.description = line_item.description.strip()
        line_item.unit_of_measure = (
            line_item.unit_of_measure.strip().lower()
        )
        self.db.add(line_item)
        self.db.flush()
        return line_item

    def update_line_item(
        self,
        line_item: SupplierBillLineItem,
    ) -> SupplierBillLineItem:
        line_item.description = line_item.description.strip()
        line_item.unit_of_measure = (
            line_item.unit_of_measure.strip().lower()
        )
        self.db.add(line_item)
        self.db.flush()
        return line_item

    def delete_line_item(self, line_item: SupplierBillLineItem) -> None:
        self.db.delete(line_item)
        self.db.flush()

    def get_line_item(
        self,
        organization_id: uuid.UUID,
        supplier_bill_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierBillLineItem | None:
        query = (
            self.db.query(SupplierBillLineItem)
            .join(SupplierBill)
            .options(joinedload(SupplierBillLineItem.match_result))
            .filter(
                SupplierBill.organization_id == organization_id,
                SupplierBill.id == supplier_bill_id,
                SupplierBillLineItem.id == line_item_id,
            )
        )
        if for_update:
            query = query.with_for_update(of=SupplierBillLineItem)
        return query.first()

    def list_line_items_for_update(
        self,
        supplier_bill_id: uuid.UUID,
    ) -> list[SupplierBillLineItem]:
        return (
            self.db.query(SupplierBillLineItem)
            .filter(
                SupplierBillLineItem.supplier_bill_id == supplier_bill_id
            )
            .order_by(SupplierBillLineItem.position.asc())
            .with_for_update(of=SupplierBillLineItem)
            .all()
        )

    def get_match_result(
        self,
        supplier_bill_line_item_id: uuid.UUID,
    ) -> SupplierBillMatchResult | None:
        return (
            self.db.query(SupplierBillMatchResult)
            .filter(
                SupplierBillMatchResult.supplier_bill_line_item_id
                == supplier_bill_line_item_id
            )
            .with_for_update(of=SupplierBillMatchResult)
            .first()
        )

    def save_match_result(
        self,
        result: SupplierBillMatchResult,
    ) -> SupplierBillMatchResult:
        self.db.add(result)
        self.db.flush()
        return result

    def posted_received_quantity(
        self,
        *,
        organization_id: uuid.UUID,
        purchase_order_line_item_id: uuid.UUID,
    ) -> Decimal:
        value = (
            self.db.query(
                func.coalesce(
                    func.sum(GoodsReceiptLineItem.quantity_accepted),
                    0,
                )
            )
            .join(
                GoodsReceipt,
                GoodsReceipt.id == GoodsReceiptLineItem.goods_receipt_id,
            )
            .filter(
                GoodsReceipt.organization_id == organization_id,
                GoodsReceipt.status == "posted",
                GoodsReceiptLineItem.purchase_order_line_item_id
                == purchase_order_line_item_id,
            )
            .scalar()
        )
        return Decimal(value or 0)
