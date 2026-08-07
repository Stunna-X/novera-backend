"""
Validation and response schemas for work-order material readiness.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from app.schemas.purchase_requisition import (
    PurchaseRequisitionResponse,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


WorkOrderMaterialReadinessStatus = Literal[
    "available",
    "partial",
    "missing",
]


def _normalize_optional_text(value: object) -> object:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None

    return value


class WorkOrderMaterialCreate(BaseModel):
    """Add one inventory requirement to a work order."""

    inventory_item_id: uuid.UUID

    required_quantity: Decimal = Field(
        gt=Decimal("0"),
        max_digits=16,
        decimal_places=3,
    )

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    position: int | None = Field(
        default=None,
        ge=0,
    )

    details: dict[str, Any] = Field(
        default_factory=dict,
    )

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: object) -> object:
        return _normalize_optional_text(value)


class WorkOrderMaterialUpdate(BaseModel):
    """Change a work-order material requirement."""

    required_quantity: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
        max_digits=16,
        decimal_places=3,
    )

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    position: int | None = Field(
        default=None,
        ge=0,
    )

    details: dict[str, Any] | None = None

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: object) -> object:
        return _normalize_optional_text(value)


class WorkOrderMaterialItemSummary(BaseModel):
    """Inventory catalogue details shown with a requirement."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    name: str
    item_type: str
    category: str | None
    unit_of_measure: str
    default_unit_cost: Decimal
    currency: str
    is_active: bool


class WorkOrderMaterialResponse(BaseModel):
    """One requirement with live organization-wide stock coverage."""

    id: uuid.UUID
    organization_id: uuid.UUID
    work_order_id: uuid.UUID
    inventory_item_id: uuid.UUID

    required_quantity: Decimal
    quantity_on_hand: Decimal
    quantity_reserved: Decimal
    available_quantity: Decimal
    reserved_for_work_order: Decimal
    covered_quantity: Decimal
    missing_quantity: Decimal
    coverage_percentage: Decimal

    readiness_status: WorkOrderMaterialReadinessStatus
    active_location_count: int = Field(ge=0)

    estimated_unit_cost: Decimal
    estimated_line_cost: Decimal
    currency: str

    notes: str | None
    position: int
    details: dict[str, Any]
    is_active: bool

    created_by_user_id: uuid.UUID | None
    updated_by_user_id: uuid.UUID | None

    item: WorkOrderMaterialItemSummary

    created_at: datetime
    updated_at: datetime


class WorkOrderMaterialListResponse(BaseModel):
    """Paginated material requirements and readiness summary."""

    items: list[WorkOrderMaterialResponse] = Field(
        default_factory=list,
    )

    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1)

    available_lines: int = Field(ge=0)
    partial_lines: int = Field(ge=0)
    missing_lines: int = Field(ge=0)

    all_materials_ready: bool
    total_estimated_cost: Decimal = Field(ge=Decimal("0"))

class WorkOrderMaterialPurchaseRequestCreate(BaseModel):
    """Options for creating a shortage purchase request."""

    requested_delivery_date: date | None = None

    justification: str | None = Field(
        default=None,
        max_length=10000,
    )

    notes: str | None = Field(
        default=None,
        max_length=10000,
    )

    details: dict[str, Any] = Field(
        default_factory=dict,
    )

    @field_validator(
        "justification",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        return _normalize_optional_text(value)


class WorkOrderMaterialPurchaseRequestResponse(BaseModel):
    """Draft requisition created from live job shortages."""

    created: bool
    shortage_line_count: int = Field(ge=1)
    source_requirement_ids: list[uuid.UUID] = Field(
        min_length=1,
    )
    requisition: PurchaseRequisitionResponse
