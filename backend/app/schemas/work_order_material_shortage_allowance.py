"""
Pydantic schemas for work-order material shortage allowances.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


ShortageAllowanceStatus = Literal[
    "draft",
    "submitted",
    "approved",
    "rejected",
    "cancelled",
]


def _normalize_required_text(value: str) -> str:
    normalized = value.strip()

    if not normalized:
        raise ValueError("Value cannot be empty.")

    return normalized


def _normalize_optional_text(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    return normalized or None


class WorkOrderMaterialShortageAllowanceCreate(
    BaseModel
):
    """Create a new draft shortage allowance."""

    requested_quantity: Decimal = Field(
        ...,
        gt=Decimal("0"),
        max_digits=16,
        decimal_places=3,
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=5000,
    )
    notes: str | None = Field(
        default=None,
        max_length=5000,
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
    )

    @field_validator("reason")
    @classmethod
    def validate_reason(
        cls,
        value: str,
    ) -> str:
        return _normalize_required_text(value)

    @field_validator("notes")
    @classmethod
    def validate_notes(
        cls,
        value: str | None,
    ) -> str | None:
        return _normalize_optional_text(value)

    @field_validator("details")
    @classmethod
    def normalize_details(
        cls,
        value: dict[str, Any],
    ) -> dict[str, Any]:
        return dict(value)


class WorkOrderMaterialShortageAllowanceUpdate(
    BaseModel
):
    """Update a draft or rejected shortage allowance."""

    requested_quantity: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
        max_digits=16,
        decimal_places=3,
    )
    reason: str | None = Field(
        default=None,
        min_length=1,
        max_length=5000,
    )
    notes: str | None = Field(
        default=None,
        max_length=5000,
    )
    details: dict[str, Any] | None = None

    @field_validator("reason")
    @classmethod
    def validate_reason(
        cls,
        value: str | None,
    ) -> str | None:
        return (
            _normalize_required_text(value)
            if value is not None
            else None
        )

    @field_validator("notes")
    @classmethod
    def validate_notes(
        cls,
        value: str | None,
    ) -> str | None:
        return _normalize_optional_text(value)

    @field_validator("details")
    @classmethod
    def normalize_details(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        return (
            dict(value)
            if value is not None
            else None
        )


class WorkOrderMaterialShortageAllowanceApprove(
    BaseModel
):
    """Approve a submitted shortage allowance."""

    approved_quantity: Decimal = Field(
        ...,
        gt=Decimal("0"),
        max_digits=16,
        decimal_places=3,
    )


class WorkOrderMaterialShortageAllowanceReject(
    BaseModel
):
    """Reject a submitted shortage allowance."""

    rejection_reason: str = Field(
        ...,
        min_length=1,
        max_length=5000,
    )

    @field_validator("rejection_reason")
    @classmethod
    def validate_rejection_reason(
        cls,
        value: str,
    ) -> str:
        return _normalize_required_text(value)


class WorkOrderMaterialShortageAllowanceCancel(
    BaseModel
):
    """Cancel or revoke an eligible shortage allowance."""

    cancellation_reason: str = Field(
        ...,
        min_length=1,
        max_length=5000,
    )

    @field_validator("cancellation_reason")
    @classmethod
    def validate_cancellation_reason(
        cls,
        value: str,
    ) -> str:
        return _normalize_required_text(value)


class WorkOrderMaterialShortageAllowanceResponse(
    BaseModel
):
    """API representation of a material shortage allowance."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    organization_id: uuid.UUID
    work_order_id: uuid.UUID
    work_order_material_requirement_id: uuid.UUID
    inventory_item_id: uuid.UUID

    required_quantity: Decimal
    current_missing_quantity: Decimal

    requested_quantity: Decimal
    approved_quantity: Decimal

    status: ShortageAllowanceStatus

    reason: str
    notes: str | None

    created_by_user_id: uuid.UUID | None
    submitted_by_user_id: uuid.UUID | None
    approved_by_user_id: uuid.UUID | None
    rejected_by_user_id: uuid.UUID | None
    cancelled_by_user_id: uuid.UUID | None

    submitted_at: datetime | None
    approved_at: datetime | None
    rejected_at: datetime | None
    cancelled_at: datetime | None

    rejection_reason: str | None
    cancellation_reason: str | None

    details: dict[str, Any]
    is_active: bool

    created_at: datetime
    updated_at: datetime


class WorkOrderMaterialShortageAllowanceListResponse(
    BaseModel
):
    """Paginated shortage allowance response."""

    items: list[
        WorkOrderMaterialShortageAllowanceResponse
    ]
    total: int
    skip: int
    limit: int