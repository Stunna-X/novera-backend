"""
Work-order activity schemas.

Defines API responses for work-order timeline entries.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    Field,
)


WorkOrderActivityType = Literal[
    "created",
    "updated",
    "status_changed",
    "workforce_assigned",
    "workforce_removed",
    "asset_assigned",
    "asset_removed",
    "deactivated",
    "reactivated",
]


class WorkOrderActivityResponse(BaseModel):
    """
    One work-order activity timeline entry.
    """

    id: uuid.UUID
    organization_id: uuid.UUID
    work_order_id: uuid.UUID

    actor_user_id: uuid.UUID | None

    actor_first_name: str | None
    actor_last_name: str | None
    actor_email: str | None

    activity_type: WorkOrderActivityType
    summary: str

    from_status: str | None
    to_status: str | None

    note: str | None

    details: dict[str, Any] = Field(
        default_factory=dict,
    )

    created_at: datetime


class WorkOrderActivityListResponse(BaseModel):
    """
    Paginated work-order activity collection.
    """

    items: list[WorkOrderActivityResponse] = Field(
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