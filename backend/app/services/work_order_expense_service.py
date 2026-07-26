"""
Work-order expense service.

Handles calculated expense totals, organization scoping,
draft editing, approval workflow, soft deletion, restoration,
summary reporting, and work-order activity recording.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.enums.work_order_expense import (
    WorkOrderExpenseCategory,
    WorkOrderExpenseStatus,
)
from app.models.work_order import WorkOrder
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_expense import WorkOrderExpense
from app.repositories.work_order import WorkOrderRepository
from app.repositories.work_order_activity import (
    WorkOrderActivityRepository,
)
from app.repositories.work_order_expense import (
    WorkOrderExpenseRepository,
)
from app.schemas.work_order_expense import (
    WorkOrderExpenseCategoryTotal,
    WorkOrderExpenseCreate,
    WorkOrderExpenseCurrencySummary,
    WorkOrderExpenseListResponse,
    WorkOrderExpenseResponse,
    WorkOrderExpenseStatusChange,
    WorkOrderExpenseStatusTotal,
    WorkOrderExpenseSummaryResponse,
    WorkOrderExpenseUpdate,
)


class WorkOrderExpenseService:
    """
    Handles work-order expense business logic.
    """

    MONEY_QUANTIZER = Decimal("0.01")
    MAX_TOTAL_AMOUNT = Decimal("999999999999.99")

    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.work_orders = WorkOrderRepository(db)
        self.expenses = WorkOrderExpenseRepository(db)
        self.activities = WorkOrderActivityRepository(db)

    @staticmethod
    def _utc_now() -> datetime:
        """
        Return the current timezone-aware UTC timestamp.
        """

        return datetime.now(timezone.utc)

    @classmethod
    def _calculate_total(
        cls,
        quantity: Decimal,
        unit_cost: Decimal,
    ) -> Decimal:
        """
        Calculate a currency total rounded to two decimals.
        """

        total = (
            Decimal(quantity)
            * Decimal(unit_cost)
        ).quantize(
            cls.MONEY_QUANTIZER,
            rounding=ROUND_HALF_UP,
        )

        if total > cls.MAX_TOTAL_AMOUNT:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=(
                    "Calculated expense total exceeds the "
                    "supported monetary limit."
                ),
            )

        return total

    @staticmethod
    def _build_response(
        expense: WorkOrderExpense,
    ) -> WorkOrderExpenseResponse:
        """
        Convert an expense model into an API response.
        """

        created_by = expense.created_by
        reviewed_by = expense.reviewed_by

        return WorkOrderExpenseResponse(
            id=expense.id,
            work_order_id=expense.work_order_id,
            created_by_user_id=(
                expense.created_by_user_id
            ),
            created_by_first_name=(
                created_by.first_name
                if created_by is not None
                else None
            ),
            created_by_last_name=(
                created_by.last_name
                if created_by is not None
                else None
            ),
            created_by_email=(
                created_by.email
                if created_by is not None
                else None
            ),
            reviewed_by_user_id=(
                expense.reviewed_by_user_id
            ),
            reviewed_by_first_name=(
                reviewed_by.first_name
                if reviewed_by is not None
                else None
            ),
            reviewed_by_last_name=(
                reviewed_by.last_name
                if reviewed_by is not None
                else None
            ),
            reviewed_by_email=(
                reviewed_by.email
                if reviewed_by is not None
                else None
            ),
            category=expense.category,
            description=expense.description,
            quantity=expense.quantity,
            unit_cost=expense.unit_cost,
            total_amount=expense.total_amount,
            currency=expense.currency,
            expense_date=expense.expense_date,
            vendor_name=expense.vendor_name,
            reference_number=expense.reference_number,
            notes=expense.notes,
            is_billable=expense.is_billable,
            status=expense.status,
            submitted_at=expense.submitted_at,
            reviewed_at=expense.reviewed_at,
            review_note=expense.review_note,
            is_active=expense.is_active,
            created_at=expense.created_at,
            updated_at=expense.updated_at,
        )

    def _record_activity(
        self,
        *,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        activity_type: str,
        summary: str,
        from_status: str | None = None,
        to_status: str | None = None,
        note: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> WorkOrderActivity:
        """
        Record one immutable expense-related activity.
        """

        activity = WorkOrderActivity(
            organization_id=organization_id,
            work_order_id=work_order_id,
            actor_user_id=actor_user_id,
            activity_type=activity_type,
            summary=summary,
            from_status=from_status,
            to_status=to_status,
            note=note,
            details=details or {},
        )

        return self.activities.create_activity(
            activity
        )

    def _get_work_order_or_404(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrder:
        """
        Retrieve an organization-scoped work order.
        """

        work_order = (
            self.work_orders.get_for_organization(
                organization_id=organization_id,
                work_order_id=work_order_id,
                include_inactive=include_inactive,
            )
        )

        if work_order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work order not found.",
            )

        return work_order

    def _get_expense_or_404(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        expense_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrderExpense:
        """
        Retrieve an organization-scoped expense.
        """

        expense = self.expenses.get_for_work_order(
            organization_id=organization_id,
            work_order_id=work_order_id,
            expense_id=expense_id,
            include_inactive=include_inactive,
        )

        if expense is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work-order expense not found.",
            )

        return expense

    def _reload_expense(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        expense_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrderExpense:
        """
        Reload an expense with user relationships.
        """

        return self._get_expense_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            expense_id=expense_id,
            include_inactive=include_inactive,
        )

    @staticmethod
    def _ensure_date_range_valid(
        date_from: date | None,
        date_to: date | None,
    ) -> None:
        """
        Reject an inverted expense date range.
        """

        if (
            date_from is not None
            and date_to is not None
            and date_from > date_to
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=(
                    "date_from cannot be later than date_to."
                ),
            )

    @staticmethod
    def _ensure_draft(
        expense: WorkOrderExpense,
    ) -> None:
        """
        Require an expense to be in draft status.
        """

        if (
            expense.status
            != WorkOrderExpenseStatus.DRAFT.value
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only draft expenses can be edited."
                ),
            )

    @staticmethod
    def _ensure_deactivation_allowed(
        expense: WorkOrderExpense,
    ) -> None:
        """
        Prevent submitted or approved expenses from deletion.
        """

        allowed_statuses = {
            WorkOrderExpenseStatus.DRAFT.value,
            WorkOrderExpenseStatus.REJECTED.value,
        }

        if expense.status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only draft or rejected expenses can "
                    "be deactivated."
                ),
            )

    @staticmethod
    def _validate_status_transition(
        current_status: str,
        target_status: WorkOrderExpenseStatus,
    ) -> None:
        """
        Validate the expense approval state transition.
        """

        allowed_transitions = {
            WorkOrderExpenseStatus.DRAFT.value: {
                WorkOrderExpenseStatus.SUBMITTED.value,
            },
            WorkOrderExpenseStatus.SUBMITTED.value: {
                WorkOrderExpenseStatus.APPROVED.value,
                WorkOrderExpenseStatus.REJECTED.value,
            },
            WorkOrderExpenseStatus.REJECTED.value: {
                WorkOrderExpenseStatus.DRAFT.value,
            },
            WorkOrderExpenseStatus.APPROVED.value: set(),
        }

        if (
            target_status.value
            not in allowed_transitions.get(
                current_status,
                set(),
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Expense status cannot change from "
                    f"'{current_status}' to "
                    f"'{target_status.value}'."
                ),
            )

    def create_expense(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        payload: WorkOrderExpenseCreate,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderExpenseResponse:
        """
        Create a draft work-order expense.
        """

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        total_amount = self._calculate_total(
            quantity=payload.quantity,
            unit_cost=payload.unit_cost,
        )

        expense = WorkOrderExpense(
            work_order_id=work_order_id,
            created_by_user_id=actor_user_id,
            category=payload.category.value,
            description=payload.description,
            quantity=payload.quantity,
            unit_cost=payload.unit_cost,
            total_amount=total_amount,
            currency=payload.currency,
            expense_date=payload.expense_date,
            vendor_name=payload.vendor_name,
            reference_number=payload.reference_number,
            notes=payload.notes,
            is_billable=payload.is_billable,
            status=WorkOrderExpenseStatus.DRAFT.value,
        )

        try:
            created = self.expenses.create_expense(
                expense
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                activity_type="work_order_expense_created",
                summary=(
                    f"Expense '{created.description}' created."
                ),
                details={
                    "expense_id": str(created.id),
                    "category": created.category,
                    "status": created.status,
                    "quantity": str(created.quantity),
                    "unit_cost": str(created.unit_cost),
                    "total_amount": str(
                        created.total_amount
                    ),
                    "currency": created.currency,
                    "is_billable": created.is_billable,
                },
            )

            loaded = self._reload_expense(
                organization_id=organization_id,
                work_order_id=work_order_id,
                expense_id=created.id,
            )

            return self._build_response(
                loaded
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The work-order expense conflicts with "
                    "an existing record."
                ),
            ) from exc

    def list_expenses(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        category: WorkOrderExpenseCategory | None = None,
        expense_status: WorkOrderExpenseStatus | None = None,
        currency: str | None = None,
        is_billable: bool | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        include_inactive: bool = False,
    ) -> WorkOrderExpenseListResponse:
        """
        List work-order expenses with optional filters.
        """

        self._ensure_date_range_valid(
            date_from=date_from,
            date_to=date_to,
        )

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            include_inactive=include_inactive,
        )

        normalized_currency = (
            currency.strip().upper()
            if currency is not None
            else None
        )

        expenses = self.expenses.list_for_work_order(
            organization_id=organization_id,
            work_order_id=work_order_id,
            skip=skip,
            limit=limit,
            category=(
                category.value
                if category is not None
                else None
            ),
            expense_status=(
                expense_status.value
                if expense_status is not None
                else None
            ),
            currency=normalized_currency,
            is_billable=is_billable,
            date_from=date_from,
            date_to=date_to,
            include_inactive=include_inactive,
        )

        total = self.expenses.count_for_work_order(
            organization_id=organization_id,
            work_order_id=work_order_id,
            category=(
                category.value
                if category is not None
                else None
            ),
            expense_status=(
                expense_status.value
                if expense_status is not None
                else None
            ),
            currency=normalized_currency,
            is_billable=is_billable,
            date_from=date_from,
            date_to=date_to,
            include_inactive=include_inactive,
        )

        return WorkOrderExpenseListResponse(
            items=[
                self._build_response(expense)
                for expense in expenses
            ],
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_expense(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        expense_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrderExpenseResponse:
        """
        Return one work-order expense.
        """

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            include_inactive=include_inactive,
        )

        expense = self._get_expense_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            expense_id=expense_id,
            include_inactive=include_inactive,
        )

        return self._build_response(
            expense
        )

    def update_expense(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        expense_id: uuid.UUID,
        payload: WorkOrderExpenseUpdate,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderExpenseResponse:
        """
        Edit a draft work-order expense.
        """

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        expense = self._get_expense_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            expense_id=expense_id,
        )

        self._ensure_draft(
            expense
        )

        update_data = payload.model_dump(
            exclude_unset=True
        )

        non_nullable_fields = {
            "category",
            "description",
            "quantity",
            "unit_cost",
            "currency",
            "expense_date",
            "is_billable",
        }

        for field_name in non_nullable_fields:
            if (
                field_name in update_data
                and update_data[field_name] is None
            ):
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail=(
                        f"{field_name.replace('_', ' ').title()} "
                        "cannot be null."
                    ),
                )

        changed_fields = sorted(
            update_data.keys()
        )

        for field_name, field_value in update_data.items():
            if isinstance(
                field_value,
                WorkOrderExpenseCategory,
            ):
                field_value = field_value.value

            setattr(
                expense,
                field_name,
                field_value,
            )

        expense.total_amount = self._calculate_total(
            quantity=expense.quantity,
            unit_cost=expense.unit_cost,
        )

        try:
            updated = self.expenses.update_expense(
                expense
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                activity_type="work_order_expense_updated",
                summary=(
                    f"Expense '{updated.description}' updated."
                ),
                details={
                    "expense_id": str(updated.id),
                    "changed_fields": changed_fields,
                    "category": updated.category,
                    "quantity": str(updated.quantity),
                    "unit_cost": str(updated.unit_cost),
                    "total_amount": str(
                        updated.total_amount
                    ),
                    "currency": updated.currency,
                    "is_billable": updated.is_billable,
                },
            )

            loaded = self._reload_expense(
                organization_id=organization_id,
                work_order_id=work_order_id,
                expense_id=updated.id,
            )

            return self._build_response(
                loaded
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The work-order expense update could "
                    "not be saved."
                ),
            ) from exc

    def change_status(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        expense_id: uuid.UUID,
        payload: WorkOrderExpenseStatusChange,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderExpenseResponse:
        """
        Submit, approve, reject, or reopen an expense.
        """

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        expense = self._get_expense_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            expense_id=expense_id,
        )

        previous_status = expense.status

        self._validate_status_transition(
            current_status=previous_status,
            target_status=payload.status,
        )

        now = self._utc_now()
        target_status = payload.status.value

        if (
            target_status
            == WorkOrderExpenseStatus.SUBMITTED.value
        ):
            expense.submitted_at = now
            expense.reviewed_by_user_id = None
            expense.reviewed_at = None
            expense.review_note = None

        elif target_status in {
            WorkOrderExpenseStatus.APPROVED.value,
            WorkOrderExpenseStatus.REJECTED.value,
        }:
            expense.reviewed_by_user_id = (
                actor_user_id
            )
            expense.reviewed_at = now
            expense.review_note = (
                payload.review_note
            )

        elif (
            target_status
            == WorkOrderExpenseStatus.DRAFT.value
        ):
            expense.submitted_at = None
            expense.reviewed_by_user_id = None
            expense.reviewed_at = None
            expense.review_note = None

        expense.status = target_status

        try:
            updated = self.expenses.update_expense(
                expense
            )

            summary_by_status = {
                WorkOrderExpenseStatus.SUBMITTED.value: (
                    "Work-order expense submitted "
                    "for approval."
                ),
                WorkOrderExpenseStatus.APPROVED.value: (
                    "Work-order expense approved."
                ),
                WorkOrderExpenseStatus.REJECTED.value: (
                    "Work-order expense rejected."
                ),
                WorkOrderExpenseStatus.DRAFT.value: (
                    "Rejected work-order expense "
                    "reopened as draft."
                ),
            }

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                activity_type=(
                    "work_order_expense_status_changed"
                ),
                summary=summary_by_status[target_status],
                from_status=previous_status,
                to_status=updated.status,
                note=payload.review_note,
                details={
                    "expense_id": str(updated.id),
                    "description": updated.description,
                    "from_status": previous_status,
                    "to_status": updated.status,
                    "total_amount": str(
                        updated.total_amount
                    ),
                    "currency": updated.currency,
                },
            )

            loaded = self._reload_expense(
                organization_id=organization_id,
                work_order_id=work_order_id,
                expense_id=updated.id,
            )

            return self._build_response(
                loaded
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The expense status change could "
                    "not be saved."
                ),
            ) from exc

    def deactivate_expense(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        expense_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
    ) -> None:
        """
        Soft-delete a draft or rejected expense.
        """

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        expense = self._get_expense_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            expense_id=expense_id,
        )

        self._ensure_deactivation_allowed(
            expense
        )

        self.expenses.deactivate_expense(
            expense
        )

        self._record_activity(
            organization_id=organization_id,
            work_order_id=work_order_id,
            actor_user_id=actor_user_id,
            activity_type=(
                "work_order_expense_deactivated"
            ),
            summary=(
                f"Expense '{expense.description}' deactivated."
            ),
            details={
                "expense_id": str(expense.id),
                "category": expense.category,
                "status": expense.status,
                "total_amount": str(
                    expense.total_amount
                ),
                "currency": expense.currency,
            },
        )

    def reactivate_expense(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        expense_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderExpenseResponse:
        """
        Reactivate a soft-deleted expense.
        """

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        expense = self._get_expense_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            expense_id=expense_id,
            include_inactive=True,
        )

        if not expense.is_active:
            expense = self.expenses.reactivate_expense(
                expense
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                activity_type=(
                    "work_order_expense_reactivated"
                ),
                summary=(
                    f"Expense '{expense.description}' "
                    "reactivated."
                ),
                details={
                    "expense_id": str(expense.id),
                    "category": expense.category,
                    "status": expense.status,
                    "total_amount": str(
                        expense.total_amount
                    ),
                    "currency": expense.currency,
                },
            )

        loaded = self._reload_expense(
            organization_id=organization_id,
            work_order_id=work_order_id,
            expense_id=expense.id,
            include_inactive=True,
        )

        return self._build_response(
            loaded
        )

    def get_summary(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        include_inactive: bool = False,
    ) -> WorkOrderExpenseSummaryResponse:
        """
        Return expense totals grouped separately by currency.
        """

        self._ensure_date_range_valid(
            date_from=date_from,
            date_to=date_to,
        )

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            include_inactive=include_inactive,
        )

        currency_rows = (
            self.expenses.totals_by_currency(
                organization_id=organization_id,
                work_order_id=work_order_id,
                date_from=date_from,
                date_to=date_to,
                include_inactive=include_inactive,
            )
        )

        category_rows = (
            self.expenses.totals_by_category(
                organization_id=organization_id,
                work_order_id=work_order_id,
                date_from=date_from,
                date_to=date_to,
                include_inactive=include_inactive,
            )
        )

        status_rows = (
            self.expenses.totals_by_status(
                organization_id=organization_id,
                work_order_id=work_order_id,
                date_from=date_from,
                date_to=date_to,
                include_inactive=include_inactive,
            )
        )

        categories_by_currency: dict[
            str,
            list[WorkOrderExpenseCategoryTotal],
        ] = {}

        for (
            currency,
            category,
            amount,
            expense_count,
        ) in category_rows:
            categories_by_currency.setdefault(
                currency,
                [],
            ).append(
                WorkOrderExpenseCategoryTotal(
                    category=category,
                    amount=amount,
                    count=expense_count,
                )
            )

        statuses_by_currency: dict[
            str,
            list[WorkOrderExpenseStatusTotal],
        ] = {}

        for (
            currency,
            expense_status,
            amount,
            expense_count,
        ) in status_rows:
            statuses_by_currency.setdefault(
                currency,
                [],
            ).append(
                WorkOrderExpenseStatusTotal(
                    status=expense_status,
                    amount=amount,
                    count=expense_count,
                )
            )

        summaries = [
            WorkOrderExpenseCurrencySummary(
                currency=currency,
                total_amount=total_amount,
                billable_amount=billable_amount,
                approved_amount=approved_amount,
                expense_count=expense_count,
                by_category=(
                    categories_by_currency.get(
                        currency,
                        [],
                    )
                ),
                by_status=(
                    statuses_by_currency.get(
                        currency,
                        [],
                    )
                ),
            )
            for (
                currency,
                total_amount,
                billable_amount,
                approved_amount,
                expense_count,
            ) in currency_rows
        ]

        return WorkOrderExpenseSummaryResponse(
            currencies=summaries
        )