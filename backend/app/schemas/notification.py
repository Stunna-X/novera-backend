"""
Notification schemas.

Defines request validation and API responses for user
notifications.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


NotificationPriority = Literal[
    "info",
    "success",
    "warning",
    "error",
]


class CreateNotificationSchema(BaseModel):
    """
    Payload used to create a notification.

    If recipient_user_id is omitted, the current user receives
    the notification.
    """

    recipient_user_id: uuid.UUID | None = None

    notification_type: str = Field(
        min_length=1,
        max_length=80,
    )

    title: str = Field(
        min_length=1,
        max_length=180,
    )

    message: str = Field(
        min_length=1,
        max_length=10000,
    )

    priority: NotificationPriority = "info"

    entity_type: str | None = Field(
        default=None,
        max_length=80,
    )

    entity_id: uuid.UUID | None = None

    action_url: str | None = Field(
        default=None,
        max_length=500,
    )

    payload: dict[str, Any] = Field(
        default_factory=dict,
    )

    @field_validator(
        "notification_type",
        "title",
        "message",
        mode="before",
    )
    @classmethod
    def normalize_required_text(
        cls,
        value: object,
    ) -> object:
        """
        Strip required text fields and reject blank values.
        """

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    "Value cannot be empty."
                )

            return normalized

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

    @field_validator(
        "entity_type",
        "action_url",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """
        Convert blank optional text to None.
        """

        if isinstance(value, str):
            normalized = value.strip()

            return normalized or None

        return value


class NotificationResponse(BaseModel):
    """
    Notification returned by the API.
    """

    id: uuid.UUID
    organization_id: uuid.UUID
    recipient_user_id: uuid.UUID
    actor_user_id: uuid.UUID | None

    notification_type: str
    title: str
    message: str
    priority: NotificationPriority

    entity_type: str | None
    entity_id: uuid.UUID | None
    action_url: str | None
    payload: dict[str, Any]

    is_read: bool
    read_at: datetime | None

    is_archived: bool
    archived_at: datetime | None

    created_at: datetime
    updated_at: datetime


class NotificationListResponse(BaseModel):
    """
    Paginated notification collection.
    """

    items: list[NotificationResponse] = Field(
        default_factory=list,
    )

    total: int = Field(
        ge=0,
    )

    unread_count: int = Field(
        ge=0,
    )

    skip: int = Field(
        ge=0,
    )

    limit: int = Field(
        ge=1,
    )


class NotificationUnreadCountResponse(BaseModel):
    """
    Unread notification count.
    """

    organization_id: uuid.UUID
    unread_count: int = Field(
        ge=0,
    )


class NotificationBulkUpdateResponse(BaseModel):
    """
    Bulk notification update result.
    """

    organization_id: uuid.UUID
    updated_count: int = Field(
        ge=0,
    )
