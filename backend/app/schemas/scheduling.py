"""
Scheduling schemas.

Defines request validation and API responses for work-order
scheduling, dispatch, calendar views, and conflict checks.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)

from app.schemas.work_order import WorkOrderResponse


ScheduleStatus = Literal[
    "draft",
    "scheduled",
    "dispatched",
    "in_progress",
    "on_hold",
    "completed",
    "cancelled",
]

ScheduleConflictType = Literal[
    "workforce",
    "asset",
]


class ScheduleConflictItem(BaseModel):
    """
    One resource booking conflict.
    """

    conflict_type: ScheduleConflictType

    resource_id: uuid.UUID
    resource_name: str | None = None

    work_order_id: uuid.UUID
    work_order_number: str
    title: str

    status: ScheduleStatus
    scheduled_start: datetime
    scheduled_end: datetime


class ScheduleConflictResponse(BaseModel):
    """
    Conflict-check response.
    """

    has_conflicts: bool
    conflicts: list[ScheduleConflictItem] = Field(
        default_factory=list,
    )


class ScheduleConflictCheckSchema(BaseModel):
    """
    Payload used to check schedule conflicts before booking.
    """

    scheduled_start: datetime
    scheduled_end: datetime

    workforce_profile_ids: list[uuid.UUID] = Field(
        default_factory=list,
        max_length=100,
    )

    asset_ids: list[uuid.UUID] = Field(
        default_factory=list,
        max_length=100,
    )

    exclude_work_order_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_window(
        self,
    ) -> "ScheduleConflictCheckSchema":
        """
        Validate that the time window is usable.
        """

        if self.scheduled_end <= self.scheduled_start:
            raise ValueError(
                "scheduled_end must be after scheduled_start."
            )

        return self


class ScheduleWorkOrderSchema(BaseModel):
    """
    Payload used to schedule a work order and optionally assign
    workforce members and assets in one operation.
    """

    scheduled_start: datetime
    scheduled_end: datetime

    workforce_profile_ids: list[uuid.UUID] | None = Field(
        default=None,
        max_length=100,
    )

    asset_ids: list[uuid.UUID] | None = Field(
        default=None,
        max_length=100,
    )

    set_status_to_scheduled: bool = True
    fail_on_conflict: bool = False

    note: str | None = Field(
        default=None,
        max_length=5000,
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
        Convert blank notes to None.
        """

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value

    @model_validator(mode="after")
    def validate_schedule(
        self,
    ) -> "ScheduleWorkOrderSchema":
        """
        Validate that scheduled_end is after scheduled_start.
        """

        if self.scheduled_end <= self.scheduled_start:
            raise ValueError(
                "scheduled_end must be after scheduled_start."
            )

        return self


class DispatchWorkOrderSchema(BaseModel):
    """
    Payload used to dispatch a scheduled work order.
    """

    note: str | None = Field(
        default=None,
        max_length=5000,
    )

    fail_on_conflict: bool = True

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
        Convert blank notes to None.
        """

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value


class ScheduleCalendarItem(BaseModel):
    """
    One work order in the dispatch calendar.
    """

    id: uuid.UUID
    organization_id: uuid.UUID

    work_order_number: str
    title: str
    description: str | None = None
    job_type: str | None = None

    customer_id: uuid.UUID
    customer_name: str | None = None

    customer_site_id: uuid.UUID | None = None
    customer_site_name: str | None = None

    priority: str
    status: ScheduleStatus

    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None

    workforce_profile_ids: list[uuid.UUID] = Field(
        default_factory=list,
    )

    asset_ids: list[uuid.UUID] = Field(
        default_factory=list,
    )


class ScheduleCalendarResponse(BaseModel):
    """
    Calendar collection response.
    """

    items: list[ScheduleCalendarItem] = Field(
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


class ScheduleWorkOrderResponse(BaseModel):
    """
    Response returned after scheduling or dispatching.
    """

    work_order: WorkOrderResponse
    conflicts: list[ScheduleConflictItem] = Field(
        default_factory=list,
    )
