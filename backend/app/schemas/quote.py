"""
Quote schemas.

Defines validation and API responses for customer quotes,
estimate line items, lifecycle actions, conversion, reporting,
and immutable quote activities.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)


QuoteStatusType = Literal[
    "draft",
    "sent",
    "accepted",
    "rejected",
    "expired",
    "converted",
]

QuoteActivityType = Literal[
    "quote_created",
    "quote_updated",
    "quote_line_item_added",
    "quote_line_item_updated",
    "quote_line_item_removed",
    "quote_sent",
    "quote_accepted",
    "quote_rejected",
    "quote_expired",
    "quote_converted",
]

WorkOrderPriority = Literal[
    "low",
    "normal",
    "high",
    "urgent",
]


def _normalize_optional_text(
    value: object,
) -> object:
    """
    Strip optional text and convert blanks to None.
    """

    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None

    return value


class QuoteLineItemCreate(BaseModel):
    """
    One line included while creating a quote.
    """

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

    unit_price: Decimal = Field(
        ge=Decimal("0"),
        max_digits=14,
        decimal_places=2,
    )

    position: int | None = Field(
        default=None,
        ge=0,
    )

    @field_validator(
        "description",
        mode="before",
    )
    @classmethod
    def normalize_description(
        cls,
        value: object,
    ) -> object:
        """
        Require a non-empty line description.
        """

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Line-item description cannot be empty."
                )

            return normalized

        return value


class QuoteLineItemUpdate(BaseModel):
    """
    Editable fields for one draft quote line.
    """

    description: str | None = Field(
        default=None,
        max_length=500,
    )

    quantity: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
        max_digits=14,
        decimal_places=3,
    )

    unit_price: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=14,
        decimal_places=2,
    )

    position: int | None = Field(
        default=None,
        ge=0,
    )

    @field_validator(
        "description",
        mode="before",
    )
    @classmethod
    def normalize_description(
        cls,
        value: object,
    ) -> object:
        """
        Reject a blank supplied description.
        """

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Line-item description cannot be empty."
                )

            return normalized

        return value


class QuoteCreate(BaseModel):
    """
    Payload used to create a draft quote.
    """

    customer_id: uuid.UUID
    customer_site_id: uuid.UUID | None = None

    quote_number: str | None = Field(
        default=None,
        max_length=50,
    )

    title: str = Field(
        min_length=1,
        max_length=200,
    )

    description: str | None = Field(
        default=None,
        max_length=10000,
    )

    currency: str = Field(
        default="NGN",
        min_length=3,
        max_length=3,
    )

    quote_date: date = Field(
        default_factory=date.today,
    )

    valid_until: date | None = None

    discount_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        max_digits=14,
        decimal_places=2,
    )

    tax_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        max_digits=14,
        decimal_places=2,
    )

    notes: str | None = Field(
        default=None,
        max_length=10000,
    )

    terms: str | None = Field(
        default=None,
        max_length=10000,
    )

    line_items: list[QuoteLineItemCreate] = Field(
        default_factory=list,
        max_length=200,
    )

    @field_validator(
        "quote_number",
        mode="before",
    )
    @classmethod
    def normalize_quote_number(
        cls,
        value: object,
    ) -> object:
        """
        Normalize an optional quote number.
        """

        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or None

        return value

    @field_validator(
        "title",
        mode="before",
    )
    @classmethod
    def normalize_title(
        cls,
        value: object,
    ) -> object:
        """
        Require a non-empty title.
        """

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Quote title cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "description",
        "notes",
        "terms",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """
        Normalize optional quote text.
        """

        return _normalize_optional_text(value)

    @field_validator(
        "currency",
        mode="before",
    )
    @classmethod
    def normalize_currency(
        cls,
        value: object,
    ) -> object:
        """
        Normalize the ISO-style currency code.
        """

        if isinstance(value, str):
            normalized = value.strip().upper()

            if len(normalized) != 3:
                raise ValueError(
                    "Currency must be a three-letter code."
                )

            return normalized

        return value

    @model_validator(mode="after")
    def validate_dates_and_positions(
        self,
    ) -> "QuoteCreate":
        """
        Validate quote dates and explicit line positions.
        """

        if (
            self.valid_until is not None
            and self.valid_until < self.quote_date
        ):
            raise ValueError(
                "Valid-until date cannot be before quote date."
            )

        explicit_positions = [
            item.position
            for item in self.line_items
            if item.position is not None
        ]

        if len(explicit_positions) != len(
            set(explicit_positions)
        ):
            raise ValueError(
                "Quote line-item positions must be unique."
            )

        return self


class QuoteUpdate(BaseModel):
    """
    Editable fields for a draft quote.
    """

    customer_id: uuid.UUID | None = None
    customer_site_id: uuid.UUID | None = None

    quote_number: str | None = Field(
        default=None,
        max_length=50,
    )

    title: str | None = Field(
        default=None,
        max_length=200,
    )

    description: str | None = Field(
        default=None,
        max_length=10000,
    )

    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
    )

    quote_date: date | None = None
    valid_until: date | None = None

    discount_amount: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=14,
        decimal_places=2,
    )

    tax_amount: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=14,
        decimal_places=2,
    )

    notes: str | None = Field(
        default=None,
        max_length=10000,
    )

    terms: str | None = Field(
        default=None,
        max_length=10000,
    )

    @field_validator(
        "quote_number",
        mode="before",
    )
    @classmethod
    def normalize_quote_number(
        cls,
        value: object,
    ) -> object:
        """
        Reject a blank supplied quote number.
        """

        if isinstance(value, str):
            normalized = value.strip().upper()

            if not normalized:
                raise ValueError(
                    "Quote number cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "title",
        mode="before",
    )
    @classmethod
    def normalize_title(
        cls,
        value: object,
    ) -> object:
        """
        Reject a blank supplied title.
        """

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Quote title cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "description",
        "notes",
        "terms",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """
        Normalize optional quote text.
        """

        return _normalize_optional_text(value)

    @field_validator(
        "currency",
        mode="before",
    )
    @classmethod
    def normalize_currency(
        cls,
        value: object,
    ) -> object:
        """
        Normalize a supplied currency code.
        """

        if isinstance(value, str):
            normalized = value.strip().upper()

            if len(normalized) != 3:
                raise ValueError(
                    "Currency must be a three-letter code."
                )

            return normalized

        return value


class QuoteLifecycleNote(BaseModel):
    """
    Optional note attached to a lifecycle action.
    """

    note: str | None = Field(
        default=None,
        max_length=10000,
    )

    @field_validator(
        "note",
        mode="before",
    )
    @classmethod
    def normalize_note(
        cls,
        value: object,
    ) -> object:
        """
        Normalize an optional lifecycle note.
        """

        return _normalize_optional_text(value)


class QuoteRejectRequest(BaseModel):
    """
    Required customer rejection reason.
    """

    reason: str = Field(
        min_length=1,
        max_length=10000,
    )

    @field_validator(
        "reason",
        mode="before",
    )
    @classmethod
    def normalize_reason(
        cls,
        value: object,
    ) -> object:
        """
        Require a non-empty rejection reason.
        """

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Rejection reason cannot be empty."
                )

            return normalized

        return value


class QuoteConvertRequest(BaseModel):
    """
    Work-order details supplied while converting an accepted quote.
    """

    title: str | None = Field(
        default=None,
        max_length=200,
    )

    description: str | None = Field(
        default=None,
        max_length=10000,
    )

    job_type: str | None = Field(
        default=None,
        max_length=100,
    )

    customer_reference: str | None = Field(
        default=None,
        max_length=100,
    )

    priority: WorkOrderPriority = "normal"

    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None

    instructions: str | None = Field(
        default=None,
        max_length=10000,
    )

    @field_validator(
        "title",
        mode="before",
    )
    @classmethod
    def normalize_title(
        cls,
        value: object,
    ) -> object:
        """
        Normalize an optional work-order title.
        """

        return _normalize_optional_text(value)

    @field_validator(
        "description",
        "job_type",
        "customer_reference",
        "instructions",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """
        Normalize optional work-order text.
        """

        return _normalize_optional_text(value)

    @field_validator(
        "priority",
        mode="before",
    )
    @classmethod
    def normalize_priority(
        cls,
        value: object,
    ) -> object:
        """
        Normalize work-order priority.
        """

        if isinstance(value, str):
            return value.strip().lower()

        return value

    @model_validator(mode="after")
    def validate_schedule(
        self,
    ) -> "QuoteConvertRequest":
        """
        Validate the optional work-order schedule.
        """

        if (
            self.scheduled_start is not None
            and self.scheduled_end is not None
            and self.scheduled_end <= self.scheduled_start
        ):
            raise ValueError(
                "Scheduled end must be after scheduled start."
            )

        return self


class QuoteLineItemResponse(BaseModel):
    """
    Quote line returned by the API.
    """

    id: uuid.UUID
    quote_id: uuid.UUID
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    position: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class QuoteResponse(BaseModel):
    """
    Complete quote returned by the API.
    """

    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID
    customer_site_id: uuid.UUID | None
    converted_work_order_id: uuid.UUID | None

    created_by_user_id: uuid.UUID | None
    created_by_first_name: str | None
    created_by_last_name: str | None
    created_by_email: str | None

    sent_by_user_id: uuid.UUID | None
    sent_by_first_name: str | None
    sent_by_last_name: str | None
    sent_by_email: str | None

    responded_by_user_id: uuid.UUID | None
    responded_by_first_name: str | None
    responded_by_last_name: str | None
    responded_by_email: str | None

    converted_by_user_id: uuid.UUID | None
    converted_by_first_name: str | None
    converted_by_last_name: str | None
    converted_by_email: str | None

    quote_number: str
    title: str
    description: str | None
    currency: str
    status: QuoteStatusType

    quote_date: date
    valid_until: date | None

    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal

    customer_name: str
    customer_email: str | None
    customer_phone: str | None
    billing_address: str | None
    service_address: str | None

    notes: str | None
    terms: str | None

    sent_at: datetime | None
    accepted_at: datetime | None
    rejected_at: datetime | None
    expired_at: datetime | None
    converted_at: datetime | None
    response_note: str | None

    is_active: bool

    line_items: list[QuoteLineItemResponse] = Field(
        default_factory=list,
    )

    created_at: datetime
    updated_at: datetime


class QuoteListResponse(BaseModel):
    """
    Paginated quote collection.
    """

    items: list[QuoteResponse] = Field(
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


class QuoteCurrencySummary(BaseModel):
    """
    Quote totals for one currency.
    """

    currency: str
    quote_count: int = Field(ge=0)
    total_quoted: Decimal = Field(ge=Decimal("0"))
    total_accepted: Decimal = Field(ge=Decimal("0"))

    draft_count: int = Field(ge=0)
    sent_count: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    expired_count: int = Field(ge=0)
    converted_count: int = Field(ge=0)


class QuoteSummaryResponse(BaseModel):
    """
    Multi-currency quote reporting response.
    """

    currencies: list[QuoteCurrencySummary] = Field(
        default_factory=list,
    )


class QuoteActivityResponse(BaseModel):
    """
    Immutable quote activity returned by the API.
    """

    id: uuid.UUID
    organization_id: uuid.UUID
    quote_id: uuid.UUID

    actor_user_id: uuid.UUID | None
    actor_first_name: str | None
    actor_last_name: str | None
    actor_email: str | None

    activity_type: QuoteActivityType
    summary: str
    from_status: QuoteStatusType | None
    to_status: QuoteStatusType | None
    note: str | None
    details: dict[str, object]

    created_at: datetime


class QuoteActivityListResponse(BaseModel):
    """
    Paginated quote activity collection.
    """

    items: list[QuoteActivityResponse] = Field(
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


class QuoteConversionResponse(BaseModel):
    """
    Result returned after converting a quote.
    """

    quote: QuoteResponse
    work_order_id: uuid.UUID
    work_order_number: str