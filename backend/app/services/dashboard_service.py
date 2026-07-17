"""
Dashboard service.

Builds organization-scoped analytics for work orders, quotes,
invoices, closeouts, workforce, and assets.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.asset import Asset
from app.models.invoice import Invoice
from app.models.membership import Membership
from app.models.quote import Quote
from app.models.work_order import (
    WorkOrder,
    WorkOrderAssetAssignment,
    WorkOrderWorkforceAssignment,
)
from app.models.work_order_closeout import WorkOrderCloseout
from app.models.workforce_profile import WorkforceProfile
from app.schemas.dashboard import (
    DashboardAssetMetric,
    DashboardCountMetric,
    DashboardCurrencyMetric,
    DashboardFinanceResponse,
    DashboardOverviewResponse,
    DashboardTeamMemberMetric,
    DashboardTeamResponse,
    DashboardWorkOrderItem,
    DashboardWorkOrdersResponse,
)


class DashboardService:
    """
    Provides organization dashboard analytics.
    """

    ACTIVE_WORK_ORDER_STATUSES = {
        "draft",
        "scheduled",
        "dispatched",
        "in_progress",
        "on_hold",
    }

    BILLABLE_INVOICE_STATUSES = {
        "issued",
        "partially_paid",
        "paid",
    }

    OUTSTANDING_INVOICE_STATUSES = {
        "issued",
        "partially_paid",
    }

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    @staticmethod
    def _now() -> datetime:
        """
        Return the current timezone-aware UTC timestamp.
        """

        return datetime.now(timezone.utc)

    @staticmethod
    def _count_metric_rows(
        rows: list[tuple[str, int]],
    ) -> list[DashboardCountMetric]:
        """
        Convert grouped count rows into response metrics.
        """

        return [
            DashboardCountMetric(
                label=str(label),
                count=int(count or 0),
            )
            for label, count in rows
        ]

    @staticmethod
    def _currency_metric_rows(
        rows: list[tuple[str, object]],
    ) -> list[DashboardCurrencyMetric]:
        """
        Convert grouped currency rows into response metrics.
        """

        return [
            DashboardCurrencyMetric(
                currency=str(currency).upper(),
                amount=Decimal(amount or 0),
            )
            for currency, amount in rows
        ]

    def _count_work_orders(
        self,
        organization_id: uuid.UUID,
        *,
        status_filter: str | None = None,
        statuses: set[str] | None = None,
    ) -> int:
        """
        Count active organization work orders.
        """

        query = self.db.query(
            func.count(WorkOrder.id)
        ).filter(
            WorkOrder.organization_id == organization_id,
            WorkOrder.is_active.is_(True),
        )

        if status_filter is not None:
            query = query.filter(
                WorkOrder.status == status_filter
            )

        if statuses is not None:
            query = query.filter(
                WorkOrder.status.in_(statuses)
            )

        return int(query.scalar() or 0)

    def _count_quotes(
        self,
        organization_id: uuid.UUID,
        *,
        status_filter: str | None = None,
        statuses: set[str] | None = None,
    ) -> int:
        """
        Count active organization quotes.
        """

        query = self.db.query(
            func.count(Quote.id)
        ).filter(
            Quote.organization_id == organization_id,
            Quote.is_active.is_(True),
        )

        if status_filter is not None:
            query = query.filter(
                Quote.status == status_filter
            )

        if statuses is not None:
            query = query.filter(
                Quote.status.in_(statuses)
            )

        return int(query.scalar() or 0)

    def _count_invoices(
        self,
        organization_id: uuid.UUID,
        status_filter: str,
    ) -> int:
        """
        Count active organization invoices by status.
        """

        return int(
            self.db.query(
                func.count(Invoice.id)
            )
            .filter(
                Invoice.organization_id == organization_id,
                Invoice.is_active.is_(True),
                Invoice.status == status_filter,
            )
            .scalar()
            or 0
        )

    def _count_closeouts(
        self,
        organization_id: uuid.UUID,
        *,
        status_filter: str | None = None,
        invoice_ready: bool | None = None,
    ) -> int:
        """
        Count organization closeouts.
        """

        query = self.db.query(
            func.count(WorkOrderCloseout.id)
        ).filter(
            WorkOrderCloseout.organization_id
            == organization_id
        )

        if status_filter is not None:
            query = query.filter(
                WorkOrderCloseout.status == status_filter
            )

        if invoice_ready is not None:
            query = query.filter(
                WorkOrderCloseout.is_invoice_ready.is_(
                    invoice_ready
                )
            )

        return int(query.scalar() or 0)

    @staticmethod
    def _work_order_item(
        work_order: WorkOrder,
    ) -> DashboardWorkOrderItem:
        """
        Convert a work order into a compact dashboard item.
        """

        return DashboardWorkOrderItem(
            id=work_order.id,
            work_order_number=work_order.work_order_number,
            title=work_order.title,
            customer_id=work_order.customer_id,
            customer_site_id=work_order.customer_site_id,
            job_type=work_order.job_type,
            priority=work_order.priority,
            status=work_order.status,
            scheduled_start=work_order.scheduled_start,
            scheduled_end=work_order.scheduled_end,
            actual_start=work_order.actual_start,
            actual_end=work_order.actual_end,
            estimated_cost=work_order.estimated_cost,
            actual_cost=work_order.actual_cost,
            workforce_profile_ids=[
                assignment.workforce_profile_id
                for assignment
                in work_order.workforce_assignments
            ],
            asset_ids=[
                assignment.asset_id
                for assignment
                in work_order.asset_assignments
            ],
        )

    def get_overview(
        self,
        organization_id: uuid.UUID,
    ) -> DashboardOverviewResponse:
        """
        Return high-level operational and finance summary.
        """

        now = self._now()

        overdue_scheduled = int(
            self.db.query(
                func.count(WorkOrder.id)
            )
            .filter(
                WorkOrder.organization_id == organization_id,
                WorkOrder.is_active.is_(True),
                WorkOrder.status.in_(
                    {"scheduled", "dispatched"}
                ),
                WorkOrder.scheduled_end.is_not(None),
                WorkOrder.scheduled_end < now,
            )
            .scalar()
            or 0
        )

        outstanding_rows = (
            self.db.query(
                Invoice.currency,
                func.coalesce(
                    func.sum(Invoice.balance_due),
                    Decimal("0.00"),
                ),
            )
            .filter(
                Invoice.organization_id == organization_id,
                Invoice.is_active.is_(True),
                Invoice.status.in_(
                    self.OUTSTANDING_INVOICE_STATUSES
                ),
            )
            .group_by(Invoice.currency)
            .order_by(Invoice.currency.asc())
            .all()
        )

        return DashboardOverviewResponse(
            organization_id=organization_id,
            generated_at=now,
            active_work_orders=self._count_work_orders(
                organization_id,
                statuses=self.ACTIVE_WORK_ORDER_STATUSES,
            ),
            scheduled_work_orders=self._count_work_orders(
                organization_id,
                status_filter="scheduled",
            ),
            dispatched_work_orders=self._count_work_orders(
                organization_id,
                status_filter="dispatched",
            ),
            in_progress_work_orders=self._count_work_orders(
                organization_id,
                status_filter="in_progress",
            ),
            completed_work_orders=self._count_work_orders(
                organization_id,
                status_filter="completed",
            ),
            overdue_scheduled_work_orders=overdue_scheduled,
            open_quotes=self._count_quotes(
                organization_id,
                statuses={"draft", "sent"},
            ),
            accepted_quotes=self._count_quotes(
                organization_id,
                status_filter="accepted",
            ),
            converted_quotes=self._count_quotes(
                organization_id,
                status_filter="converted",
            ),
            submitted_closeouts=self._count_closeouts(
                organization_id,
                status_filter="submitted",
            ),
            approved_closeouts=self._count_closeouts(
                organization_id,
                status_filter="approved",
            ),
            invoice_ready_closeouts=self._count_closeouts(
                organization_id,
                invoice_ready=True,
            ),
            draft_invoices=self._count_invoices(
                organization_id,
                "draft",
            ),
            issued_invoices=self._count_invoices(
                organization_id,
                "issued",
            ),
            partially_paid_invoices=self._count_invoices(
                organization_id,
                "partially_paid",
            ),
            paid_invoices=self._count_invoices(
                organization_id,
                "paid",
            ),
            outstanding_balances=self._currency_metric_rows(
                outstanding_rows
            ),
        )

    def get_work_orders(
        self,
        organization_id: uuid.UUID,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 10,
    ) -> DashboardWorkOrdersResponse:
        """
        Return work-order status, priority, upcoming, and completion analytics.
        """

        now = self._now()

        base_filters = [
            WorkOrder.organization_id == organization_id,
            WorkOrder.is_active.is_(True),
        ]

        status_rows = (
            self.db.query(
                WorkOrder.status,
                func.count(WorkOrder.id),
            )
            .filter(*base_filters)
            .group_by(WorkOrder.status)
            .order_by(WorkOrder.status.asc())
            .all()
        )

        priority_rows = (
            self.db.query(
                WorkOrder.priority,
                func.count(WorkOrder.id),
            )
            .filter(*base_filters)
            .group_by(WorkOrder.priority)
            .order_by(WorkOrder.priority.asc())
            .all()
        )

        upcoming_query = (
            self.db.query(WorkOrder)
            .options(
                selectinload(
                    WorkOrder.workforce_assignments
                ),
                selectinload(
                    WorkOrder.asset_assignments
                ),
            )
            .filter(
                *base_filters,
                WorkOrder.status.in_(
                    {
                        "scheduled",
                        "dispatched",
                        "in_progress",
                    }
                ),
                WorkOrder.scheduled_start.is_not(None),
            )
        )

        if start is not None:
            upcoming_query = upcoming_query.filter(
                or_(
                    WorkOrder.scheduled_end.is_(None),
                    WorkOrder.scheduled_end >= start,
                )
            )

        if end is not None:
            upcoming_query = upcoming_query.filter(
                WorkOrder.scheduled_start <= end
            )

        if start is None and end is None:
            upcoming_query = upcoming_query.filter(
                WorkOrder.scheduled_start >= now
            )

        upcoming = (
            upcoming_query.order_by(
                WorkOrder.scheduled_start.asc()
            )
            .limit(limit)
            .all()
        )

        recently_completed = (
            self.db.query(WorkOrder)
            .options(
                selectinload(
                    WorkOrder.workforce_assignments
                ),
                selectinload(
                    WorkOrder.asset_assignments
                ),
            )
            .filter(
                *base_filters,
                WorkOrder.status == "completed",
            )
            .order_by(
                WorkOrder.actual_end.desc().nullslast(),
                WorkOrder.updated_at.desc(),
            )
            .limit(limit)
            .all()
        )

        return DashboardWorkOrdersResponse(
            organization_id=organization_id,
            generated_at=now,
            status_counts=self._count_metric_rows(
                status_rows
            ),
            priority_counts=self._count_metric_rows(
                priority_rows
            ),
            upcoming_work_orders=[
                self._work_order_item(work_order)
                for work_order in upcoming
            ],
            recently_completed_work_orders=[
                self._work_order_item(work_order)
                for work_order in recently_completed
            ],
        )

    def get_finance(
        self,
        organization_id: uuid.UUID,
    ) -> DashboardFinanceResponse:
        """
        Return invoice and quote financial analytics.
        """

        now = self._now()

        invoice_status_rows = (
            self.db.query(
                Invoice.status,
                func.count(Invoice.id),
            )
            .filter(
                Invoice.organization_id == organization_id,
                Invoice.is_active.is_(True),
            )
            .group_by(Invoice.status)
            .order_by(Invoice.status.asc())
            .all()
        )

        quote_status_rows = (
            self.db.query(
                Quote.status,
                func.count(Quote.id),
            )
            .filter(
                Quote.organization_id == organization_id,
                Quote.is_active.is_(True),
            )
            .group_by(Quote.status)
            .order_by(Quote.status.asc())
            .all()
        )

        total_invoiced_rows = (
            self.db.query(
                Invoice.currency,
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Invoice.status.in_(
                                    self.BILLABLE_INVOICE_STATUSES
                                ),
                                Invoice.total_amount,
                            ),
                            else_=Decimal("0.00"),
                        )
                    ),
                    Decimal("0.00"),
                ),
            )
            .filter(
                Invoice.organization_id == organization_id,
                Invoice.is_active.is_(True),
            )
            .group_by(Invoice.currency)
            .order_by(Invoice.currency.asc())
            .all()
        )

        total_paid_rows = (
            self.db.query(
                Invoice.currency,
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Invoice.status.in_(
                                    self.BILLABLE_INVOICE_STATUSES
                                ),
                                Invoice.amount_paid,
                            ),
                            else_=Decimal("0.00"),
                        )
                    ),
                    Decimal("0.00"),
                ),
            )
            .filter(
                Invoice.organization_id == organization_id,
                Invoice.is_active.is_(True),
            )
            .group_by(Invoice.currency)
            .order_by(Invoice.currency.asc())
            .all()
        )

        outstanding_rows = (
            self.db.query(
                Invoice.currency,
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Invoice.status.in_(
                                    self.OUTSTANDING_INVOICE_STATUSES
                                ),
                                Invoice.balance_due,
                            ),
                            else_=Decimal("0.00"),
                        )
                    ),
                    Decimal("0.00"),
                ),
            )
            .filter(
                Invoice.organization_id == organization_id,
                Invoice.is_active.is_(True),
            )
            .group_by(Invoice.currency)
            .order_by(Invoice.currency.asc())
            .all()
        )

        accepted_quote_rows = (
            self.db.query(
                Quote.currency,
                func.coalesce(
                    func.sum(Quote.total_amount),
                    Decimal("0.00"),
                ),
            )
            .filter(
                Quote.organization_id == organization_id,
                Quote.is_active.is_(True),
                Quote.status == "accepted",
            )
            .group_by(Quote.currency)
            .order_by(Quote.currency.asc())
            .all()
        )

        converted_quote_rows = (
            self.db.query(
                Quote.currency,
                func.coalesce(
                    func.sum(Quote.total_amount),
                    Decimal("0.00"),
                ),
            )
            .filter(
                Quote.organization_id == organization_id,
                Quote.is_active.is_(True),
                Quote.status == "converted",
            )
            .group_by(Quote.currency)
            .order_by(Quote.currency.asc())
            .all()
        )

        return DashboardFinanceResponse(
            organization_id=organization_id,
            generated_at=now,
            invoice_status_counts=self._count_metric_rows(
                invoice_status_rows
            ),
            quote_status_counts=self._count_metric_rows(
                quote_status_rows
            ),
            total_invoiced=self._currency_metric_rows(
                total_invoiced_rows
            ),
            total_paid=self._currency_metric_rows(
                total_paid_rows
            ),
            total_outstanding=self._currency_metric_rows(
                outstanding_rows
            ),
            accepted_quote_value=self._currency_metric_rows(
                accepted_quote_rows
            ),
            converted_quote_value=self._currency_metric_rows(
                converted_quote_rows
            ),
        )

    def get_team(
        self,
        organization_id: uuid.UUID,
        *,
        limit: int = 25,
    ) -> DashboardTeamResponse:
        """
        Return workforce and asset workload analytics.
        """

        now = self._now()
        last_30_days = now - timedelta(days=30)

        active_workforce_count = int(
            self.db.query(
                func.count(WorkforceProfile.id)
            )
            .filter(
                WorkforceProfile.organization_id
                == organization_id,
                WorkforceProfile.is_active.is_(True),
                WorkforceProfile.status == "active",
            )
            .scalar()
            or 0
        )

        available_workforce_count = int(
            self.db.query(
                func.count(WorkforceProfile.id)
            )
            .filter(
                WorkforceProfile.organization_id
                == organization_id,
                WorkforceProfile.is_active.is_(True),
                WorkforceProfile.status == "active",
                WorkforceProfile.is_available.is_(True),
            )
            .scalar()
            or 0
        )

        profiles = (
            self.db.query(WorkforceProfile)
            .options(
                joinedload(
                    WorkforceProfile.membership
                ).joinedload(
                    Membership.user
                ),
                joinedload(
                    WorkforceProfile.membership
                ).joinedload(
                    Membership.role
                ),
            )
            .filter(
                WorkforceProfile.organization_id
                == organization_id,
                WorkforceProfile.is_active.is_(True),
            )
            .order_by(
                WorkforceProfile.is_available.desc(),
                WorkforceProfile.created_at.asc(),
            )
            .limit(limit)
            .all()
        )

        workforce_metrics: list[
            DashboardTeamMemberMetric
        ] = []

        for profile in profiles:
            membership = profile.membership
            user = membership.user
            role = membership.role

            open_assignment_count = int(
                self.db.query(
                    func.count(
                        WorkOrderWorkforceAssignment.id
                    )
                )
                .join(
                    WorkOrder,
                    WorkOrder.id
                    == (
                        WorkOrderWorkforceAssignment
                        .work_order_id
                    ),
                )
                .filter(
                    WorkOrder.organization_id
                    == organization_id,
                    WorkOrder.is_active.is_(True),
                    WorkOrder.status.in_(
                        self.ACTIVE_WORK_ORDER_STATUSES
                    ),
                    (
                        WorkOrderWorkforceAssignment
                        .workforce_profile_id
                    )
                    == profile.id,
                )
                .scalar()
                or 0
            )

            completed_assignment_count = int(
                self.db.query(
                    func.count(
                        WorkOrderWorkforceAssignment.id
                    )
                )
                .join(
                    WorkOrder,
                    WorkOrder.id
                    == (
                        WorkOrderWorkforceAssignment
                        .work_order_id
                    ),
                )
                .filter(
                    WorkOrder.organization_id
                    == organization_id,
                    WorkOrder.is_active.is_(True),
                    WorkOrder.status == "completed",
                    WorkOrder.actual_end.is_not(None),
                    WorkOrder.actual_end >= last_30_days,
                    (
                        WorkOrderWorkforceAssignment
                        .workforce_profile_id
                    )
                    == profile.id,
                )
                .scalar()
                or 0
            )

            workforce_metrics.append(
                DashboardTeamMemberMetric(
                    workforce_profile_id=profile.id,
                    membership_id=profile.membership_id,
                    user_id=membership.user_id,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    email=user.email,
                    role_name=role.name,
                    job_title=profile.job_title,
                    status=profile.status,
                    is_available=profile.is_available,
                    open_assignment_count=(
                        open_assignment_count
                    ),
                    completed_assignment_count=(
                        completed_assignment_count
                    ),
                )
            )

        active_asset_count = int(
            self.db.query(
                func.count(Asset.id)
            )
            .filter(
                Asset.organization_id == organization_id,
                Asset.is_active.is_(True),
            )
            .scalar()
            or 0
        )

        available_asset_count = int(
            self.db.query(
                func.count(Asset.id)
            )
            .filter(
                Asset.organization_id == organization_id,
                Asset.is_active.is_(True),
                Asset.status == "available",
            )
            .scalar()
            or 0
        )

        assets = (
            self.db.query(Asset)
            .filter(
                Asset.organization_id == organization_id,
                Asset.is_active.is_(True),
            )
            .order_by(
                Asset.status.asc(),
                Asset.name.asc(),
            )
            .limit(limit)
            .all()
        )

        asset_metrics: list[DashboardAssetMetric] = []

        for asset in assets:
            open_assignment_count = int(
                self.db.query(
                    func.count(WorkOrderAssetAssignment.id)
                )
                .join(
                    WorkOrder,
                    WorkOrder.id
                    == WorkOrderAssetAssignment.work_order_id,
                )
                .filter(
                    WorkOrder.organization_id
                    == organization_id,
                    WorkOrder.is_active.is_(True),
                    WorkOrder.status.in_(
                        self.ACTIVE_WORK_ORDER_STATUSES
                    ),
                    WorkOrderAssetAssignment.asset_id
                    == asset.id,
                )
                .scalar()
                or 0
            )

            asset_metrics.append(
                DashboardAssetMetric(
                    asset_id=asset.id,
                    asset_code=asset.asset_code,
                    name=asset.name,
                    asset_type=asset.asset_type,
                    status=asset.status,
                    condition=asset.condition,
                    open_assignment_count=(
                        open_assignment_count
                    ),
                )
            )

        return DashboardTeamResponse(
            organization_id=organization_id,
            generated_at=now,
            active_workforce_count=active_workforce_count,
            available_workforce_count=(
                available_workforce_count
            ),
            active_asset_count=active_asset_count,
            available_asset_count=available_asset_count,
            workforce=workforce_metrics,
            assets=asset_metrics,
        )
