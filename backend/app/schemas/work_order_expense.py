"""
Work-order expense schemas.

Defines request and response payloads for operational expenses,
approval workflow, filtering, and cost summaries.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)

from app.enums.work_order_expense import (
    WorkOrderExpenseCategory,
    WorkOrderExpenseStatus,
)


class WorkOrderExpenseCreate(BaseModel):
    """
    Payload for recording a new work-order expense.
    """

    category: WorkOrderExpenseCategory = (
        WorkOrderExpenseCategory.OTHER
    )

    description: str = Field(
        min_length=1,
        max_length=500,
    )

    quantity: Decimal = Field(
        default=Decimal("1.000"),
        gt=Decimal("0"),
        max_digits=14,
        decimal_places=3,
    )

    unit_cost: Decimal = Field(
        ge=Decimal("0"),
        max_digits=14,
        decimal_places=2,
    )

    currency: str = Field(
        default="NGN",
        min_length=3,
        max_length=3,
    )

    expense_date: date = Field(
        default_factory=date.today,
    )

    vendor_name: str | None = Field(
        default=None,
        max_length=200,
    )

    reference_number: str | None = Field(
        default=None,
        max_length=100,
    )

    notes: str | None = Field(
        default=None,
        max_length=10_000,
    )

    is_billable: bool = True

    @field_validator("description")
    @classmethod
    def normalize_description(
        cls,
        value: str,
    ) -> str:
        """
        Strip and validate the required description.
        """

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Expense description cannot be empty."
            )

        return normalized

    @field_validator("currency")
    @classmethod
    def normalize_currency(
        cls,
        value: str,
    ) -> str:
        """
        Normalize an ISO-style three-letter currency code.
        """

        normalized = value.strip().upper()

        if (
            len(normalized) != 3
            or not normalized.isalpha()
        ):
            raise ValueError(
                "Currency must be a three-letter code."
            )

        return normalized

    @field_validator(
        "vendor_name",
        "reference_number",
        "notes",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        """
        Strip optional text and convert blanks to null.
        """

        if value is None:
            return None

        normalized = value.strip()

        return normalized or None


class WorkOrderExpenseUpdate(BaseModel):
    """
    Payload for editing a draft work-order expense.

    Approval status changes use a separate payload.
    """

    category: WorkOrderExpenseCategory | None = None

    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )

    quantity: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
        max_digits=14,
        decimal_places=3,
    )

    unit_cost: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=14,
        decimal_places=2,
    )

    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
    )

    expense_date: date | None = None

    vendor_name: str | None = Field(
        default=None,
        max_length=200,
    )

    reference_number: str | None = Field(
        default=None,
        max_length=100,
    )

    notes: str | None = Field(
        default=None,
        max_length=10_000,
    )

    is_billable: bool | None = None

    @field_validator("description")
    @classmethod
    def normalize_description(
        cls,
        value: str | None,
    ) -> str | None:
        """
        Normalize an optional description.
        """

        if value is None:
            return None

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Expense description cannot be empty."
            )

        return normalized

    @field_validator("currency")
    @classmethod
    def normalize_currency(
        cls,
        value: str | None,
    ) -> str | None:
        """
        Normalize an optional currency code.
        """

        if value is None:
            return None

        normalized = value.strip().upper()

        if (
            len(normalized) != 3
            or not normalized.isalpha()
        ):
            raise ValueError(
                "Currency must be a three-letter code."
            )

        return normalized

    @field_validator(
        "vendor_name",
        "reference_number",
        "notes",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        """
        Strip optional text and convert blanks to null.
        """

        if value is None:
            return None

        normalized = value.strip()

        return normalized or None

    @model_validator(mode="after")
    def validate_update_payload(
        self,
    ) -> "WorkOrderExpenseUpdate":
        """
        Require at least one supplied update field.
        """

        if not self.model_fields_set:
            raise ValueError(
                "At least one expense field must be supplied."
            )

        return self


class WorkOrderExpenseStatusChange(BaseModel):
    """
    Payload for changing an expense approval status.
    """

    status: WorkOrderExpenseStatus

    review_note: str | None = Field(
        default=None,
        max_length=10_000,
    )

    @field_validator("review_note")
    @classmethod
    def normalize_review_note(
        cls,
        value: str | None,
    ) -> str | None:
        """
        Strip an optional review note.
        """

        if value is None:
            return None

        normalized = value.strip()

        return normalized or None

    @model_validator(mode="after")
    def validate_rejection_note(
        self,
    ) -> "WorkOrderExpenseStatusChange":
        """
        Require an explanation when rejecting an expense.
        """

        if (
            self.status
            == WorkOrderExpenseStatus.REJECTED
            and not self.review_note
        ):
            raise ValueError(
                "A review note is required when rejecting "
                "an expense."
            )

        return self


class WorkOrderExpenseResponse(BaseModel):
    """
    One work-order expense returned by the API.
    """

    id: uuid.UUID
    work_order_id: uuid.UUID

    created_by_user_id: uuid.UUID | None
    created_by_first_name: str | None
    created_by_last_name: str | None
    created_by_email: str | None

    reviewed_by_user_id: uuid.UUID | None
    reviewed_by_first_name: str | None
    reviewed_by_last_name: str | None
    reviewed_by_email: str | None

    category: WorkOrderExpenseCategory
    description: str

    quantity: Decimal
    unit_cost: Decimal
    total_amount: Decimal
    currency: str

    expense_date: date

    vendor_name: str | None
    reference_number: str | None
    notes: str | None

    is_billable: bool
    status: WorkOrderExpenseStatus

    submitted_at: datetime | None
    reviewed_at: datetime | None
    review_note: str | None

    is_active: bool

    created_at: datetime
    updated_at: datetime


class WorkOrderExpenseListResponse(BaseModel):
    """
    Paginated work-order expense collection.
    """

    items: list[WorkOrderExpenseResponse] = Field(
        default_factory=list,
    )

    total: int = Field(
        ge=0,
    )

    skip: int = Field(
        ge=0,
    )

    limit: int = Field(
        ge=1,
    )


class WorkOrderExpenseCategoryTotal(BaseModel):
    """
    Expense total for one category and currency.
    """

    category: WorkOrderExpenseCategory
    amount: Decimal
    count: int = Field(
        ge=0,
    )


class WorkOrderExpenseStatusTotal(BaseModel):
    """
    Expense total for one approval status and currency.
    """

    status: WorkOrderExpenseStatus
    amount: Decimal
    count: int = Field(
        ge=0,
    )


class WorkOrderExpenseCurrencySummary(BaseModel):
    """
    Expense totals belonging to one currency.
    """

    currency: str

    total_amount: Decimal
    billable_amount: Decimal
    approved_amount: Decimal

    expense_count: int = Field(
        ge=0,
    )

    by_category: list[
        WorkOrderExpenseCategoryTotal
    ] = Field(
        default_factory=list,
    )

    by_status: list[
        WorkOrderExpenseStatusTotal
    ] = Field(
        default_factory=list,
    )


class WorkOrderExpenseSummaryResponse(BaseModel):
    """
    Work-order expense summary grouped by currency.

    Different currencies are deliberately not added together.
    """

    currencies: list[
        WorkOrderExpenseCurrencySummary
    ] = Field(
        default_factory=list,
    )