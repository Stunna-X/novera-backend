"""Application service for procurement reporting and spend analytics."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.procurement_analytics import (
    ProcurementAnalyticsRepository,
)
from app.schemas.procurement_analytics import (
    AccountsPayableItem,
    AccountsPayableResponse,
    MatchExceptionItem,
    MatchExceptionResponse,
    PaymentHistoryItem,
    PaymentHistoryResponse,
    ProcurementCurrencyAmount,
    ProcurementOverviewResponse,
    ProcurementSettlementStatus,
    PurchaseOrderCommitmentItem,
    PurchaseOrderCommitmentResponse,
    ReceiptVarianceItem,
    ReceiptVarianceResponse,
    SupplierSpendItem,
    SupplierSpendResponse,
)


class ProcurementAnalyticsService:
    """Build organization-scoped procurement reporting responses."""

    DEFAULT_WINDOW_DAYS = 30
    MAX_WINDOW_DAYS = 366
    PERCENT_QUANTUM = Decimal("0.0001")

    def __init__(
        self,
        db: Session,
        *,
        repository: ProcurementAnalyticsRepository | None = None,
    ):
        self.db = db
        self.repository = repository or ProcurementAnalyticsRepository(db)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def normalize_date_range(
        cls,
        date_from: date | None,
        date_to: date | None,
    ) -> tuple[date, date]:
        resolved_to = date_to or date.today()
        resolved_from = date_from or (
            resolved_to - timedelta(days=cls.DEFAULT_WINDOW_DAYS - 1)
        )
        if resolved_from > resolved_to:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="date_from must not be after date_to.",
            )
        if (resolved_to - resolved_from).days + 1 > cls.MAX_WINDOW_DAYS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Procurement reporting ranges may not exceed "
                    f"{cls.MAX_WINDOW_DAYS} days."
                ),
            )
        return resolved_from, resolved_to

    @staticmethod
    def normalize_currency(currency: str | None) -> str | None:
        if currency is None:
            return None
        normalized = currency.strip().upper()
        if len(normalized) != 3:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="currency must contain exactly three characters.",
            )
        return normalized

    @staticmethod
    def settlement_status(
        *,
        total_amount: Decimal,
        amount_paid: Decimal,
        due_date: date | None,
        as_of_date: date,
    ) -> ProcurementSettlementStatus:
        balance = max(total_amount - amount_paid, Decimal("0.00"))
        if balance == 0:
            return ProcurementSettlementStatus.PAID
        if due_date is not None and due_date < as_of_date:
            return ProcurementSettlementStatus.OVERDUE
        if amount_paid > 0:
            return ProcurementSettlementStatus.PARTIALLY_PAID
        return ProcurementSettlementStatus.UNPAID

    @classmethod
    def exception_rate(
        cls,
        *,
        rejected: Decimal,
        damaged: Decimal,
        total_delivered: Decimal,
    ) -> Decimal:
        if total_delivered <= 0:
            return Decimal("0.0000")
        return (
            ((rejected + damaged) / total_delivered) * Decimal("100")
        ).quantize(cls.PERCENT_QUANTUM, rounding=ROUND_HALF_UP)

    def get_overview(
        self,
        organization_id: uuid.UUID,
        *,
        as_of_date: date | None = None,
        payment_date_from: date | None = None,
        payment_date_to: date | None = None,
    ) -> ProcurementOverviewResponse:
        resolved_as_of = as_of_date or date.today()
        resolved_from, resolved_to = self.normalize_date_range(
            payment_date_from,
            payment_date_to or resolved_as_of,
        )
        counts = self.repository.overview_counts(
            organization_id,
            as_of_date=resolved_as_of,
        )
        return ProcurementOverviewResponse(
            organization_id=organization_id,
            generated_at=self._now(),
            as_of_date=resolved_as_of,
            **counts,
            open_commitments=[
                ProcurementCurrencyAmount(
                    currency=row.currency,
                    amount=row.amount,
                )
                for row in self.repository.open_commitments(
                    organization_id
                )
            ],
            outstanding_payables=[
                ProcurementCurrencyAmount(
                    currency=row.currency,
                    amount=row.amount,
                )
                for row in self.repository.outstanding_payables(
                    organization_id
                )
            ],
            payments_in_period=[
                ProcurementCurrencyAmount(
                    currency=row.currency,
                    amount=row.amount,
                )
                for row in self.repository.payments_in_period(
                    organization_id,
                    date_from=resolved_from,
                    date_to=resolved_to,
                )
            ],
        )

    def get_supplier_spend(
        self,
        organization_id: uuid.UUID,
        *,
        date_from: date | None,
        date_to: date | None,
        supplier_id: uuid.UUID | None,
        currency: str | None,
        limit: int,
    ) -> SupplierSpendResponse:
        resolved_from, resolved_to = self.normalize_date_range(
            date_from,
            date_to,
        )
        normalized_currency = self.normalize_currency(currency)
        rows = self.repository.supplier_spend(
            organization_id,
            date_from=resolved_from,
            date_to=resolved_to,
            supplier_id=supplier_id,
            currency=normalized_currency,
            limit=limit,
        )
        return SupplierSpendResponse(
            organization_id=organization_id,
            generated_at=self._now(),
            date_from=resolved_from,
            date_to=resolved_to,
            items=[SupplierSpendItem(**row.__dict__) for row in rows],
        )

    def get_commitments(
        self,
        organization_id: uuid.UUID,
        *,
        supplier_id: uuid.UUID | None,
        currency: str | None,
        limit: int,
    ) -> PurchaseOrderCommitmentResponse:
        rows = self.repository.purchase_order_commitments(
            organization_id,
            supplier_id=supplier_id,
            currency=self.normalize_currency(currency),
            limit=limit,
        )
        return PurchaseOrderCommitmentResponse(
            organization_id=organization_id,
            generated_at=self._now(),
            items=[
                PurchaseOrderCommitmentItem(**row.__dict__)
                for row in rows
            ],
            total=len(rows),
            limit=limit,
        )

    def get_payables(
        self,
        organization_id: uuid.UUID,
        *,
        as_of_date: date | None,
        supplier_id: uuid.UUID | None,
        currency: str | None,
        overdue_only: bool,
        limit: int,
    ) -> AccountsPayableResponse:
        resolved_as_of = as_of_date or date.today()
        rows = self.repository.accounts_payable(
            organization_id,
            as_of_date=resolved_as_of,
            supplier_id=supplier_id,
            currency=self.normalize_currency(currency),
            overdue_only=overdue_only,
            limit=limit,
        )
        items: list[AccountsPayableItem] = []
        for row in rows:
            balance = max(row.balance_due, Decimal("0.00"))
            is_overdue = (
                row.due_date is not None
                and row.due_date < resolved_as_of
                and balance > 0
            )
            items.append(
                AccountsPayableItem(
                    supplier_bill_id=row.supplier_bill_id,
                    supplier_bill_number=row.supplier_bill_number,
                    supplier_invoice_number=(
                        row.supplier_invoice_number
                    ),
                    supplier_id=row.supplier_id,
                    supplier_name=row.supplier_name,
                    purchase_order_id=row.purchase_order_id,
                    invoice_date=row.invoice_date,
                    due_date=row.due_date,
                    currency=row.currency,
                    total_amount=row.total_amount,
                    amount_paid=row.amount_paid,
                    balance_due=balance,
                    settlement_status=self.settlement_status(
                        total_amount=row.total_amount,
                        amount_paid=row.amount_paid,
                        due_date=row.due_date,
                        as_of_date=resolved_as_of,
                    ),
                    is_overdue=is_overdue,
                )
            )
        return AccountsPayableResponse(
            organization_id=organization_id,
            generated_at=self._now(),
            as_of_date=resolved_as_of,
            items=items,
            total=len(items),
            limit=limit,
        )

    def get_match_exceptions(
        self,
        organization_id: uuid.UUID,
        *,
        date_from: date | None,
        date_to: date | None,
        supplier_id: uuid.UUID | None,
        limit: int,
    ) -> MatchExceptionResponse:
        resolved_from, resolved_to = self.normalize_date_range(
            date_from,
            date_to,
        )
        rows = self.repository.match_exceptions(
            organization_id,
            date_from=resolved_from,
            date_to=resolved_to,
            supplier_id=supplier_id,
            limit=limit,
        )
        items = [
            MatchExceptionItem(
                match_result_id=row.match_result.id,
                supplier_bill_id=row.bill.id,
                supplier_bill_number=row.bill.supplier_bill_number,
                supplier_invoice_number=row.bill.supplier_invoice_number,
                supplier_id=row.bill.supplier_id,
                supplier_name=row.supplier.name,
                purchase_order_id=row.bill.purchase_order_id,
                purchase_order_line_item_id=(
                    row.match_result.purchase_order_line_item_id
                ),
                description=row.line.description,
                currency=row.bill.currency,
                quantity_ordered=row.match_result.quantity_ordered,
                quantity_received=row.match_result.quantity_received,
                quantity_billed=row.match_result.quantity_billed,
                purchase_order_unit_price=(
                    row.match_result.purchase_order_unit_price
                ),
                supplier_bill_unit_price=(
                    row.match_result.supplier_bill_unit_price
                ),
                quantity_variance=row.match_result.quantity_variance,
                unit_price_variance=row.match_result.unit_price_variance,
                quantity_variance_percent=(
                    row.match_result.quantity_variance_percent
                ),
                unit_price_variance_percent=(
                    row.match_result.unit_price_variance_percent
                ),
                reasons=list(row.match_result.reasons or []),
                evaluated_at=row.match_result.evaluated_at,
            )
            for row in rows
        ]
        return MatchExceptionResponse(
            organization_id=organization_id,
            generated_at=self._now(),
            date_from=resolved_from,
            date_to=resolved_to,
            items=items,
            total=len(items),
            limit=limit,
        )

    def get_receipt_variances(
        self,
        organization_id: uuid.UUID,
        *,
        date_from: date | None,
        date_to: date | None,
        supplier_id: uuid.UUID | None,
        limit: int,
    ) -> ReceiptVarianceResponse:
        resolved_from, resolved_to = self.normalize_date_range(
            date_from,
            date_to,
        )
        rows = self.repository.receipt_variances(
            organization_id,
            date_from=resolved_from,
            date_to=resolved_to,
            supplier_id=supplier_id,
            limit=limit,
        )
        items: list[ReceiptVarianceItem] = []
        for row in rows:
            total_delivered = (
                row.line.quantity_accepted
                + row.line.quantity_rejected
                + row.line.quantity_damaged
            )
            items.append(
                ReceiptVarianceItem(
                    goods_receipt_id=row.receipt.id,
                    goods_receipt_number=(
                        row.receipt.goods_receipt_number
                    ),
                    purchase_order_id=row.purchase_order.id,
                    purchase_order_number=(
                        row.purchase_order.purchase_order_number
                    ),
                    supplier_id=row.supplier.id,
                    supplier_name=row.supplier.name,
                    purchase_order_line_item_id=(
                        row.line.purchase_order_line_item_id
                    ),
                    inventory_item_id=row.line.inventory_item_id,
                    description=row.line.description,
                    received_at=row.receipt.received_at,
                    quantity_accepted=row.line.quantity_accepted,
                    quantity_rejected=row.line.quantity_rejected,
                    quantity_damaged=row.line.quantity_damaged,
                    total_delivered=total_delivered,
                    exception_rate_percent=self.exception_rate(
                        rejected=row.line.quantity_rejected,
                        damaged=row.line.quantity_damaged,
                        total_delivered=total_delivered,
                    ),
                    rejection_reason=row.line.rejection_reason,
                    damage_notes=row.line.damage_notes,
                )
            )
        return ReceiptVarianceResponse(
            organization_id=organization_id,
            generated_at=self._now(),
            date_from=resolved_from,
            date_to=resolved_to,
            items=items,
            total=len(items),
            limit=limit,
        )

    def get_payment_history(
        self,
        organization_id: uuid.UUID,
        *,
        date_from: date | None,
        date_to: date | None,
        supplier_id: uuid.UUID | None,
        currency: str | None,
        include_reversed: bool,
        limit: int,
    ) -> PaymentHistoryResponse:
        resolved_from, resolved_to = self.normalize_date_range(
            date_from,
            date_to,
        )
        rows = self.repository.payment_history(
            organization_id,
            date_from=resolved_from,
            date_to=resolved_to,
            supplier_id=supplier_id,
            currency=self.normalize_currency(currency),
            include_reversed=include_reversed,
            limit=limit,
        )
        return PaymentHistoryResponse(
            organization_id=organization_id,
            generated_at=self._now(),
            date_from=resolved_from,
            date_to=resolved_to,
            items=[
                PaymentHistoryItem(
                    supplier_payment_id=row.payment.id,
                    payment_number=row.payment.payment_number,
                    supplier_id=row.payment.supplier_id,
                    supplier_name=row.supplier.name,
                    payment_date=row.payment.payment_date,
                    payment_method=row.payment.payment_method,
                    currency=row.payment.currency,
                    total_amount=row.payment.total_amount,
                    allocated_amount=row.allocated_amount,
                    allocation_count=row.allocation_count,
                    reference_number=row.payment.reference_number,
                    status=row.payment.status,
                    reversed_at=row.payment.reversed_at,
                    reversal_reason=row.payment.reversal_reason,
                )
                for row in rows
            ],
            total=len(rows),
            limit=limit,
        )
