"""Tenant-scoped persistence for supplier returns and debit notes."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.goods_receipt import GoodsReceipt, GoodsReceiptLineItem
from app.models.supplier_bill import SupplierBill, SupplierBillLineItem
from app.models.supplier_payment import SupplierPayment
from app.models.supplier_return import (
    SupplierCreditSettlement,
    SupplierDebitNote,
    SupplierDebitNoteLineItem,
    SupplierReturn,
    SupplierReturnLineItem,
)


class SupplierReturnRepository:
    """Repository mutations flush but do not commit."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _return_options():
        return (
            selectinload(SupplierReturn.line_items),
            joinedload(SupplierReturn.supplier),
            joinedload(SupplierReturn.purchase_order),
            joinedload(SupplierReturn.goods_receipt),
            joinedload(SupplierReturn.source_location),
        )

    @staticmethod
    def _debit_note_options():
        return (
            selectinload(SupplierDebitNote.line_items),
            selectinload(SupplierDebitNote.settlements).joinedload(
                SupplierCreditSettlement.supplier_payment
            ),
            joinedload(SupplierDebitNote.supplier),
            joinedload(SupplierDebitNote.supplier_return),
            joinedload(SupplierDebitNote.purchase_order),
        )

    def get_goods_receipt(
        self,
        organization_id: uuid.UUID,
        goods_receipt_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> GoodsReceipt | None:
        query = (
            self.db.query(GoodsReceipt)
            .options(selectinload(GoodsReceipt.line_items))
            .populate_existing()
            .filter(
                GoodsReceipt.id == goods_receipt_id,
                GoodsReceipt.organization_id == organization_id,
                GoodsReceipt.is_active.is_(True),
            )
        )
        if for_update:
            query = query.with_for_update(of=GoodsReceipt)
        return query.first()

    def get_goods_receipt_line(
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
                GoodsReceipt.id == GoodsReceiptLineItem.goods_receipt_id,
            )
            .filter(
                GoodsReceipt.organization_id == organization_id,
                GoodsReceipt.id == goods_receipt_id,
                GoodsReceiptLineItem.id == line_item_id,
            )
        )
        if for_update:
            query = query.with_for_update(of=GoodsReceiptLineItem)
        return query.first()

    def return_number_exists(
        self,
        organization_id: uuid.UUID,
        return_number: str,
    ) -> bool:
        return (
            self.db.query(SupplierReturn.id)
            .filter(
                SupplierReturn.organization_id == organization_id,
                func.lower(SupplierReturn.return_number)
                == return_number.strip().lower(),
            )
            .first()
            is not None
        )

    def create_return(
        self,
        supplier_return: SupplierReturn,
    ) -> SupplierReturn:
        self.db.add(supplier_return)
        self.db.flush()
        return supplier_return

    def update_return(
        self,
        supplier_return: SupplierReturn,
    ) -> SupplierReturn:
        self.db.add(supplier_return)
        self.db.flush()
        return supplier_return

    def get_return(
        self,
        organization_id: uuid.UUID,
        supplier_return_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierReturn | None:
        query = (
            self.db.query(SupplierReturn)
            .options(*self._return_options())
            .populate_existing()
            .filter(
                SupplierReturn.id == supplier_return_id,
                SupplierReturn.organization_id == organization_id,
                SupplierReturn.is_active.is_(True),
            )
        )
        if for_update:
            query = query.with_for_update(of=SupplierReturn)
        return query.first()

    def list_returns(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        supplier_id: uuid.UUID | None,
        status_filter: str | None,
        search: str | None,
    ) -> list[SupplierReturn]:
        query = (
            self.db.query(SupplierReturn)
            .options(*self._return_options())
            .filter(
                SupplierReturn.organization_id == organization_id,
                SupplierReturn.is_active.is_(True),
            )
        )
        if supplier_id is not None:
            query = query.filter(
                SupplierReturn.supplier_id == supplier_id
            )
        if status_filter:
            query = query.filter(SupplierReturn.status == status_filter)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    SupplierReturn.return_number.ilike(pattern),
                    SupplierReturn.supplier_reference.ilike(pattern),
                    SupplierReturn.tracking_number.ilike(pattern),
                )
            )
        return (
            query.order_by(
                SupplierReturn.return_date.desc(),
                SupplierReturn.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_returns(
        self,
        organization_id: uuid.UUID,
        *,
        supplier_id: uuid.UUID | None,
        status_filter: str | None,
        search: str | None,
    ) -> int:
        query = self.db.query(func.count(SupplierReturn.id)).filter(
            SupplierReturn.organization_id == organization_id,
            SupplierReturn.is_active.is_(True),
        )
        if supplier_id is not None:
            query = query.filter(
                SupplierReturn.supplier_id == supplier_id
            )
        if status_filter:
            query = query.filter(SupplierReturn.status == status_filter)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    SupplierReturn.return_number.ilike(pattern),
                    SupplierReturn.supplier_reference.ilike(pattern),
                    SupplierReturn.tracking_number.ilike(pattern),
                )
            )
        return int(query.scalar() or 0)

    def get_return_line(
        self,
        organization_id: uuid.UUID,
        supplier_return_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierReturnLineItem | None:
        query = (
            self.db.query(SupplierReturnLineItem)
            .join(
                SupplierReturn,
                SupplierReturn.id
                == SupplierReturnLineItem.supplier_return_id,
            )
            .filter(
                SupplierReturn.organization_id == organization_id,
                SupplierReturn.id == supplier_return_id,
                SupplierReturnLineItem.id == line_item_id,
            )
        )
        if for_update:
            query = query.with_for_update(of=SupplierReturnLineItem)
        return query.first()

    def returned_quantity(
        self,
        organization_id: uuid.UUID,
        goods_receipt_line_item_id: uuid.UUID,
        quantity_source: str,
        *,
        exclude_line_item_id: uuid.UUID | None = None,
    ) -> Decimal:
        query = (
            self.db.query(
                func.coalesce(
                    func.sum(SupplierReturnLineItem.quantity_returned),
                    Decimal("0.000"),
                )
            )
            .join(
                SupplierReturn,
                SupplierReturn.id
                == SupplierReturnLineItem.supplier_return_id,
            )
            .filter(
                SupplierReturn.organization_id == organization_id,
                SupplierReturn.status.in_(["dispatched", "completed"]),
                SupplierReturnLineItem.goods_receipt_line_item_id
                == goods_receipt_line_item_id,
                SupplierReturnLineItem.quantity_source == quantity_source,
            )
        )
        if exclude_line_item_id is not None:
            query = query.filter(
                SupplierReturnLineItem.id != exclude_line_item_id
            )
        return Decimal(query.scalar() or 0)

    def next_return_line_position(
        self,
        supplier_return_id: uuid.UUID,
    ) -> int:
        highest = (
            self.db.query(func.max(SupplierReturnLineItem.position))
            .filter(
                SupplierReturnLineItem.supplier_return_id
                == supplier_return_id
            )
            .scalar()
        )
        return int(highest or -1) + 1

    def add_return_line(
        self,
        line_item: SupplierReturnLineItem,
    ) -> SupplierReturnLineItem:
        self.db.add(line_item)
        self.db.flush()
        return line_item

    def update_return_line(
        self,
        line_item: SupplierReturnLineItem,
    ) -> SupplierReturnLineItem:
        self.db.add(line_item)
        self.db.flush()
        return line_item

    def delete_return_line(
        self,
        line_item: SupplierReturnLineItem,
    ) -> None:
        self.db.delete(line_item)
        self.db.flush()

    def debit_note_number_exists(
        self,
        organization_id: uuid.UUID,
        debit_note_number: str,
    ) -> bool:
        return (
            self.db.query(SupplierDebitNote.id)
            .filter(
                SupplierDebitNote.organization_id == organization_id,
                func.lower(SupplierDebitNote.debit_note_number)
                == debit_note_number.strip().lower(),
            )
            .first()
            is not None
        )

    def supplier_credit_reference_exists(
        self,
        organization_id: uuid.UUID,
        supplier_id: uuid.UUID,
        reference: str,
        *,
        exclude_debit_note_id: uuid.UUID | None = None,
    ) -> bool:
        query = self.db.query(SupplierDebitNote.id).filter(
            SupplierDebitNote.organization_id == organization_id,
            SupplierDebitNote.supplier_id == supplier_id,
            func.lower(SupplierDebitNote.supplier_credit_reference)
            == reference.strip().lower(),
        )
        if exclude_debit_note_id is not None:
            query = query.filter(
                SupplierDebitNote.id != exclude_debit_note_id
            )
        return query.first() is not None

    def create_debit_note(
        self,
        debit_note: SupplierDebitNote,
    ) -> SupplierDebitNote:
        self.db.add(debit_note)
        self.db.flush()
        return debit_note

    def update_debit_note(
        self,
        debit_note: SupplierDebitNote,
    ) -> SupplierDebitNote:
        self.db.add(debit_note)
        self.db.flush()
        return debit_note

    def get_debit_note(
        self,
        organization_id: uuid.UUID,
        debit_note_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierDebitNote | None:
        query = (
            self.db.query(SupplierDebitNote)
            .options(*self._debit_note_options())
            .populate_existing()
            .filter(
                SupplierDebitNote.id == debit_note_id,
                SupplierDebitNote.organization_id == organization_id,
            )
        )
        if for_update:
            query = query.with_for_update(of=SupplierDebitNote)
        return query.first()

    def list_debit_notes(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        supplier_id: uuid.UUID | None,
        status_filter: str | None,
        search: str | None,
    ) -> list[SupplierDebitNote]:
        query = (
            self.db.query(SupplierDebitNote)
            .options(*self._debit_note_options())
            .filter(
                SupplierDebitNote.organization_id == organization_id
            )
        )
        if supplier_id is not None:
            query = query.filter(
                SupplierDebitNote.supplier_id == supplier_id
            )
        if status_filter:
            query = query.filter(
                SupplierDebitNote.status == status_filter
            )
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    SupplierDebitNote.debit_note_number.ilike(pattern),
                    SupplierDebitNote.supplier_credit_reference.ilike(
                        pattern
                    ),
                    SupplierDebitNote.reason.ilike(pattern),
                )
            )
        return (
            query.order_by(
                SupplierDebitNote.note_date.desc(),
                SupplierDebitNote.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_debit_notes(
        self,
        organization_id: uuid.UUID,
        *,
        supplier_id: uuid.UUID | None,
        status_filter: str | None,
        search: str | None,
    ) -> int:
        query = self.db.query(func.count(SupplierDebitNote.id)).filter(
            SupplierDebitNote.organization_id == organization_id
        )
        if supplier_id is not None:
            query = query.filter(
                SupplierDebitNote.supplier_id == supplier_id
            )
        if status_filter:
            query = query.filter(
                SupplierDebitNote.status == status_filter
            )
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    SupplierDebitNote.debit_note_number.ilike(pattern),
                    SupplierDebitNote.supplier_credit_reference.ilike(
                        pattern
                    ),
                    SupplierDebitNote.reason.ilike(pattern),
                )
            )
        return int(query.scalar() or 0)

    def get_debit_note_line(
        self,
        organization_id: uuid.UUID,
        debit_note_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierDebitNoteLineItem | None:
        query = (
            self.db.query(SupplierDebitNoteLineItem)
            .join(
                SupplierDebitNote,
                SupplierDebitNote.id
                == SupplierDebitNoteLineItem.supplier_debit_note_id,
            )
            .filter(
                SupplierDebitNote.organization_id == organization_id,
                SupplierDebitNote.id == debit_note_id,
                SupplierDebitNoteLineItem.id == line_item_id,
            )
        )
        if for_update:
            query = query.with_for_update(
                of=SupplierDebitNoteLineItem
            )
        return query.first()

    def next_debit_note_line_position(
        self,
        debit_note_id: uuid.UUID,
    ) -> int:
        highest = (
            self.db.query(func.max(SupplierDebitNoteLineItem.position))
            .filter(
                SupplierDebitNoteLineItem.supplier_debit_note_id
                == debit_note_id
            )
            .scalar()
        )
        return int(highest or -1) + 1

    def add_debit_note_line(
        self,
        line_item: SupplierDebitNoteLineItem,
    ) -> SupplierDebitNoteLineItem:
        self.db.add(line_item)
        self.db.flush()
        return line_item

    def update_debit_note_line(
        self,
        line_item: SupplierDebitNoteLineItem,
    ) -> SupplierDebitNoteLineItem:
        self.db.add(line_item)
        self.db.flush()
        return line_item

    def delete_debit_note_line(
        self,
        line_item: SupplierDebitNoteLineItem,
    ) -> None:
        self.db.delete(line_item)
        self.db.flush()

    def get_supplier_bill_line(
        self,
        organization_id: uuid.UUID,
        line_item_id: uuid.UUID,
    ) -> SupplierBillLineItem | None:
        return (
            self.db.query(SupplierBillLineItem)
            .join(
                SupplierBill,
                SupplierBill.id
                == SupplierBillLineItem.supplier_bill_id,
            )
            .filter(
                SupplierBill.organization_id == organization_id,
                SupplierBillLineItem.id == line_item_id,
            )
            .first()
        )

    def active_settlement_total(
        self,
        debit_note_id: uuid.UUID,
    ) -> Decimal:
        value = (
            self.db.query(
                func.coalesce(
                    func.sum(
                        SupplierCreditSettlement.amount_settled
                    ),
                    Decimal("0.00"),
                )
            )
            .join(
                SupplierPayment,
                SupplierPayment.id
                == SupplierCreditSettlement.supplier_payment_id,
            )
            .filter(
                SupplierCreditSettlement.supplier_debit_note_id
                == debit_note_id,
                SupplierPayment.status == "posted",
            )
            .scalar()
        )
        return Decimal(value or 0)

    def next_settlement_position(
        self,
        debit_note_id: uuid.UUID,
    ) -> int:
        highest = (
            self.db.query(func.max(SupplierCreditSettlement.position))
            .filter(
                SupplierCreditSettlement.supplier_debit_note_id
                == debit_note_id
            )
            .scalar()
        )
        return int(highest or -1) + 1

    def create_settlement(
        self,
        settlement: SupplierCreditSettlement,
    ) -> SupplierCreditSettlement:
        self.db.add(settlement)
        self.db.flush()
        return settlement

    def get_settlement(
        self,
        organization_id: uuid.UUID,
        debit_note_id: uuid.UUID,
        settlement_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierCreditSettlement | None:
        query = (
            self.db.query(SupplierCreditSettlement)
            .options(
                joinedload(SupplierCreditSettlement.supplier_payment)
            )
            .join(
                SupplierDebitNote,
                SupplierDebitNote.id
                == SupplierCreditSettlement.supplier_debit_note_id,
            )
            .filter(
                SupplierCreditSettlement.id == settlement_id,
                SupplierCreditSettlement.supplier_debit_note_id
                == debit_note_id,
                SupplierCreditSettlement.organization_id
                == organization_id,
                SupplierDebitNote.organization_id == organization_id,
            )
        )
        if for_update:
            query = query.with_for_update(
                of=SupplierCreditSettlement
            )
        return query.first()
