"""Work-order closeout schemas.

Defines request validation and API responses for completion
reports, customer approval, and invoice-readiness.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    field_validator,
)


WorkOrderCloseoutStatus = Literal[
    "submitted",
    "approved",
    "rejected",
]


class SubmitWorkOrderCloseoutSchema(BaseModel):
    """Payload used to submit a completed work-order report."""

    completion_summary: str = Field(
        min_length=1,
        max_length=10000,
    )

    work_performed: str | None = Field(
        default=None,
        max_length=10000,
    )

    materials_used: str | None = Field(
        default=None,
        max_length=10000,
    )

    customer_notes: str | None = Field(
        default=None,
        max_length=10000,
    )

    internal_notes: str | None = Field(
        default=None,
        max_length=10000,
    )

    note: str | None = Field(
        default=None,
        max_length=10000,
    )

    @field_validator(
        "completion_summary",
        mode="before",
    )
    @classmethod
    def normalize_required_text(
        cls,
        value: object,
    ) -> object:
        """Strip and validate required text."""

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Completion summary cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "work_performed",
        "materials_used",
        "customer_notes",
        "internal_notes",
        "note",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """Convert blank optional text values to None."""

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value


class UpdateWorkOrderCloseoutSchema(BaseModel):
    """Payload used to revise a pending closeout report."""

    completion_summary: str | None = Field(
        default=None,
        max_length=10000,
    )

    work_performed: str | None = Field(
        default=None,
        max_length=10000,
    )

    materials_used: str | None = Field(
        default=None,
        max_length=10000,
    )

    customer_notes: str | None = Field(
        default=None,
        max_length=10000,
    )

    internal_notes: str | None = Field(
        default=None,
        max_length=10000,
    )

    note: str | None = Field(
        default=None,
        max_length=10000,
    )

    @field_validator(
        "completion_summary",
        mode="before",
    )
    @classmethod
    def normalize_required_if_supplied(
        cls,
        value: object,
    ) -> object:
        """Strip supplied completion summary."""

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Completion summary cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "work_performed",
        "materials_used",
        "customer_notes",
        "internal_notes",
        "note",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """Convert blank optional text values to None."""

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value


class ApproveWorkOrderCloseoutSchema(BaseModel):
    """Payload used to capture customer sign-off."""

    customer_name: str = Field(
        min_length=1,
        max_length=160,
    )

    customer_email: EmailStr | None = None

    customer_phone: str | None = Field(
        default=None,
        max_length=50,
    )

    customer_title: str | None = Field(
        default=None,
        max_length=120,
    )

    customer_signature_url: str | None = Field(
        default=None,
        max_length=2000,
    )

    customer_rating: int | None = Field(
        default=None,
        ge=1,
        le=5,
    )

    customer_feedback: str | None = Field(
        default=None,
        max_length=10000,
    )

    ready_for_invoice: bool = True

    note: str | None = Field(
        default=None,
        max_length=10000,
    )

    @field_validator(
        "customer_name",
        mode="before",
    )
    @classmethod
    def normalize_customer_name(
        cls,
        value: object,
    ) -> object:
        """Strip and validate customer name."""

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Customer name cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "customer_phone",
        "customer_title",
        "customer_signature_url",
        "customer_feedback",
        "note",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """Convert blank optional values to None."""

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value


class RejectWorkOrderCloseoutSchema(BaseModel):
    """Payload used when the customer rejects a closeout."""

    rejection_reason: str = Field(
        min_length=1,
        max_length=10000,
    )

    note: str | None = Field(
        default=None,
        max_length=10000,
    )

    @field_validator(
        "rejection_reason",
        mode="before",
    )
    @classmethod
    def normalize_reason(
        cls,
        value: object,
    ) -> object:
        """Strip and validate rejection reason."""

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Rejection reason cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "note",
        mode="before",
    )
    @classmethod
    def normalize_note(
        cls,
        value: object,
    ) -> object:
        """Convert blank note to None."""

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value


class MarkCloseoutInvoiceReadySchema(BaseModel):
    """Payload used to mark an approved closeout invoice-ready."""

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
        """Convert blank note to None."""

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value


class WorkOrderCloseoutResponse(BaseModel):
    """Closeout returned by the API."""

    id: uuid.UUID
    organization_id: uuid.UUID
    work_order_id: uuid.UUID

    created_by_user_id: uuid.UUID | None
    submitted_by_user_id: uuid.UUID | None
    approved_by_user_id: uuid.UUID | None
    rejected_by_user_id: uuid.UUID | None
    invoice_ready_by_user_id: uuid.UUID | None

    status: WorkOrderCloseoutStatus

    completion_summary: str
    work_performed: str | None
    materials_used: str | None
    customer_notes: str | None
    internal_notes: str | None

    customer_name: str | None
    customer_email: EmailStr | None
    customer_phone: str | None
    customer_title: str | None
    customer_signature_url: str | None
    customer_rating: int | None
    customer_feedback: str | None

    rejection_reason: str | None

    submitted_at: datetime | None
    approved_at: datetime | None
    rejected_at: datetime | None
    invoice_ready_at: datetime | None
    is_invoice_ready: bool

    created_at: datetime
    updated_at: datetime
