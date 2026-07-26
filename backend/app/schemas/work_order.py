"""
Work-order schemas.

Defines request validation and API responses for
field-service work orders.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)


WorkOrderPriority = Literal[
    "low",
    "normal",
    "high",
    "urgent",
]

WorkOrderStatus = Literal[
    "draft",
    "scheduled",
    "dispatched",
    "in_progress",
    "on_hold",
    "completed",
    "cancelled",
]


class CreateWorkOrderSchema(BaseModel):
    """
    Payload used to create a work order.
    """

    customer_id: uuid.UUID
    customer_site_id: uuid.UUID | None = None

    work_order_number: str | None = Field(
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

    job_type: str | None = Field(
        default=None,
        max_length=100,
    )

    customer_reference: str | None = Field(
        default=None,
        max_length=100,
    )

    priority: WorkOrderPriority = "normal"
    status: WorkOrderStatus = "draft"

    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None

    estimated_cost: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        decimal_places=2,
    )

    instructions: str | None = Field(
        default=None,
        max_length=10000,
    )

    @field_validator(
        "work_order_number",
        mode="before",
    )
    @classmethod
    def normalize_work_order_number(
        cls,
        value: object,
    ) -> object:
        """
        Normalize a supplied work-order number.
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
        Normalize and validate the title.
        """

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Work-order title cannot be empty."
                )

            return normalized

        return value

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
        Convert blank optional strings to None.
        """

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value

    @field_validator(
        "priority",
        "status",
        mode="before",
    )
    @classmethod
    def normalize_choice(
        cls,
        value: object,
    ) -> object:
        """
        Normalize controlled choice values.
        """

        if isinstance(value, str):
            return value.strip().lower()

        return value

    @model_validator(mode="after")
    def validate_schedule(
        self,
    ) -> "CreateWorkOrderSchema":
        """
        Validate the work-order schedule.
        """

        if (
            self.scheduled_start is not None
            and self.scheduled_end is not None
            and self.scheduled_end <= self.scheduled_start
        ):
            raise ValueError(
                "Scheduled end must be after scheduled start."
            )

        if (
            self.status == "scheduled"
            and self.scheduled_start is None
        ):
            raise ValueError(
                "Scheduled start is required for "
                "a scheduled work order."
            )

        return self


class UpdateWorkOrderSchema(BaseModel):
    """
    Payload used to update work-order details.

    Status changes are handled through the dedicated
    work-order status endpoint.
    """

    customer_id: uuid.UUID | None = None
    customer_site_id: uuid.UUID | None = None

    work_order_number: str | None = Field(
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

    job_type: str | None = Field(
        default=None,
        max_length=100,
    )

    customer_reference: str | None = Field(
        default=None,
        max_length=100,
    )

    priority: WorkOrderPriority | None = None

    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None

    estimated_cost: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        decimal_places=2,
    )

    actual_cost: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        decimal_places=2,
    )

    instructions: str | None = Field(
        default=None,
        max_length=10000,
    )

    completion_notes: str | None = Field(
        default=None,
        max_length=10000,
    )

    @field_validator(
        "work_order_number",
        mode="before",
    )
    @classmethod
    def normalize_work_order_number(
        cls,
        value: object,
    ) -> object:
        """
        Normalize a supplied work-order number.
        """

        if isinstance(value, str):
            normalized = value.strip().upper()

            if not normalized:
                raise ValueError(
                    "Work-order number cannot be empty."
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
        Normalize and validate a supplied title.
        """

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Work-order title cannot be empty."
                )

            return normalized

        return value

    @field_validator(
        "description",
        "job_type",
        "customer_reference",
        "instructions",
        "completion_notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """
        Convert blank optional strings to None.
        """

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value

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
        Normalize priority values.
        """

        if isinstance(value, str):
            return value.strip().lower()

        return value


class ChangeWorkOrderStatusSchema(BaseModel):
    """
    Payload used to change work-order status.
    """

    status: WorkOrderStatus

    note: str | None = Field(
        default=None,
        max_length=10000,
    )

    @field_validator(
        "status",
        mode="before",
    )
    @classmethod
    def normalize_status(
        cls,
        value: object,
    ) -> object:
        """
        Normalize status values.
        """

        if isinstance(value, str):
            return value.strip().lower()

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
        """
        Convert a blank status note to None.
        """

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value


class WorkOrderResponse(BaseModel):
    """
    Work order returned by the API.
    """

    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID
    customer_site_id: uuid.UUID | None

    work_order_number: str
    title: str
    description: str | None
    job_type: str | None
    customer_reference: str | None

    priority: WorkOrderPriority
    status: WorkOrderStatus

    scheduled_start: datetime | None
    scheduled_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None

    estimated_cost: Decimal | None
    actual_cost: Decimal | None

    instructions: str | None
    completion_notes: str | None
    cancellation_reason: str | None

    workforce_profile_ids: list[uuid.UUID] = Field(
        default_factory=list,
    )

    asset_ids: list[uuid.UUID] = Field(
        default_factory=list,
    )

    is_active: bool

    created_at: datetime
    updated_at: datetime


class WorkOrderListResponse(BaseModel):
    """
    Paginated work-order collection.
    """

    items: list[WorkOrderResponse] = Field(
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