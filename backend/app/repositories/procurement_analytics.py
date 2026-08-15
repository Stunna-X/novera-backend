"""Organization-scoped procurement reporting queries."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.goods_receipt import GoodsReceipt, GoodsReceiptLineItem
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLineItem
from app.models.purchase_requisition import PurchaseRequisition
from app.models.supplier import Supplier
from app.models.supplier_bill import (
    SupplierBill,
    SupplierBillLineItem,
    SupplierBillMatchResult,
)
from app.models.supplier_payment import (
    SupplierPayment,
    SupplierPaymentAllocation,
)


@dataclass(frozen=True)
class CurrencyAmountRecord:
    currency: str
    amount: Decimal


@dataclass(frozen=True)
class SupplierSpendRecord:
    supplier_id: uuid.UUID
    supplier_code: str
    supplier_name: str
    currency: str
    bill_count: int
    payment_count: int
    billed_amount: Decimal
    paid_amount: Decimal
    outstanding_amount: Decimal


@dataclass(frozen=True)
class PurchaseOrderCommitmentRecord:
    purchase_order_id: uuid.UUID
    purchase_order_number: str
    supplier_id: uuid.UUID
    supplier_name: str
    status: str
    issue_date: date | None
    expected_delivery_date: date | None
    currency: str
    ordered_amount: Decimal
    billed_amount: Decimal
    open_commitment: Decimal


@dataclass(frozen=True)
class AccountsPayableRecord:
    supplier_bill_id: uuid.UUID
    supplier_bill_number: str
    supplier_invoice_number: str
    supplier_id: uuid.UUID
    supplier_name: str
    purchase_order_id: uuid.UUID
    invoice_date: date
    due_date: date | None
    currency: str
    total_amount: Decimal
    amount_paid: Decimal
    balance_due: Decimal


@dataclass(frozen=True)
class MatchExceptionRecord:
    match_result: SupplierBillMatchResult
    bill: SupplierBill
    line: SupplierBillLineItem
    supplier: Supplier


@dataclass(frozen=True)
class ReceiptVarianceRecord:
    receipt: GoodsReceipt
    line: GoodsReceiptLineItem
    purchase_order: PurchaseOrder
    supplier: Supplier


@dataclass(frozen=True)
class PaymentHistoryRecord:
    payment: SupplierPayment
    supplier: Supplier
    allocated_amount: Decimal
    allocation_count: int


class ProcurementAnalyticsRepository:
    """Read-only reporting queries scoped to one organization."""

    ACTIVE_PURCHASE_ORDER_STATUSES = (
        "issued",
        "acknowledged",
        "partially_received",
    )

    def __init__(self, db: Session):
        self.db = db

    def _posted_allocation_subquery(self):
        return (
            self.db.query(
                SupplierPaymentAllocation.supplier_bill_id.label(
                    "supplier_bill_id"
                ),
                func.coalesce(
                    func.sum(SupplierPaymentAllocation.amount_allocated),
                    Decimal("0.00"),
                ).label("amount_paid"),
            )
            .join(
                SupplierPayment,
                SupplierPayment.id
                == SupplierPaymentAllocation.supplier_payment_id,
            )
            .filter(SupplierPayment.status == "posted")
            .group_by(SupplierPaymentAllocation.supplier_bill_id)
            .subquery()
        )

    def overview_counts(
        self,
        organization_id: uuid.UUID,
        *,
        as_of_date: date,
    ) -> dict[str, int]:
        paid = self._posted_allocation_subquery()
        balance = func.greatest(
            SupplierBill.total_amount
            - func.coalesce(paid.c.amount_paid, Decimal("0.00")),
            Decimal("0.00"),
        )

        return {
            "open_requisitions": int(
                self.db.query(func.count(PurchaseRequisition.id))
                .filter(
                    PurchaseRequisition.organization_id == organization_id,
                    PurchaseRequisition.is_active.is_(True),
                    PurchaseRequisition.status.in_(("draft", "submitted")),
                )
                .scalar()
                or 0
            ),
            "active_purchase_orders": int(
                self.db.query(func.count(PurchaseOrder.id))
                .filter(
                    PurchaseOrder.organization_id == organization_id,
                    PurchaseOrder.is_active.is_(True),
                    PurchaseOrder.status.in_(
                        self.ACTIVE_PURCHASE_ORDER_STATUSES
                    ),
                )
                .scalar()
                or 0
            ),
            "posted_goods_receipts": int(
                self.db.query(func.count(GoodsReceipt.id))
                .filter(
                    GoodsReceipt.organization_id == organization_id,
                    GoodsReceipt.is_active.is_(True),
                    GoodsReceipt.status == "posted",
                )
                .scalar()
                or 0
            ),
            "bills_awaiting_approval": int(
                self.db.query(func.count(SupplierBill.id))
                .filter(
                    SupplierBill.organization_id == organization_id,
                    SupplierBill.is_active.is_(True),
                    SupplierBill.status.in_(
                        ("submitted", "matched", "exception")
                    ),
                )
                .scalar()
                or 0
            ),
            "match_exception_count": int(
                self.db.query(func.count(SupplierBillMatchResult.id))
                .join(
                    SupplierBill,
                    SupplierBill.id
                    == SupplierBillMatchResult.supplier_bill_id,
                )
                .filter(
                    SupplierBill.organization_id == organization_id,
                    SupplierBill.is_active.is_(True),
                    SupplierBill.status != "voided",
                    SupplierBillMatchResult.status == "exception",
                )
                .scalar()
                or 0
            ),
            "overdue_bill_count": int(
                self.db.query(func.count(SupplierBill.id))
                .outerjoin(
                    paid,
                    paid.c.supplier_bill_id == SupplierBill.id,
                )
                .filter(
                    SupplierBill.organization_id == organization_id,
                    SupplierBill.is_active.is_(True),
                    SupplierBill.status == "approved",
                    SupplierBill.due_date.is_not(None),
                    SupplierBill.due_date < as_of_date,
                    balance > Decimal("0.00"),
                )
                .scalar()
                or 0
            ),
        }

    def open_commitments(
        self,
        organization_id: uuid.UUID,
    ) -> list[CurrencyAmountRecord]:
        rows = (
            self.db.query(
                PurchaseOrder.currency,
                func.coalesce(
                    func.sum(PurchaseOrder.total_amount),
                    Decimal("0.00"),
                ),
            )
            .filter(
                PurchaseOrder.organization_id == organization_id,
                PurchaseOrder.is_active.is_(True),
                PurchaseOrder.status.in_(
                    self.ACTIVE_PURCHASE_ORDER_STATUSES
                ),
            )
            .group_by(PurchaseOrder.currency)
            .order_by(PurchaseOrder.currency.asc())
            .all()
        )
        return [
            CurrencyAmountRecord(str(currency), Decimal(amount or 0))
            for currency, amount in rows
        ]

    def outstanding_payables(
        self,
        organization_id: uuid.UUID,
    ) -> list[CurrencyAmountRecord]:
        paid = self._posted_allocation_subquery()
        balance = func.greatest(
            SupplierBill.total_amount
            - func.coalesce(paid.c.amount_paid, Decimal("0.00")),
            Decimal("0.00"),
        )
        rows = (
            self.db.query(
                SupplierBill.currency,
                func.coalesce(func.sum(balance), Decimal("0.00")),
            )
            .outerjoin(
                paid,
                paid.c.supplier_bill_id == SupplierBill.id,
            )
            .filter(
                SupplierBill.organization_id == organization_id,
                SupplierBill.is_active.is_(True),
                SupplierBill.status == "approved",
            )
            .group_by(SupplierBill.currency)
            .having(func.sum(balance) > Decimal("0.00"))
            .order_by(SupplierBill.currency.asc())
            .all()
        )
        return [
            CurrencyAmountRecord(str(currency), Decimal(amount or 0))
            for currency, amount in rows
        ]

    def payments_in_period(
        self,
        organization_id: uuid.UUID,
        *,
        date_from: date,
        date_to: date,
    ) -> list[CurrencyAmountRecord]:
        rows = (
            self.db.query(
                SupplierPayment.currency,
                func.coalesce(
                    func.sum(SupplierPayment.total_amount),
                    Decimal("0.00"),
                ),
            )
            .filter(
                SupplierPayment.organization_id == organization_id,
                SupplierPayment.status == "posted",
                SupplierPayment.payment_date >= date_from,
                SupplierPayment.payment_date <= date_to,
            )
            .group_by(SupplierPayment.currency)
            .order_by(SupplierPayment.currency.asc())
            .all()
        )
        return [
            CurrencyAmountRecord(str(currency), Decimal(amount or 0))
            for currency, amount in rows
        ]

    def supplier_spend(
        self,
        organization_id: uuid.UUID,
        *,
        date_from: date,
        date_to: date,
        supplier_id: uuid.UUID | None,
        currency: str | None,
        limit: int,
    ) -> list[SupplierSpendRecord]:
        paid = self._posted_allocation_subquery()
        balance = func.greatest(
            SupplierBill.total_amount
            - func.coalesce(paid.c.amount_paid, Decimal("0.00")),
            Decimal("0.00"),
        )
        payment_count = (
            self.db.query(
                SupplierPayment.supplier_id.label("supplier_id"),
                SupplierPayment.currency.label("currency"),
                func.count(SupplierPayment.id).label("payment_count"),
                func.sum(SupplierPayment.total_amount).label("paid_amount"),
            )
            .filter(
                SupplierPayment.organization_id == organization_id,
                SupplierPayment.status == "posted",
                SupplierPayment.payment_date >= date_from,
                SupplierPayment.payment_date <= date_to,
            )
            .group_by(
                SupplierPayment.supplier_id,
                SupplierPayment.currency,
            )
            .subquery()
        )
        query = (
            self.db.query(
                Supplier.id,
                Supplier.code,
                Supplier.name,
                SupplierBill.currency,
                func.count(SupplierBill.id),
                func.coalesce(
                    func.sum(SupplierBill.total_amount),
                    Decimal("0.00"),
                ),
                func.coalesce(
                    func.sum(balance),
                    Decimal("0.00"),
                ),
                func.coalesce(payment_count.c.payment_count, 0),
                func.coalesce(
                    payment_count.c.paid_amount,
                    Decimal("0.00"),
                ),
            )
            .join(Supplier, Supplier.id == SupplierBill.supplier_id)
            .outerjoin(
                paid,
                paid.c.supplier_bill_id == SupplierBill.id,
            )
            .outerjoin(
                payment_count,
                (payment_count.c.supplier_id == Supplier.id)
                & (payment_count.c.currency == SupplierBill.currency),
            )
            .filter(
                SupplierBill.organization_id == organization_id,
                Supplier.organization_id == organization_id,
                SupplierBill.is_active.is_(True),
                SupplierBill.status != "voided",
                SupplierBill.invoice_date >= date_from,
                SupplierBill.invoice_date <= date_to,
            )
        )
        if supplier_id is not None:
            query = query.filter(Supplier.id == supplier_id)
        if currency is not None:
            query = query.filter(SupplierBill.currency == currency)
        rows = (
            query.group_by(
                Supplier.id,
                Supplier.code,
                Supplier.name,
                SupplierBill.currency,
                payment_count.c.payment_count,
                payment_count.c.paid_amount,
            )
            .order_by(
                func.sum(SupplierBill.total_amount).desc(),
                Supplier.name.asc(),
            )
            .limit(limit)
            .all()
        )
        return [
            SupplierSpendRecord(
                supplier_id=row[0],
                supplier_code=str(row[1]),
                supplier_name=str(row[2]),
                currency=str(row[3]),
                bill_count=int(row[4] or 0),
                billed_amount=Decimal(row[5] or 0),
                outstanding_amount=Decimal(row[6] or 0),
                payment_count=int(row[7] or 0),
                paid_amount=Decimal(row[8] or 0),
            )
            for row in rows
        ]

    def purchase_order_commitments(
        self,
        organization_id: uuid.UUID,
        *,
        supplier_id: uuid.UUID | None,
        currency: str | None,
        limit: int,
    ) -> list[PurchaseOrderCommitmentRecord]:
        billed = (
            self.db.query(
                SupplierBill.purchase_order_id.label("purchase_order_id"),
                func.sum(SupplierBill.total_amount).label("billed_amount"),
            )
            .filter(
                SupplierBill.organization_id == organization_id,
                SupplierBill.is_active.is_(True),
                SupplierBill.status != "voided",
            )
            .group_by(SupplierBill.purchase_order_id)
            .subquery()
        )
        billed_amount = func.coalesce(
            billed.c.billed_amount,
            Decimal("0.00"),
        )
        open_commitment = func.greatest(
            PurchaseOrder.total_amount - billed_amount,
            Decimal("0.00"),
        )
        query = (
            self.db.query(
                PurchaseOrder.id,
                PurchaseOrder.purchase_order_number,
                PurchaseOrder.supplier_id,
                PurchaseOrder.supplier_name,
                PurchaseOrder.status,
                PurchaseOrder.issue_date,
                PurchaseOrder.expected_delivery_date,
                PurchaseOrder.currency,
                PurchaseOrder.total_amount,
                billed_amount,
                open_commitment,
            )
            .outerjoin(
                billed,
                billed.c.purchase_order_id == PurchaseOrder.id,
            )
            .filter(
                PurchaseOrder.organization_id == organization_id,
                PurchaseOrder.is_active.is_(True),
                PurchaseOrder.status.in_(
                    self.ACTIVE_PURCHASE_ORDER_STATUSES
                ),
                open_commitment > Decimal("0.00"),
            )
        )
        if supplier_id is not None:
            query = query.filter(
                PurchaseOrder.supplier_id == supplier_id
            )
        if currency is not None:
            query = query.filter(PurchaseOrder.currency == currency)
        rows = (
            query.order_by(
                PurchaseOrder.expected_delivery_date.asc().nullslast(),
                PurchaseOrder.created_at.desc(),
            )
            .limit(limit)
            .all()
        )
        return [PurchaseOrderCommitmentRecord(*row) for row in rows]

    def accounts_payable(
        self,
        organization_id: uuid.UUID,
        *,
        as_of_date: date,
        supplier_id: uuid.UUID | None,
        currency: str | None,
        overdue_only: bool,
        limit: int,
    ) -> list[AccountsPayableRecord]:
        paid = self._posted_allocation_subquery()
        amount_paid = func.coalesce(
            paid.c.amount_paid,
            Decimal("0.00"),
        )
        balance = func.greatest(
            SupplierBill.total_amount - amount_paid,
            Decimal("0.00"),
        )
        query = (
            self.db.query(
                SupplierBill.id,
                SupplierBill.supplier_bill_number,
                SupplierBill.supplier_invoice_number,
                SupplierBill.supplier_id,
                Supplier.name,
                SupplierBill.purchase_order_id,
                SupplierBill.invoice_date,
                SupplierBill.due_date,
                SupplierBill.currency,
                SupplierBill.total_amount,
                amount_paid,
                balance,
            )
            .join(Supplier, Supplier.id == SupplierBill.supplier_id)
            .outerjoin(
                paid,
                paid.c.supplier_bill_id == SupplierBill.id,
            )
            .filter(
                SupplierBill.organization_id == organization_id,
                Supplier.organization_id == organization_id,
                SupplierBill.is_active.is_(True),
                SupplierBill.status == "approved",
                balance > Decimal("0.00"),
            )
        )
        if supplier_id is not None:
            query = query.filter(SupplierBill.supplier_id == supplier_id)
        if currency is not None:
            query = query.filter(SupplierBill.currency == currency)
        if overdue_only:
            query = query.filter(
                SupplierBill.due_date.is_not(None),
                SupplierBill.due_date < as_of_date,
            )
        rows = (
            query.order_by(
                SupplierBill.due_date.asc().nullslast(),
                SupplierBill.invoice_date.asc(),
            )
            .limit(limit)
            .all()
        )
        return [AccountsPayableRecord(*row) for row in rows]

    def match_exceptions(
        self,
        organization_id: uuid.UUID,
        *,
        date_from: date,
        date_to: date,
        supplier_id: uuid.UUID | None,
        limit: int,
    ) -> list[MatchExceptionRecord]:
        query = (
            self.db.query(
                SupplierBillMatchResult,
                SupplierBill,
                SupplierBillLineItem,
                Supplier,
            )
            .join(
                SupplierBill,
                SupplierBill.id
                == SupplierBillMatchResult.supplier_bill_id,
            )
            .join(
                SupplierBillLineItem,
                SupplierBillLineItem.id
                == SupplierBillMatchResult.supplier_bill_line_item_id,
            )
            .join(Supplier, Supplier.id == SupplierBill.supplier_id)
            .filter(
                SupplierBill.organization_id == organization_id,
                Supplier.organization_id == organization_id,
                SupplierBill.is_active.is_(True),
                SupplierBill.status != "voided",
                SupplierBillMatchResult.status == "exception",
                func.date(SupplierBillMatchResult.evaluated_at)
                >= date_from,
                func.date(SupplierBillMatchResult.evaluated_at)
                <= date_to,
            )
        )
        if supplier_id is not None:
            query = query.filter(SupplierBill.supplier_id == supplier_id)
        rows = (
            query.order_by(
                SupplierBillMatchResult.evaluated_at.desc(),
                SupplierBillLineItem.position.asc(),
            )
            .limit(limit)
            .all()
        )
        return [MatchExceptionRecord(*row) for row in rows]

    def receipt_variances(
        self,
        organization_id: uuid.UUID,
        *,
        date_from: date,
        date_to: date,
        supplier_id: uuid.UUID | None,
        limit: int,
    ) -> list[ReceiptVarianceRecord]:
        delivered = (
            GoodsReceiptLineItem.quantity_accepted
            + GoodsReceiptLineItem.quantity_rejected
            + GoodsReceiptLineItem.quantity_damaged
        )
        query = (
            self.db.query(
                GoodsReceipt,
                GoodsReceiptLineItem,
                PurchaseOrder,
                Supplier,
            )
            .join(
                GoodsReceiptLineItem,
                GoodsReceiptLineItem.goods_receipt_id == GoodsReceipt.id,
            )
            .join(
                PurchaseOrder,
                PurchaseOrder.id == GoodsReceipt.purchase_order_id,
            )
            .join(Supplier, Supplier.id == GoodsReceipt.supplier_id)
            .filter(
                GoodsReceipt.organization_id == organization_id,
                PurchaseOrder.organization_id == organization_id,
                Supplier.organization_id == organization_id,
                GoodsReceipt.is_active.is_(True),
                GoodsReceipt.status == "posted",
                GoodsReceipt.received_at.is_not(None),
                func.date(GoodsReceipt.received_at) >= date_from,
                func.date(GoodsReceipt.received_at) <= date_to,
                delivered > Decimal("0.000"),
                (
                    GoodsReceiptLineItem.quantity_rejected
                    + GoodsReceiptLineItem.quantity_damaged
                )
                > Decimal("0.000"),
            )
        )
        if supplier_id is not None:
            query = query.filter(GoodsReceipt.supplier_id == supplier_id)
        rows = (
            query.order_by(
                GoodsReceipt.received_at.desc(),
                GoodsReceiptLineItem.position.asc(),
            )
            .limit(limit)
            .all()
        )
        return [ReceiptVarianceRecord(*row) for row in rows]

    def payment_history(
        self,
        organization_id: uuid.UUID,
        *,
        date_from: date,
        date_to: date,
        supplier_id: uuid.UUID | None,
        currency: str | None,
        include_reversed: bool,
        limit: int,
    ) -> list[PaymentHistoryRecord]:
        query = (
            self.db.query(
                SupplierPayment,
                Supplier,
                func.coalesce(
                    func.sum(SupplierPaymentAllocation.amount_allocated),
                    Decimal("0.00"),
                ),
                func.count(SupplierPaymentAllocation.id),
            )
            .join(Supplier, Supplier.id == SupplierPayment.supplier_id)
            .outerjoin(
                SupplierPaymentAllocation,
                SupplierPaymentAllocation.supplier_payment_id
                == SupplierPayment.id,
            )
            .filter(
                SupplierPayment.organization_id == organization_id,
                Supplier.organization_id == organization_id,
                SupplierPayment.payment_date >= date_from,
                SupplierPayment.payment_date <= date_to,
            )
        )
        if supplier_id is not None:
            query = query.filter(
                SupplierPayment.supplier_id == supplier_id
            )
        if currency is not None:
            query = query.filter(SupplierPayment.currency == currency)
        if not include_reversed:
            query = query.filter(SupplierPayment.status == "posted")
        rows = (
            query.group_by(SupplierPayment.id, Supplier.id)
            .order_by(
                SupplierPayment.payment_date.desc(),
                SupplierPayment.created_at.desc(),
            )
            .limit(limit)
            .all()
        )
        return [
            PaymentHistoryRecord(
                payment=row[0],
                supplier=row[1],
                allocated_amount=Decimal(row[2] or 0),
                allocation_count=int(row[3] or 0),
            )
            for row in rows
        ]
