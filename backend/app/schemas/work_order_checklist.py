"""
Work-order checklist schemas.

Defines request and response payloads for checklist-item operations.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.enums.work_order_checklist import WorkOrderChecklistStatus


class WorkOrderChecklistItemCreate(BaseModel):
    """
    Payload for creating a checklist item.
    """

    title: str = Field(
        min_length=1,
        max_length=255,
    )

    description: str | None = Field(
        default=None,
        max_length=5000,
    )

    is_required: bool = True

    position: int | None = Field(
        default=None,
        ge=0,
    )

    @field_validator("title")
    @classmethod
    def normalize_title(
        cls,
        value: str,
    ) -> str:
        """
        Strip surrounding whitespace from the title.
        """

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Checklist-item title cannot be empty."
            )

        return normalized

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

        return normalized or None


class WorkOrderChecklistItemUpdate(BaseModel):
    """
    Payload for updating checklist-item details.
    """

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    description: str | None = Field(
        default=None,
        max_length=5000,
    )

    is_required: bool | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(
        cls,
        value: str | None,
    ) -> str | None:
        """
        Strip surrounding whitespace from an optional title.
        """

        if value is None:
            return None

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Checklist-item title cannot be empty."
            )

        return normalized

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

        return normalized or None


class WorkOrderChecklistStatusUpdate(BaseModel):
    """
    Payload for completing, skipping, or reopening an item.
    """

    status: WorkOrderChecklistStatus

    note: str | None = Field(
        default=None,
        max_length=5000,
    )

    @field_validator("note")
    @classmethod
    def normalize_note(
        cls,
        value: str | None,
    ) -> str | None:
        """
        Normalize an optional completion or skip note.
        """

        if value is None:
            return None

        normalized = value.strip()

        return normalized or None


class WorkOrderChecklistReorderRequest(BaseModel):
    """
    Payload containing the desired checklist-item order.
    """

    item_ids: list[uuid.UUID] = Field(
        min_length=1,
    )

    @field_validator("item_ids")
    @classmethod
    def validate_unique_item_ids(
        cls,
        value: list[uuid.UUID],
    ) -> list[uuid.UUID]:
        """
        Reject duplicate checklist-item IDs.
        """

        if len(value) != len(set(value)):
            raise ValueError(
                "Checklist-item IDs must be unique."
            )

        return value


class WorkOrderChecklistItemResponse(BaseModel):
    """
    Public checklist-item response.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    work_order_id: uuid.UUID

    title: str
    description: str | None

    status: WorkOrderChecklistStatus
    is_required: bool
    position: int

    completion_note: str | None
    completed_by_user_id: uuid.UUID | None
    completed_at: datetime | None

    skipped_by_user_id: uuid.UUID | None
    skipped_at: datetime | None

    is_active: bool

    created_at: datetime
    updated_at: datetime


class WorkOrderChecklistListResponse(BaseModel):
    """
    Paginated checklist-item response.
    """

    items: list[WorkOrderChecklistItemResponse]
    total: int
    skip: int
    limit: int


class WorkOrderChecklistProgressResponse(BaseModel):
    """
    Checklist completion summary for one work order.
    """

    total_items: int
    pending_items: int
    completed_items: int
    skipped_items: int

    required_items: int
    completed_required_items: int
    incomplete_required_items: int

    completion_percentage: float
    can_complete_work_order: bool