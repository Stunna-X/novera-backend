"""
Work-order expense repository.

Contains organization-scoped persistence, filtering, and
aggregate queries for work-order expenses.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.orm import (
    Session,
    joinedload,
)

from app.models.work_order import WorkOrder
from app.models.work_order_expense import WorkOrderExpense
from app.repositories.base import BaseRepository


class WorkOrderExpenseRepository(
    BaseRepository[WorkOrderExpense]
):
    """
    Repository for work-order expense operations.
    """

    def __init__(
        self,
        db: Session,
    ):
        super().__init__(
            db,
            WorkOrderExpense,
        )

    @staticmethod
    def _response_options():
        """
        Return eager-loading options for API responses.
        """

        return (
            joinedload(
                WorkOrderExpense.created_by
            ),
            joinedload(
                WorkOrderExpense.reviewed_by
            ),
        )

    def _base_query(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ):
        """
        Build an organization-scoped expense query.
        """

        query = (
            self.db.query(WorkOrderExpense)
            .join(
                WorkOrder,
                WorkOrder.id
                == WorkOrderExpense.work_order_id,
            )
            .filter(
                WorkOrder.organization_id
                == organization_id,
                WorkOrder.id == work_order_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrder.is_active.is_(True),
                WorkOrderExpense.is_active.is_(True),
            )

        return query

    @staticmethod
    def _apply_filters(
        query,
        *,
        category: str | None = None,
        expense_status: str | None = None,
        currency: str | None = None,
        is_billable: bool | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ):
        """
        Apply reusable work-order expense filters.
        """

        if category is not None:
            query = query.filter(
                WorkOrderExpense.category == category
            )

        if expense_status is not None:
            query = query.filter(
                WorkOrderExpense.status
                == expense_status
            )

        if currency is not None:
            query = query.filter(
                WorkOrderExpense.currency
                == currency.upper()
            )

        if is_billable is not None:
            query = query.filter(
                WorkOrderExpense.is_billable
                == is_billable
            )

        if date_from is not None:
            query = query.filter(
                WorkOrderExpense.expense_date
                >= date_from
            )

        if date_to is not None:
            query = query.filter(
                WorkOrderExpense.expense_date
                <= date_to
            )

        return query

    def get_for_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        expense_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrderExpense | None:
        """
        Retrieve one organization-scoped expense.
        """

        return (
            self._base_query(
                organization_id=organization_id,
                work_order_id=work_order_id,
                include_inactive=include_inactive,
            )
            .options(
                *self._response_options()
            )
            .populate_existing()
            .filter(
                WorkOrderExpense.id == expense_id
            )
            .first()
        )

    def list_for_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        category: str | None = None,
        expense_status: str | None = None,
        currency: str | None = None,
        is_billable: bool | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        include_inactive: bool = False,
    ) -> list[WorkOrderExpense]:
        """
        List filtered expenses belonging to one work order.
        """

        query = (
            self._base_query(
                organization_id=organization_id,
                work_order_id=work_order_id,
                include_inactive=include_inactive,
            )
            .options(
                *self._response_options()
            )
            .populate_existing()
        )

        query = self._apply_filters(
            query,
            category=category,
            expense_status=expense_status,
            currency=currency,
            is_billable=is_billable,
            date_from=date_from,
            date_to=date_to,
        )

        return (
            query.order_by(
                WorkOrderExpense.expense_date.desc(),
                WorkOrderExpense.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        category: str | None = None,
        expense_status: str | None = None,
        currency: str | None = None,
        is_billable: bool | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        include_inactive: bool = False,
    ) -> int:
        """
        Count filtered work-order expenses.
        """

        query = (
            self.db.query(
                func.count(
                    WorkOrderExpense.id
                )
            )
            .join(
                WorkOrder,
                WorkOrder.id
                == WorkOrderExpense.work_order_id,
            )
            .filter(
                WorkOrder.organization_id
                == organization_id,
                WorkOrder.id == work_order_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrder.is_active.is_(True),
                WorkOrderExpense.is_active.is_(True),
            )

        query = self._apply_filters(
            query,
            category=category,
            expense_status=expense_status,
            currency=currency,
            is_billable=is_billable,
            date_from=date_from,
            date_to=date_to,
        )

        return query.scalar() or 0

    def create_expense(
        self,
        expense: WorkOrderExpense,
    ) -> WorkOrderExpense:
        """
        Persist a new work-order expense.
        """

        expense.description = (
            expense.description.strip()
        )

        expense.currency = (
            expense.currency.strip().upper()
        )

        self.db.add(expense)
        self.db.commit()
        self.db.refresh(expense)

        return expense

    def update_expense(
        self,
        expense: WorkOrderExpense,
    ) -> WorkOrderExpense:
        """
        Persist work-order expense changes.
        """

        expense.description = (
            expense.description.strip()
        )

        expense.currency = (
            expense.currency.strip().upper()
        )

        self.db.add(expense)
        self.db.commit()
        self.db.refresh(expense)

        return expense

    def deactivate_expense(
        self,
        expense: WorkOrderExpense,
    ) -> WorkOrderExpense:
        """
        Soft-delete a work-order expense.
        """

        expense.is_active = False

        self.db.add(expense)
        self.db.commit()
        self.db.refresh(expense)

        return expense

    def reactivate_expense(
        self,
        expense: WorkOrderExpense,
    ) -> WorkOrderExpense:
        """
        Reactivate a soft-deleted work-order expense.
        """

        expense.is_active = True

        self.db.add(expense)
        self.db.commit()
        self.db.refresh(expense)

        return expense

    def totals_by_currency(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        include_inactive: bool = False,
    ) -> list[
        tuple[
            str,
            Decimal,
            Decimal,
            Decimal,
            int,
        ]
    ]:
        """
        Aggregate totals, billable totals, and approved totals
        by currency.
        """

        query = (
            self.db.query(
                WorkOrderExpense.currency,
                func.coalesce(
                    func.sum(
                        WorkOrderExpense.total_amount
                    ),
                    Decimal("0.00"),
                ).label("total_amount"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                WorkOrderExpense.is_billable
                                .is_(True),
                                WorkOrderExpense.total_amount,
                            ),
                            else_=Decimal("0.00"),
                        )
                    ),
                    Decimal("0.00"),
                ).label("billable_amount"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                WorkOrderExpense.status
                                == "approved",
                                WorkOrderExpense.total_amount,
                            ),
                            else_=Decimal("0.00"),
                        )
                    ),
                    Decimal("0.00"),
                ).label("approved_amount"),
                func.count(
                    WorkOrderExpense.id
                ).label("expense_count"),
            )
            .join(
                WorkOrder,
                WorkOrder.id
                == WorkOrderExpense.work_order_id,
            )
            .filter(
                WorkOrder.organization_id
                == organization_id,
                WorkOrder.id == work_order_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrder.is_active.is_(True),
                WorkOrderExpense.is_active.is_(True),
            )

        query = self._apply_filters(
            query,
            date_from=date_from,
            date_to=date_to,
        )

        return (
            query.group_by(
                WorkOrderExpense.currency
            )
            .order_by(
                WorkOrderExpense.currency
            )
            .all()
        )

    def totals_by_category(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        include_inactive: bool = False,
    ) -> list[
        tuple[
            str,
            str,
            Decimal,
            int,
        ]
    ]:
        """
        Aggregate expense totals by currency and category.
        """

        query = (
            self.db.query(
                WorkOrderExpense.currency,
                WorkOrderExpense.category,
                func.coalesce(
                    func.sum(
                        WorkOrderExpense.total_amount
                    ),
                    Decimal("0.00"),
                ).label("amount"),
                func.count(
                    WorkOrderExpense.id
                ).label("expense_count"),
            )
            .join(
                WorkOrder,
                WorkOrder.id
                == WorkOrderExpense.work_order_id,
            )
            .filter(
                WorkOrder.organization_id
                == organization_id,
                WorkOrder.id == work_order_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrder.is_active.is_(True),
                WorkOrderExpense.is_active.is_(True),
            )

        query = self._apply_filters(
            query,
            date_from=date_from,
            date_to=date_to,
        )

        return (
            query.group_by(
                WorkOrderExpense.currency,
                WorkOrderExpense.category,
            )
            .order_by(
                WorkOrderExpense.currency,
                WorkOrderExpense.category,
            )
            .all()
        )

    def totals_by_status(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        include_inactive: bool = False,
    ) -> list[
        tuple[
            str,
            str,
            Decimal,
            int,
        ]
    ]:
        """
        Aggregate expense totals by currency and status.
        """

        query = (
            self.db.query(
                WorkOrderExpense.currency,
                WorkOrderExpense.status,
                func.coalesce(
                    func.sum(
                        WorkOrderExpense.total_amount
                    ),
                    Decimal("0.00"),
                ).label("amount"),
                func.count(
                    WorkOrderExpense.id
                ).label("expense_count"),
            )
            .join(
                WorkOrder,
                WorkOrder.id
                == WorkOrderExpense.work_order_id,
            )
            .filter(
                WorkOrder.organization_id
                == organization_id,
                WorkOrder.id == work_order_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrder.is_active.is_(True),
                WorkOrderExpense.is_active.is_(True),
            )

        query = self._apply_filters(
            query,
            date_from=date_from,
            date_to=date_to,
        )

        return (
            query.group_by(
                WorkOrderExpense.currency,
                WorkOrderExpense.status,
            )
            .order_by(
                WorkOrderExpense.currency,
                WorkOrderExpense.status,
            )
            .all()
        )