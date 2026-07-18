"""
Audit log schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


AuditLogStatus = Literal[
    "success",
    "failure",
    "warning",
    "info",
]


class AuditLogCreate(BaseModel):
    """
    Internal schema for creating audit events.
    """

    actor_user_id: uuid.UUID | None = None
    actor_membership_id: uuid.UUID | None = None

    action: str = Field(
        ...,
        min_length=2,
        max_length=120,
    )

    entity_type: str | None = Field(
        default=None,
        max_length=80,
    )

    entity_id: uuid.UUID | None = None

    summary: str | None = Field(
        default=None,
        max_length=2000,
    )

    status: AuditLogStatus = "success"

    request_method: str | None = Field(
        default=None,
        max_length=12,
    )

    request_path: str | None = Field(
        default=None,
        max_length=500,
    )

    ip_address: str | None = Field(
        default=None,
        max_length=80,
    )

    user_agent: str | None = Field(
        default=None,
        max_length=2000,
    )

    details: dict[str, Any] = Field(
        default_factory=dict,
    )


class AuditLogResponse(BaseModel):
    """
    Audit event returned by the API.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    organization_id: uuid.UUID

    actor_user_id: uuid.UUID | None
    actor_first_name: str | None
    actor_last_name: str | None
    actor_email: str | None
    actor_membership_id: uuid.UUID | None

    action: str
    entity_type: str | None
    entity_id: uuid.UUID | None
    summary: str | None
    status: str

    request_method: str | None
    request_path: str | None
    ip_address: str | None
    user_agent: str | None

    details: dict[str, Any]

    created_at: datetime
    updated_at: datetime


class AuditLogListResponse(BaseModel):
    """
    Paginated audit-log response.
    """

    items: list[AuditLogResponse]
    total: int
    skip: int
    limit: int
