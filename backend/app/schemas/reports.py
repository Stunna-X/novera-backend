"""
Report schemas.

Defines response models for organization reports.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ReportCountItem(BaseModel):
    """
    One grouped count in a report.
    """

    key: str
    label: str
    count: int = Field(
        ge=0,
    )


class ReportMoneyItem(BaseModel):
    """
    One currency-denominated report total.
    """

    currency: str
    amount: Decimal


class ReportPaymentMethodTotal(BaseModel):
    """
    Payment total grouped by method and currency.
    """

    payment_method: str
    currency: str
    amount: Decimal


class BaseReportResponse(BaseModel):
    """
    Common report response fields.
    """

    organization_id: uuid.UUID
    generated_at: datetime
    date_from: date | None = None
    date_to: date | None = None


class OperationsReportResponse(BaseReportResponse):
    """
    Operational performance report.
    """

    work_order_status_counts: list[ReportCountItem] = Field(
        default_factory=list,
    )
    work_order_priority_counts: list[ReportCountItem] = Field(
        default_factory=list,
    )
    closeout_status_counts: list[ReportCountItem] = Field(
        default_factory=list,
    )

    scheduled_work_orders: int = Field(
        ge=0,
    )
    completed_work_orders: int = Field(
        ge=0,
    )
    cancelled_work_orders: int = Field(
        ge=0,
    )
    overdue_scheduled_work_orders: int = Field(
        ge=0,
    )
    invoice_ready_closeouts: int = Field(
        ge=0,
    )

    active_workforce_assignments: int = Field(
        ge=0,
    )
    active_asset_assignments: int = Field(
        ge=0,
    )


class FinanceReportResponse(BaseReportResponse):
    """
    Financial report.
    """

    invoice_status_counts: list[ReportCountItem] = Field(
        default_factory=list,
    )
    total_invoiced: list[ReportMoneyItem] = Field(
        default_factory=list,
    )
    total_paid: list[ReportMoneyItem] = Field(
        default_factory=list,
    )
    total_outstanding: list[ReportMoneyItem] = Field(
        default_factory=list,
    )
    payment_method_totals: list[ReportPaymentMethodTotal] = Field(
        default_factory=list,
    )


class WorkOrderPerformanceReportResponse(BaseReportResponse):
    """
    Work-order performance report.
    """

    total_work_orders: int = Field(
        ge=0,
    )
    completed_work_orders: int = Field(
        ge=0,
    )
    cancelled_work_orders: int = Field(
        ge=0,
    )
    completion_rate_percent: Decimal
    average_completion_hours: Decimal | None = None

    status_counts: list[ReportCountItem] = Field(
        default_factory=list,
    )
    priority_counts: list[ReportCountItem] = Field(
        default_factory=list,
    )
    job_type_counts: list[ReportCountItem] = Field(
        default_factory=list,
    )


class QuoteConversionReportResponse(BaseReportResponse):
    """
    Quote conversion and quote value report.
    """

    total_quotes: int = Field(
        ge=0,
    )
    sent_quotes: int = Field(
        ge=0,
    )
    accepted_quotes: int = Field(
        ge=0,
    )
    rejected_quotes: int = Field(
        ge=0,
    )
    expired_quotes: int = Field(
        ge=0,
    )
    converted_quotes: int = Field(
        ge=0,
    )
    conversion_rate_percent: Decimal

    quote_status_counts: list[ReportCountItem] = Field(
        default_factory=list,
    )
    total_quote_value: list[ReportMoneyItem] = Field(
        default_factory=list,
    )
    accepted_quote_value: list[ReportMoneyItem] = Field(
        default_factory=list,
    )
    converted_quote_value: list[ReportMoneyItem] = Field(
        default_factory=list,
    )
