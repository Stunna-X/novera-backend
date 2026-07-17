"""
Reports service.

Builds organization-scoped operational, financial, work-order,
and quote conversion reports.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoicePayment
from app.models.quote import Quote
from app.models.work_order import (
    WorkOrder,
    WorkOrderAssetAssignment,
    WorkOrderWorkforceAssignment,
)
from app.models.work_order_closeout import WorkOrderCloseout
from app.schemas.reports import (
    FinanceReportResponse,
    OperationsReportResponse,
    QuoteConversionReportResponse,
    ReportCountItem,
    ReportMoneyItem,
    ReportPaymentMethodTotal,
    WorkOrderPerformanceReportResponse,
)


ACTIVE_WORK_ORDER_STATUSES = [
    "draft",
    "scheduled",
    "dispatched",
    "in_progress",
    "on_hold",
]

WORK_ORDER_STATUSES = [
    "draft",
    "scheduled",
    "dispatched",
    "in_progress",
    "on_hold",
    "completed",
    "cancelled",
]

WORK_ORDER_PRIORITIES = [
    "low",
    "normal",
    "high",
    "urgent",
]

QUOTE_STATUSES = [
    "draft",
    "sent",
    "accepted",
    "rejected",
    "expired",
    "converted",
]

INVOICE_STATUSES = [
    "draft",
    "issued",
    "partially_paid",
    "paid",
    "void",
]

CLOSEOUT_STATUSES = [
    "submitted",
    "approved",
    "rejected",
]


class ReportsService:
    """
    Builds business reports for one organization.
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def get_operations_report(
        self,
        *,
        organization_id: uuid.UUID,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> OperationsReportResponse:
        """
        Return an operations report.
        """

        work_order_status_counts = self._named_counts(
            self._work_order_group_counts(
                organization_id=organization_id,
                group_column=WorkOrder.status,
                date_column=WorkOrder.created_at,
                date_from=date_from,
                date_to=date_to,
            ),
            WORK_ORDER_STATUSES,
        )

        work_order_priority_counts = self._named_counts(
            self._work_order_group_counts(
                organization_id=organization_id,
                group_column=WorkOrder.priority,
                date_column=WorkOrder.created_at,
                date_from=date_from,
                date_to=date_to,
            ),
            WORK_ORDER_PRIORITIES,
        )

        closeout_status_counts = self._named_counts(
            self._closeout_group_counts(
                organization_id=organization_id,
                group_column=WorkOrderCloseout.status,
                date_column=WorkOrderCloseout.created_at,
                date_from=date_from,
                date_to=date_to,
            ),
            CLOSEOUT_STATUSES,
        )

        return OperationsReportResponse(
            organization_id=organization_id,
            generated_at=self._now(),
            date_from=date_from,
            date_to=date_to,
            work_order_status_counts=work_order_status_counts,
            work_order_priority_counts=work_order_priority_counts,
            closeout_status_counts=closeout_status_counts,
            scheduled_work_orders=self._work_order_count(
                organization_id=organization_id,
                statuses=["scheduled"],
                date_from=date_from,
                date_to=date_to,
            ),
            completed_work_orders=self._work_order_count(
                organization_id=organization_id,
                statuses=["completed"],
                date_from=date_from,
                date_to=date_to,
            ),
            cancelled_work_orders=self._work_order_count(
                organization_id=organization_id,
                statuses=["cancelled"],
                date_from=date_from,
                date_to=date_to,
            ),
            overdue_scheduled_work_orders=(
                self._overdue_scheduled_work_order_count(
                    organization_id=organization_id,
                )
            ),
            invoice_ready_closeouts=self._invoice_ready_closeout_count(
                organization_id=organization_id,
                date_from=date_from,
                date_to=date_to,
            ),
            active_workforce_assignments=(
                self._active_workforce_assignment_count(
                    organization_id=organization_id,
                )
            ),
            active_asset_assignments=self._active_asset_assignment_count(
                organization_id=organization_id,
            ),
        )

    def get_finance_report(
        self,
        *,
        organization_id: uuid.UUID,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> FinanceReportResponse:
        """
        Return a finance report.
        """

        invoice_status_counts = self._named_counts(
            self._invoice_group_counts(
                organization_id=organization_id,
                group_column=Invoice.status,
                date_column=Invoice.invoice_date,
                date_from=date_from,
                date_to=date_to,
            ),
            INVOICE_STATUSES,
        )

        return FinanceReportResponse(
            organization_id=organization_id,
            generated_at=self._now(),
            date_from=date_from,
            date_to=date_to,
            invoice_status_counts=invoice_status_counts,
            total_invoiced=self._invoice_money_by_currency(
                organization_id=organization_id,
                amount_column=Invoice.total_amount,
                date_from=date_from,
                date_to=date_to,
                statuses=["issued", "partially_paid", "paid"],
            ),
            total_paid=self._invoice_money_by_currency(
                organization_id=organization_id,
                amount_column=Invoice.amount_paid,
                date_from=date_from,
                date_to=date_to,
                statuses=["partially_paid", "paid"],
            ),
            total_outstanding=self._invoice_money_by_currency(
                organization_id=organization_id,
                amount_column=Invoice.balance_due,
                date_from=date_from,
                date_to=date_to,
                statuses=["issued", "partially_paid"],
            ),
            payment_method_totals=self._payment_method_totals(
                organization_id=organization_id,
                date_from=date_from,
                date_to=date_to,
            ),
        )

    def get_work_order_performance_report(
        self,
        *,
        organization_id: uuid.UUID,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> WorkOrderPerformanceReportResponse:
        """
        Return a work-order performance report.
        """

        total = self._work_order_count(
            organization_id=organization_id,
            statuses=None,
            date_from=date_from,
            date_to=date_to,
        )

        completed = self._work_order_count(
            organization_id=organization_id,
            statuses=["completed"],
            date_from=date_from,
            date_to=date_to,
        )

        cancelled = self._work_order_count(
            organization_id=organization_id,
            statuses=["cancelled"],
            date_from=date_from,
            date_to=date_to,
        )

        completion_rate = Decimal("0.00")
        if total:
            completion_rate = (
                Decimal(completed)
                / Decimal(total)
                * Decimal("100")
            ).quantize(
                Decimal("0.01")
            )

        return WorkOrderPerformanceReportResponse(
            organization_id=organization_id,
            generated_at=self._now(),
            date_from=date_from,
            date_to=date_to,
            total_work_orders=total,
            completed_work_orders=completed,
            cancelled_work_orders=cancelled,
            completion_rate_percent=completion_rate,
            average_completion_hours=self._average_completion_hours(
                organization_id=organization_id,
                date_from=date_from,
                date_to=date_to,
            ),
            status_counts=self._named_counts(
                self._work_order_group_counts(
                    organization_id=organization_id,
                    group_column=WorkOrder.status,
                    date_column=WorkOrder.created_at,
                    date_from=date_from,
                    date_to=date_to,
                ),
                WORK_ORDER_STATUSES,
            ),
            priority_counts=self._named_counts(
                self._work_order_group_counts(
                    organization_id=organization_id,
                    group_column=WorkOrder.priority,
                    date_column=WorkOrder.created_at,
                    date_from=date_from,
                    date_to=date_to,
                ),
                WORK_ORDER_PRIORITIES,
            ),
            job_type_counts=self._job_type_counts(
                organization_id=organization_id,
                date_from=date_from,
                date_to=date_to,
            ),
        )

    def get_quote_conversion_report(
        self,
        *,
        organization_id: uuid.UUID,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> QuoteConversionReportResponse:
        """
        Return a quote conversion report.
        """

        counts = self._quote_group_counts(
            organization_id=organization_id,
            group_column=Quote.status,
            date_column=Quote.quote_date,
            date_from=date_from,
            date_to=date_to,
        )

        total = sum(counts.values())
        converted = counts.get("converted", 0)

        conversion_rate = Decimal("0.00")
        if total:
            conversion_rate = (
                Decimal(converted)
                / Decimal(total)
                * Decimal("100")
            ).quantize(
                Decimal("0.01")
            )

        return QuoteConversionReportResponse(
            organization_id=organization_id,
            generated_at=self._now(),
            date_from=date_from,
            date_to=date_to,
            total_quotes=total,
            sent_quotes=counts.get("sent", 0),
            accepted_quotes=counts.get("accepted", 0),
            rejected_quotes=counts.get("rejected", 0),
            expired_quotes=counts.get("expired", 0),
            converted_quotes=converted,
            conversion_rate_percent=conversion_rate,
            quote_status_counts=self._named_counts(
                counts,
                QUOTE_STATUSES,
            ),
            total_quote_value=self._quote_money_by_currency(
                organization_id=organization_id,
                statuses=None,
                date_from=date_from,
                date_to=date_to,
            ),
            accepted_quote_value=self._quote_money_by_currency(
                organization_id=organization_id,
                statuses=["accepted"],
                date_from=date_from,
                date_to=date_to,
            ),
            converted_quote_value=self._quote_money_by_currency(
                organization_id=organization_id,
                statuses=["converted"],
                date_from=date_from,
                date_to=date_to,
            ),
        )

    def _work_order_count(
        self,
        *,
        organization_id: uuid.UUID,
        statuses: list[str] | None,
        date_from: date | None,
        date_to: date | None,
    ) -> int:
        query = self.db.query(
            func.count(WorkOrder.id)
        ).filter(
            WorkOrder.organization_id == organization_id,
            WorkOrder.is_active.is_(True),
        )

        if statuses is not None:
            query = query.filter(
                WorkOrder.status.in_(statuses),
            )

        query = self._filter_datetime_range(
            query=query,
            column=WorkOrder.created_at,
            date_from=date_from,
            date_to=date_to,
        )

        return self._count(query)

    def _overdue_scheduled_work_order_count(
        self,
        *,
        organization_id: uuid.UUID,
    ) -> int:
        now = self._now()

        return self._count(
            self.db.query(
                func.count(WorkOrder.id),
            ).filter(
                WorkOrder.organization_id == organization_id,
                WorkOrder.is_active.is_(True),
                WorkOrder.status.in_(
                    [
                        "scheduled",
                        "dispatched",
                        "in_progress",
                    ]
                ),
                WorkOrder.scheduled_end.is_not(None),
                WorkOrder.scheduled_end < now,
            )
        )

    def _invoice_ready_closeout_count(
        self,
        *,
        organization_id: uuid.UUID,
        date_from: date | None,
        date_to: date | None,
    ) -> int:
        query = self.db.query(
            func.count(WorkOrderCloseout.id),
        ).filter(
            WorkOrderCloseout.organization_id == organization_id,
            WorkOrderCloseout.is_invoice_ready.is_(True),
        )

        query = self._filter_datetime_range(
            query=query,
            column=WorkOrderCloseout.created_at,
            date_from=date_from,
            date_to=date_to,
        )

        return self._count(query)

    def _active_workforce_assignment_count(
        self,
        *,
        organization_id: uuid.UUID,
    ) -> int:
        return self._count(
            self.db.query(
                func.count(
                    func.distinct(
                        WorkOrderWorkforceAssignment.workforce_profile_id
                    )
                )
            )
            .join(
                WorkOrder,
                WorkOrder.id
                == WorkOrderWorkforceAssignment.work_order_id,
            )
            .filter(
                WorkOrder.organization_id == organization_id,
                WorkOrder.is_active.is_(True),
                WorkOrder.status.in_(ACTIVE_WORK_ORDER_STATUSES),
            )
        )

    def _active_asset_assignment_count(
        self,
        *,
        organization_id: uuid.UUID,
    ) -> int:
        return self._count(
            self.db.query(
                func.count(
                    func.distinct(
                        WorkOrderAssetAssignment.asset_id
                    )
                )
            )
            .join(
                WorkOrder,
                WorkOrder.id
                == WorkOrderAssetAssignment.work_order_id,
            )
            .filter(
                WorkOrder.organization_id == organization_id,
                WorkOrder.is_active.is_(True),
                WorkOrder.status.in_(ACTIVE_WORK_ORDER_STATUSES),
            )
        )

    def _average_completion_hours(
        self,
        *,
        organization_id: uuid.UUID,
        date_from: date | None,
        date_to: date | None,
    ) -> Decimal | None:
        query = self.db.query(
            WorkOrder.actual_start,
            WorkOrder.actual_end,
        ).filter(
            WorkOrder.organization_id == organization_id,
            WorkOrder.is_active.is_(True),
            WorkOrder.status == "completed",
            WorkOrder.actual_start.is_not(None),
            WorkOrder.actual_end.is_not(None),
        )

        query = self._filter_datetime_range(
            query=query,
            column=WorkOrder.actual_end,
            date_from=date_from,
            date_to=date_to,
        )

        rows = query.all()

        durations: list[Decimal] = []
        for actual_start, actual_end in rows:
            seconds = (
                actual_end - actual_start
            ).total_seconds()

            if seconds >= 0:
                durations.append(
                    Decimal(str(seconds / 3600))
                )

        if not durations:
            return None

        average = sum(
            durations,
            Decimal("0"),
        ) / Decimal(len(durations))

        return average.quantize(
            Decimal("0.01")
        )

    def _work_order_group_counts(
        self,
        *,
        organization_id: uuid.UUID,
        group_column,
        date_column,
        date_from: date | None,
        date_to: date | None,
    ) -> dict[str, int]:
        query = self.db.query(
            group_column,
            func.count(WorkOrder.id),
        ).filter(
            WorkOrder.organization_id == organization_id,
            WorkOrder.is_active.is_(True),
        )

        query = self._filter_datetime_range(
            query=query,
            column=date_column,
            date_from=date_from,
            date_to=date_to,
        )

        rows = query.group_by(
            group_column,
        ).all()

        return {
            str(key): int(count)
            for key, count in rows
            if key is not None
        }

    def _quote_group_counts(
        self,
        *,
        organization_id: uuid.UUID,
        group_column,
        date_column,
        date_from: date | None,
        date_to: date | None,
    ) -> dict[str, int]:
        query = self.db.query(
            group_column,
            func.count(Quote.id),
        ).filter(
            Quote.organization_id == organization_id,
            Quote.is_active.is_(True),
        )

        query = self._filter_date_range(
            query=query,
            column=date_column,
            date_from=date_from,
            date_to=date_to,
        )

        rows = query.group_by(
            group_column,
        ).all()

        return {
            str(key): int(count)
            for key, count in rows
            if key is not None
        }

    def _invoice_group_counts(
        self,
        *,
        organization_id: uuid.UUID,
        group_column,
        date_column,
        date_from: date | None,
        date_to: date | None,
    ) -> dict[str, int]:
        query = self.db.query(
            group_column,
            func.count(Invoice.id),
        ).filter(
            Invoice.organization_id == organization_id,
            Invoice.is_active.is_(True),
        )

        query = self._filter_date_range(
            query=query,
            column=date_column,
            date_from=date_from,
            date_to=date_to,
        )

        rows = query.group_by(
            group_column,
        ).all()

        return {
            str(key): int(count)
            for key, count in rows
            if key is not None
        }

    def _closeout_group_counts(
        self,
        *,
        organization_id: uuid.UUID,
        group_column,
        date_column,
        date_from: date | None,
        date_to: date | None,
    ) -> dict[str, int]:
        query = self.db.query(
            group_column,
            func.count(WorkOrderCloseout.id),
        ).filter(
            WorkOrderCloseout.organization_id == organization_id,
        )

        query = self._filter_datetime_range(
            query=query,
            column=date_column,
            date_from=date_from,
            date_to=date_to,
        )

        rows = query.group_by(
            group_column,
        ).all()

        return {
            str(key): int(count)
            for key, count in rows
            if key is not None
        }

    def _job_type_counts(
        self,
        *,
        organization_id: uuid.UUID,
        date_from: date | None,
        date_to: date | None,
    ) -> list[ReportCountItem]:
        query = self.db.query(
            WorkOrder.job_type,
            func.count(WorkOrder.id),
        ).filter(
            WorkOrder.organization_id == organization_id,
            WorkOrder.is_active.is_(True),
        )

        query = self._filter_datetime_range(
            query=query,
            column=WorkOrder.created_at,
            date_from=date_from,
            date_to=date_to,
        )

        rows = query.group_by(
            WorkOrder.job_type,
        ).order_by(
            func.count(WorkOrder.id).desc(),
        ).all()

        items: list[ReportCountItem] = []

        for job_type, count in rows:
            key = job_type or "unspecified"
            items.append(
                ReportCountItem(
                    key=key,
                    label=key.replace("_", " ").title(),
                    count=int(count),
                )
            )

        return items

    def _invoice_money_by_currency(
        self,
        *,
        organization_id: uuid.UUID,
        amount_column,
        date_from: date | None,
        date_to: date | None,
        statuses: list[str],
    ) -> list[ReportMoneyItem]:
        query = self.db.query(
            Invoice.currency,
            func.coalesce(
                func.sum(amount_column),
                Decimal("0.00"),
            ),
        ).filter(
            Invoice.organization_id == organization_id,
            Invoice.is_active.is_(True),
            Invoice.status.in_(statuses),
        )

        query = self._filter_date_range(
            query=query,
            column=Invoice.invoice_date,
            date_from=date_from,
            date_to=date_to,
        )

        rows = query.group_by(
            Invoice.currency,
        ).order_by(
            Invoice.currency,
        ).all()

        return [
            ReportMoneyItem(
                currency=currency,
                amount=amount or Decimal("0.00"),
            )
            for currency, amount in rows
        ]

    def _quote_money_by_currency(
        self,
        *,
        organization_id: uuid.UUID,
        statuses: list[str] | None,
        date_from: date | None,
        date_to: date | None,
    ) -> list[ReportMoneyItem]:
        query = self.db.query(
            Quote.currency,
            func.coalesce(
                func.sum(Quote.total_amount),
                Decimal("0.00"),
            ),
        ).filter(
            Quote.organization_id == organization_id,
            Quote.is_active.is_(True),
        )

        if statuses is not None:
            query = query.filter(
                Quote.status.in_(statuses),
            )

        query = self._filter_date_range(
            query=query,
            column=Quote.quote_date,
            date_from=date_from,
            date_to=date_to,
        )

        rows = query.group_by(
            Quote.currency,
        ).order_by(
            Quote.currency,
        ).all()

        return [
            ReportMoneyItem(
                currency=currency,
                amount=amount or Decimal("0.00"),
            )
            for currency, amount in rows
        ]

    def _payment_method_totals(
        self,
        *,
        organization_id: uuid.UUID,
        date_from: date | None,
        date_to: date | None,
    ) -> list[ReportPaymentMethodTotal]:
        query = self.db.query(
            InvoicePayment.payment_method,
            InvoicePayment.currency,
            func.coalesce(
                func.sum(InvoicePayment.amount),
                Decimal("0.00"),
            ),
        ).join(
            Invoice,
            Invoice.id == InvoicePayment.invoice_id,
        ).filter(
            Invoice.organization_id == organization_id,
            InvoicePayment.is_reversed.is_(False),
        )

        query = self._filter_date_range(
            query=query,
            column=InvoicePayment.payment_date,
            date_from=date_from,
            date_to=date_to,
        )

        rows = query.group_by(
            InvoicePayment.payment_method,
            InvoicePayment.currency,
        ).order_by(
            InvoicePayment.payment_method,
            InvoicePayment.currency,
        ).all()

        return [
            ReportPaymentMethodTotal(
                payment_method=payment_method,
                currency=currency,
                amount=amount or Decimal("0.00"),
            )
            for payment_method, currency, amount in rows
        ]

    def _named_counts(
        self,
        counts: dict[str, int],
        keys: list[str],
    ) -> list[ReportCountItem]:
        items: list[ReportCountItem] = []

        seen: set[str] = set()

        for key in keys:
            items.append(
                ReportCountItem(
                    key=key,
                    label=key.replace("_", " ").title(),
                    count=counts.get(key, 0),
                )
            )
            seen.add(key)

        for key in sorted(counts):
            if key in seen:
                continue

            items.append(
                ReportCountItem(
                    key=key,
                    label=key.replace("_", " ").title(),
                    count=counts[key],
                )
            )

        return items

    def _filter_date_range(
        self,
        *,
        query,
        column,
        date_from: date | None,
        date_to: date | None,
    ):
        if date_from is not None:
            query = query.filter(
                column >= date_from,
            )

        if date_to is not None:
            query = query.filter(
                column <= date_to,
            )

        return query

    def _filter_datetime_range(
        self,
        *,
        query,
        column,
        date_from: date | None,
        date_to: date | None,
    ):
        if date_from is not None:
            query = query.filter(
                func.date(column) >= date_from,
            )

        if date_to is not None:
            query = query.filter(
                func.date(column) <= date_to,
            )

        return query

    def _count(
        self,
        query,
    ) -> int:
        value = query.scalar()
        return int(value or 0)

    def _now(
        self,
    ) -> datetime:
        return datetime.now(UTC)
