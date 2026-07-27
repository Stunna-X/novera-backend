"""Schemas for procurement workflow alerts and user preferences."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


ProcurementAlertType = Literal[
    "requisition_approval_required",
    "purchase_order_delivery_due",
    "purchase_order_delivery_overdue",
    "supplier_bill_overdue",
    "supplier_bill_match_exception",
    "supplier_payment_action_required",
]


class ProcurementAlertPreferenceUpdate(BaseModel):
    """Editable alert settings for the current organization user."""

    requisition_approval_enabled: bool | None = None
    purchase_order_delivery_enabled: bool | None = None
    supplier_bill_overdue_enabled: bool | None = None
    match_exception_enabled: bool | None = None
    payment_action_enabled: bool | None = None
    delivery_lead_days: int | None = Field(
        default=None,
        ge=0,
        le=30,
    )
    payment_lead_days: int | None = Field(
        default=None,
        ge=0,
        le=30,
    )
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError(
                "At least one procurement alert preference must be supplied."
            )
        return self


class ProcurementAlertPreferenceResponse(BaseModel):
    """Current effective procurement alert preferences."""

    model_config = ConfigDict(from_attributes=True)

    organization_id: uuid.UUID
    user_id: uuid.UUID
    requisition_approval_enabled: bool
    purchase_order_delivery_enabled: bool
    supplier_bill_overdue_enabled: bool
    match_exception_enabled: bool
    payment_action_enabled: bool
    delivery_lead_days: int = Field(ge=0, le=30)
    payment_lead_days: int = Field(ge=0, le=30)
    is_active: bool
    persisted: bool


class ProcurementAlertDispatchRequest(BaseModel):
    """Run procurement-alert evaluation for one business date."""

    as_of_date: date | None = None


class ProcurementAlertDispatchResponse(BaseModel):
    """Result of one idempotent procurement-alert dispatch."""

    as_of_date: date
    candidate_count: int = Field(ge=0)
    delivered_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    disabled_count: int = Field(ge=0)


class ProcurementAlertDeliveryResponse(BaseModel):
    """One persisted procurement alert delivery."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    recipient_user_id: uuid.UUID
    notification_id: uuid.UUID | None
    alert_type: ProcurementAlertType
    entity_type: str
    entity_id: uuid.UUID
    alert_date: date
    deduplication_key: str
    status: str
    delivered_at: datetime | None
    details: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProcurementAlertDeliveryListResponse(BaseModel):
    """Paginated delivery-history response."""

    items: list[ProcurementAlertDeliveryResponse]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
