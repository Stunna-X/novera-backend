"""Validation tests for work-order material schemas."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.work_order_material import (
    WorkOrderMaterialCreate,
    WorkOrderMaterialUpdate,
)


pytestmark = pytest.mark.unit


def test_create_schema_normalizes_blank_notes() -> None:
    payload = WorkOrderMaterialCreate(
        inventory_item_id=uuid.uuid4(),
        required_quantity=Decimal("12.500"),
        notes="   ",
    )

    assert payload.notes is None
    assert payload.required_quantity == Decimal("12.500")


def test_create_schema_rejects_non_positive_quantity() -> None:
    with pytest.raises(ValidationError):
        WorkOrderMaterialCreate(
            inventory_item_id=uuid.uuid4(),
            required_quantity=Decimal("0"),
        )


def test_update_schema_rejects_negative_position() -> None:
    with pytest.raises(ValidationError):
        WorkOrderMaterialUpdate(position=-1)
