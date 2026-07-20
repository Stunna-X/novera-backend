"""
Dashboard schemas.

Defines response models for operational, commercial, finance,
team, and asset dashboard analytics.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class DashboardCountMetric(BaseModel):
    """
    Simple count grouped by a label such as status or priority.
    """

    label: str
    count: int = Field(ge=0)


class DashboardCurrencyMetric(BaseModel):
    """
    Currency-scoped monetary dashboard metric.
    """

    currency: str
    amount: Decimal = Field(ge=0)


class DashboardWorkOrderItem(BaseModel):
    """
    Compact work-order item for dashboard lists.
    """

    id: uuid.UUID
    work_order_number: str
    title: str
    customer_id: uuid.UUID
    customer_site_id: uuid.UUID | None
    job_type: str | None
    priority: str
    status: str
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    estimated_cost: Decimal | None
    actual_cost: Decimal | None
    workforce_profile_ids: list[uuid.UUID] = Field(
        default_factory=list,
    )
    asset_ids: list[uuid.UUID] = Field(
        default_factory=list,
    )


class DashboardOverviewResponse(BaseModel):
    """
    High-level organization dashboard summary.
    """

    organization_id: uuid.UUID
    generated_at: datetime

    active_work_orders: int = Field(ge=0)
    scheduled_work_orders: int = Field(ge=0)
    dispatched_work_orders: int = Field(ge=0)
    in_progress_work_orders: int = Field(ge=0)
    completed_work_orders: int = Field(ge=0)
    overdue_scheduled_work_orders: int = Field(ge=0)

    open_quotes: int = Field(ge=0)
    accepted_quotes: int = Field(ge=0)
    converted_quotes: int = Field(ge=0)

    submitted_closeouts: int = Field(ge=0)
    approved_closeouts: int = Field(ge=0)
    invoice_ready_closeouts: int = Field(ge=0)

    draft_invoices: int = Field(ge=0)
    issued_invoices: int = Field(ge=0)
    partially_paid_invoices: int = Field(ge=0)
    paid_invoices: int = Field(ge=0)

    outstanding_balances: list[
        DashboardCurrencyMetric
    ] = Field(default_factory=list)


class DashboardWorkOrdersResponse(BaseModel):
    """
    Work-order analytics and dashboard lists.
    """

    organization_id: uuid.UUID
    generated_at: datetime

    status_counts: list[
        DashboardCountMetric
    ] = Field(default_factory=list)

    priority_counts: list[
        DashboardCountMetric
    ] = Field(default_factory=list)

    upcoming_work_orders: list[
        DashboardWorkOrderItem
    ] = Field(default_factory=list)

    recently_completed_work_orders: list[
        DashboardWorkOrderItem
    ] = Field(default_factory=list)


class DashboardFinanceResponse(BaseModel):
    """
    Commercial and invoice analytics.
    """

    organization_id: uuid.UUID
    generated_at: datetime

    invoice_status_counts: list[
        DashboardCountMetric
    ] = Field(default_factory=list)

    quote_status_counts: list[
        DashboardCountMetric
    ] = Field(default_factory=list)

    total_invoiced: list[
        DashboardCurrencyMetric
    ] = Field(default_factory=list)

    total_paid: list[
        DashboardCurrencyMetric
    ] = Field(default_factory=list)

    total_outstanding: list[
        DashboardCurrencyMetric
    ] = Field(default_factory=list)

    accepted_quote_value: list[
        DashboardCurrencyMetric
    ] = Field(default_factory=list)

    converted_quote_value: list[
        DashboardCurrencyMetric
    ] = Field(default_factory=list)


class DashboardTeamMemberMetric(BaseModel):
    """
    Workforce dashboard workload item.
    """

    workforce_profile_id: uuid.UUID
    membership_id: uuid.UUID
    user_id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    role_name: str
    job_title: str | None
    status: str
    is_available: bool
    open_assignment_count: int = Field(ge=0)
    completed_assignment_count: int = Field(ge=0)


class DashboardAssetMetric(BaseModel):
    """
    Asset dashboard usage item.
    """

    asset_id: uuid.UUID
    asset_code: str
    name: str
    asset_type: str
    status: str
    condition: str
    open_assignment_count: int = Field(ge=0)


class DashboardTeamResponse(BaseModel):
    """
    Team and asset workload dashboard response.
    """

    organization_id: uuid.UUID
    generated_at: datetime

    active_workforce_count: int = Field(ge=0)
    available_workforce_count: int = Field(ge=0)
    active_asset_count: int = Field(ge=0)
    available_asset_count: int = Field(ge=0)

    workforce: list[
        DashboardTeamMemberMetric
    ] = Field(default_factory=list)

    assets: list[
        DashboardAssetMetric
    ] = Field(default_factory=list)
