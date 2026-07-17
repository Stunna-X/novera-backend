"""
Invoice schemas.

Defines validation and API response models for invoices,
invoice line items, customer payments, payment reversals,
and organization billing summaries.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.enums.invoice import (
    InvoiceLineSource,
    InvoicePaymentMethod,
    InvoiceStatus,
)


class InvoiceManualLineItemCreate(BaseModel):
    """
    Manual line item supplied while creating an invoice.
    """

    description: str = Field(
        min_length=1,
        max_length=500,
    )

    quantity: Decimal = Field(
        default=Decimal("1.000"),
        gt=0,
        max_digits=14,
        decimal_places=3,
    )

    unit_price: Decimal = Field(
        ge=0,
        max_digits=14,
        decimal_places=2,
    )

    position: int | None = Field(
        default=None,
        ge=0,
    )

    @field_validator("description")
    @classmethod
    def normalize_description(
        cls,
        value: str,
    ) -> str:
        """
        Trim and validate the line-item description.
        """

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Description cannot be empty."
            )

        return normalized


class InvoiceCreate(BaseModel):
    """
    Payload for creating a draft invoice.

    At least one approved billable expense or one manual
    line item must be supplied.
    """

    currency: str = Field(
        default="NGN",
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
    )

    invoice_date: date = Field(
        default_factory=date.today,
    )

    due_date: date | None = None

    discount_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        max_digits=14,
        decimal_places=2,
    )

    tax_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        max_digits=14,
        decimal_places=2,
    )

    billing_address: str | None = Field(
        default=None,
        max_length=2000,
    )

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    terms: str | None = Field(
        default=None,
        max_length=5000,
    )

    expense_ids: list[uuid.UUID] = Field(
        default_factory=list,
        max_length=200,
    )

    manual_line_items: list[
        InvoiceManualLineItemCreate
    ] = Field(
        default_factory=list,
        max_length=200,
    )

    @field_validator("currency")
    @classmethod
    def normalize_currency(
        cls,
        value: str,
    ) -> str:
        """
        Normalize ISO-style currency code.
        """

        return value.strip().upper()

    @field_validator(
        "billing_address",
        "notes",
        "terms",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        """
        Convert blank optional text values to null.
        """

        if value is None:
            return None

        normalized = value.strip()

        return normalized or None

    @field_validator("expense_ids")
    @classmethod
    def validate_unique_expenses(
        cls,
        value: list[uuid.UUID],
    ) -> list[uuid.UUID]:
        """
        Prevent duplicate expense identifiers.
        """

        if len(value) != len(set(value)):
            raise ValueError(
                "expense_ids cannot contain duplicates."
            )

        return value

    @model_validator(mode="after")
    def validate_invoice_payload(
        self,
    ) -> Self:
        """
        Validate dates and require at least one line source.
        """

        if (
            self.due_date is not None
            and self.due_date < self.invoice_date
        ):
            raise ValueError(
                "due_date cannot be earlier than invoice_date."
            )

        if (
            not self.expense_ids
            and not self.manual_line_items
        ):
            raise ValueError(
                "At least one expense or manual line item "
                "must be supplied."
            )

        return self



class InvoiceFromCloseoutCreate(BaseModel):
    currency: str = Field(
        default="NGN",
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
    )

    invoice_date: date = Field(
        default_factory=date.today,
    )

    due_date: date | None = None

    discount_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        max_digits=14,
        decimal_places=2,
    )

    tax_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        max_digits=14,
        decimal_places=2,
    )

    billing_address: str | None = Field(
        default=None,
        max_length=2000,
    )

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    terms: str | None = Field(
        default=None,
        max_length=5000,
    )

    include_estimated_cost_line: bool = True

    closeout_line_description: str | None = Field(
        default=None,
        max_length=500,
    )

    manual_line_items: list[
        InvoiceManualLineItemCreate
    ] = Field(
        default_factory=list,
        max_length=200,
    )

    @field_validator("currency")
    @classmethod
    def normalize_currency(
        cls,
        value: str,
    ) -> str:
        return value.strip().upper()

    @field_validator(
        "billing_address",
        "notes",
        "terms",
        "closeout_line_description",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip()

        return normalized or None

    @model_validator(mode="after")
    def validate_closeout_invoice_payload(
        self,
    ) -> Self:
        if (
            self.due_date is not None
            and self.due_date < self.invoice_date
        ):
            raise ValueError(
                "due_date cannot be earlier than invoice_date."
            )

        if (
            not self.include_estimated_cost_line
            and not self.manual_line_items
        ):
            raise ValueError(
                "Either include_estimated_cost_line must be true "
                "or at least one manual line item must be supplied."
            )

        return self


class InvoiceUpdate(BaseModel):
    """
    Editable fields on a draft invoice.
    """

    invoice_date: date | None = None
    due_date: date | None = None

    discount_amount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=2,
    )

    tax_amount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=2,
    )

    billing_address: str | None = Field(
        default=None,
        max_length=2000,
    )

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    terms: str | None = Field(
        default=None,
        max_length=5000,
    )

    @field_validator(
        "billing_address",
        "notes",
        "terms",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        """
        Convert blank optional text values to null.
        """

        if value is None:
            return None

        normalized = value.strip()

        return normalized or None

    @model_validator(mode="after")
    def require_update_field(
        self,
    ) -> Self:
        """
        Require at least one supplied update field.
        """

        if not self.model_fields_set:
            raise ValueError(
                "At least one invoice field must be supplied."
            )

        return self


class InvoiceLineItemCreate(BaseModel):
    """
    Payload for adding a manual draft-invoice line item.
    """

    description: str = Field(
        min_length=1,
        max_length=500,
    )

    quantity: Decimal = Field(
        default=Decimal("1.000"),
        gt=0,
        max_digits=14,
        decimal_places=3,
    )

    unit_price: Decimal = Field(
        ge=0,
        max_digits=14,
        decimal_places=2,
    )

    position: int | None = Field(
        default=None,
        ge=0,
    )

    @field_validator("description")
    @classmethod
    def normalize_description(
        cls,
        value: str,
    ) -> str:
        """
        Trim the line-item description.
        """

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Description cannot be empty."
            )

        return normalized


class InvoiceExpenseLineCreate(BaseModel):
    """
    Payload for adding one approved billable expense.
    """

    expense_id: uuid.UUID

    position: int | None = Field(
        default=None,
        ge=0,
    )


class InvoiceLineItemUpdate(BaseModel):
    """
    Editable manual line-item fields.
    """

    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )

    quantity: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=14,
        decimal_places=3,
    )

    unit_price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=2,
    )

    position: int | None = Field(
        default=None,
        ge=0,
    )

    @field_validator("description")
    @classmethod
    def normalize_description(
        cls,
        value: str | None,
    ) -> str | None:
        """
        Trim an optional line-item description.
        """

        if value is None:
            return None

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Description cannot be empty."
            )

        return normalized

    @model_validator(mode="after")
    def require_update_field(
        self,
    ) -> Self:
        """
        Require at least one line-item update.
        """

        if not self.model_fields_set:
            raise ValueError(
                "At least one line-item field must be supplied."
            )

        return self


class InvoiceIssueRequest(BaseModel):
    """
    Optional note attached when issuing an invoice.
    """

    note: str | None = Field(
        default=None,
        max_length=2000,
    )

    @field_validator("note")
    @classmethod
    def normalize_note(
        cls,
        value: str | None,
    ) -> str | None:
        """
        Convert a blank issue note to null.
        """

        if value is None:
            return None

        normalized = value.strip()

        return normalized or None


class InvoiceVoidRequest(BaseModel):
    """
    Required explanation for voiding an invoice.
    """

    reason: str = Field(
        min_length=3,
        max_length=2000,
    )

    @field_validator("reason")
    @classmethod
    def normalize_reason(
        cls,
        value: str,
    ) -> str:
        """
        Trim and validate the void reason.
        """

        normalized = value.strip()

        if len(normalized) < 3:
            raise ValueError(
                "Void reason must contain at least "
                "three characters."
            )

        return normalized


class InvoicePaymentCreate(BaseModel):
    """
    Payload for recording a customer payment.
    """

    amount: Decimal = Field(
        gt=0,
        max_digits=14,
        decimal_places=2,
    )

    payment_date: date = Field(
        default_factory=date.today,
    )

    payment_method: InvoicePaymentMethod = Field(
        default=InvoicePaymentMethod.BANK_TRANSFER,
    )

    reference_number: str | None = Field(
        default=None,
        max_length=150,
    )

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    @field_validator(
        "reference_number",
        "notes",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        """
        Convert blank payment text fields to null.
        """

        if value is None:
            return None

        normalized = value.strip()

        return normalized or None


class InvoicePaymentReverse(BaseModel):
    """
    Required explanation for reversing a payment.
    """

    reason: str = Field(
        min_length=3,
        max_length=2000,
    )

    @field_validator("reason")
    @classmethod
    def normalize_reason(
        cls,
        value: str,
    ) -> str:
        """
        Trim and validate a payment reversal reason.
        """

        normalized = value.strip()

        if len(normalized) < 3:
            raise ValueError(
                "Reversal reason must contain at least "
                "three characters."
            )

        return normalized


class InvoiceLineItemResponse(BaseModel):
    """
    One invoice line-item response.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    invoice_id: uuid.UUID
    work_order_expense_id: uuid.UUID | None

    source_type: InvoiceLineSource

    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal

    position: int
    is_active: bool

    created_at: datetime
    updated_at: datetime


