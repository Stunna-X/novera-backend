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
    EmailStr,
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

    membership_id: uuid.UUID | None = None

    job_title: str | None = Field(
        default=None,
        max_length=120,
    )

    employment_type: EmploymentType | None = None

    phone: str | None = Field(
        default=None,
        max_length=50,
    )

    emergency_contact_name: str | None = Field(
        default=None,
        max_length=160,
    )

    emergency_contact_phone: str | None = Field(
        default=None,
        max_length=50,
    )

    skills: list[str] = Field(
        default_factory=list,
        max_length=100,
    )

    status: WorkforceStatus = "active"

    is_available: bool = True

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

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
        "emergency_contact_name",
        "emergency_contact_phone",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        """Convert blank optional strings to None."""

        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None

        return value

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skills(cls, value: object) -> object:
        """Normalize skills and remove case-insensitive duplicates."""

        if not isinstance(value, list):
            return value

        normalized_skills: list[str] = []

        for item in value:
            if not isinstance(item, str):
                raise ValueError("Each skill must be a string.")

            skill = item.strip()

            if (
                skill
                and skill.lower()
                not in {
                    existing.lower()
                    for existing in normalized_skills
                }
            ):
                normalized_skills.append(skill)

        return normalized_skills


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

    emergency_contact_name: str | None = Field(
        default=None,
        max_length=160,
    )

    emergency_contact_phone: str | None = Field(
        default=None,
        max_length=50,
    )

    skills: list[str] = Field(
        default_factory=list,
        max_length=100,
    )

    status: WorkforceStatus | None = None

    is_available: bool | None = None

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

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
        "emergency_contact_name",
        "emergency_contact_phone",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        """Convert blank optional strings to None."""

        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None

        return value

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skills(cls, value: object) -> object:
        """Normalize skills and remove case-insensitive duplicates."""

        if value is None or not isinstance(value, list):
            return value

        normalized_skills: list[str] = []

        for item in value:
            if not isinstance(item, str):
                raise ValueError("Each skill must be a string.")

            skill = item.strip()

            if (
                skill
                and skill.lower()
                not in {
                    existing.lower()
                    for existing in normalized_skills
                }
            ):
                normalized_skills.append(skill)

        return normalized_skills


class WorkforceProfileResponse(BaseModel):
    """Workforce profile returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    full_name: str

    membership_id: uuid.UUID | None = None

    # Optional account information.
    # Standalone employees do not need platform accounts.
    user_id: uuid.UUID | None = None
    email: EmailStr | None = None

    job_title: str | None = None
    employment_type: EmploymentType | None = None

    phone: str | None = None

    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    skills: list[str] = Field(
        default_factory=list,
    )

    status: WorkforceStatus
    is_available: bool
    is_active: bool

    notes: str | None = None

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
