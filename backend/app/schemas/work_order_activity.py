"""
Work-order activity schemas.

Defines API responses for immutable work-order timeline entries.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


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
    "checklist_item_created",
    "checklist_item_updated",
    "checklist_item_completed",
    "checklist_item_skipped",
    "checklist_item_reopened",
    "checklist_reordered",
    "checklist_item_deactivated",
    "checklist_item_reactivated",
    "work_order_note_created",
    "work_order_note_updated",
    "work_order_note_deactivated",
    "work_order_note_reactivated",
    "work_order_note_attachment_added",
    "work_order_note_attachment_removed",
    "work_order_expense_created",
    "work_order_expense_updated",
    "work_order_expense_status_changed",
    "work_order_expense_deactivated",
    "work_order_expense_reactivated",
    "invoice_created",
    "invoice_updated",
    "invoice_line_item_added",
    "invoice_line_item_updated",
    "invoice_line_item_removed",
    "invoice_issued",
    "invoice_payment_recorded",
    "invoice_payment_reversed",
    "invoice_voided",

    "closeout_submitted",
    "closeout_updated",
    "closeout_approved",
    "closeout_rejected",
    "closeout_invoice_ready",
    "invoice_created_from_closeout",]


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