class InvoicePaymentResponse(BaseModel):
    """
    One invoice payment response.
    """

    id: uuid.UUID
    invoice_id: uuid.UUID

    recorded_by_user_id: uuid.UUID | None
    recorded_by_first_name: str | None
    recorded_by_last_name: str | None
    recorded_by_email: str | None

    reversed_by_user_id: uuid.UUID | None
    reversed_by_first_name: str | None
    reversed_by_last_name: str | None
    reversed_by_email: str | None

    amount: Decimal
    currency: str
    payment_date: date
    payment_method: InvoicePaymentMethod

    reference_number: str | None
    notes: str | None

    is_reversed: bool
    reversed_at: datetime | None
    reversal_reason: str | None

    created_at: datetime
    updated_at: datetime


class InvoiceResponse(BaseModel):
    """
    Complete invoice response.
    """

    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID
    work_order_id: uuid.UUID

    created_by_user_id: uuid.UUID | None
    created_by_first_name: str | None
    created_by_last_name: str | None
    created_by_email: str | None

    issued_by_user_id: uuid.UUID | None
    issued_by_first_name: str | None
    issued_by_last_name: str | None
    issued_by_email: str | None

    voided_by_user_id: uuid.UUID | None
    voided_by_first_name: str | None
    voided_by_last_name: str | None
    voided_by_email: str | None

    invoice_number: str
    currency: str
    status: InvoiceStatus

    invoice_date: date
    due_date: date | None

    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    balance_due: Decimal

    customer_name: str
    customer_email: str | None
    customer_phone: str | None
    billing_address: str | None

    notes: str | None
    terms: str | None

    issued_at: datetime | None
    paid_at: datetime | None
    voided_at: datetime | None
    void_reason: str | None

    is_active: bool

    line_items: list[
        InvoiceLineItemResponse
    ] = Field(
        default_factory=list,
    )

    payments: list[
        InvoicePaymentResponse
    ] = Field(
        default_factory=list,
    )

    created_at: datetime
    updated_at: datetime


class InvoiceListResponse(BaseModel):
    """
    Paginated invoice collection.
    """

    items: list[InvoiceResponse] = Field(
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


class InvoiceCurrencySummary(BaseModel):
    """
    Billing totals for one currency.
    """

    currency: str

    invoice_count: int = Field(
        ge=0,
    )

    total_invoiced: Decimal = Field(
        ge=0,
    )

    total_paid: Decimal = Field(
        ge=0,
    )

    total_outstanding: Decimal = Field(
        ge=0,
    )

    draft_count: int = Field(
        ge=0,
    )

    issued_count: int = Field(
        ge=0,
    )

    partially_paid_count: int = Field(
        ge=0,
    )

    paid_count: int = Field(
        ge=0,
    )

    void_count: int = Field(
        ge=0,
    )


class InvoiceSummaryResponse(BaseModel):
    """
    Organization invoice totals separated by currency.
    """

    currencies: list[
        InvoiceCurrencySummary
    ] = Field(
        default_factory=list,
    )