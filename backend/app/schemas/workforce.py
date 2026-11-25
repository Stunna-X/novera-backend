"""
Workforce schemas.

Defines validation and API responses for organization
workforce profiles.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


EmploymentType = Literal[
    "full_time",
    "part_time",
    "contractor",
    "casual",
    "intern",
]

WorkforceStatus = Literal[
    "active",
    "inactive",
    "on_leave",
    "suspended",
]


class CreateWorkforceProfileSchema(BaseModel):
    """Payload used to create a workforce profile."""

    full_name: str = Field(
        min_length=1,
        max_length=200,
    )

    job_title: str | None = Field(
        default=None,
        max_length=120,
    )

    employment_type: EmploymentType | None = None

    phone: str | None = Field(
        default=None,
        max_length=50,
    )

    status: WorkforceStatus = "active"

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_full_name(cls, value: object) -> object:
        """Normalize and validate the employee's full name."""

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError("Full name cannot be blank.")

            return normalized

        return value

    @field_validator(
        "job_title",
        "phone",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        """Convert blank optional strings to None."""

        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None

        return value


class UpdateWorkforceProfileSchema(BaseModel):
    """Payload used to update a workforce profile."""

    full_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    job_title: str | None = Field(
        default=None,
        max_length=120,
    )

    employment_type: EmploymentType | None = None

    phone: str | None = Field(
        default=None,
        max_length=50,
    )

    status: WorkforceStatus | None = None

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_full_name(cls, value: object) -> object:
        """Normalize and validate an updated full name."""

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                raise ValueError("Full name cannot be blank.")

            return normalized

        return value

    @field_validator(
        "job_title",
        "phone",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        """Convert blank optional strings to None."""

        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None

        return value


class WorkforceProfileResponse(BaseModel):
    """Workforce profile returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    full_name: str
    job_title: str | None = None
    employment_type: EmploymentType | None = None
    phone: str | None = None
    status: WorkforceStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime


class WorkforceProfileListResponse(BaseModel):
    """Paginated workforce collection."""

    items: list[WorkforceProfileResponse] = Field(
        default_factory=list,
    )

    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1)
