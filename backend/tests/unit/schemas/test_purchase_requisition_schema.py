"""Unit tests for purchase requisition validation."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.purchase_requisition import (
    CreatePurchaseRequisitionSchema,
    PurchaseRequisitionLineCreate,
    RejectPurchaseRequisitionSchema,
    UpdatePurchaseRequisitionSchema,
)


def test_create_schema_normalizes_core_values() -> None:
    payload = CreatePurchaseRequisitionSchema(
        requisition_number=" pr-001 ",
        title="  Pump replacement  ",
        priority="URGENT",
        currency="ngn",
        line_items=[
            PurchaseRequisitionLineCreate(
                description="  Replacement pump  ",
                quantity="2.500",
                unit_of_measure=" EACH ",
                estimated_unit_cost="1250.1250",
            )
        ],
    )

    assert payload.requisition_number == "PR-001"
    assert payload.title == "Pump replacement"
    assert payload.priority == "urgent"
    assert payload.currency == "NGN"
    assert payload.line_items[0].description == "Replacement pump"
    assert payload.line_items[0].unit_of_measure == "each"
    assert payload.line_items[0].quantity == Decimal("2.500")


def test_create_schema_rejects_duplicate_positions() -> None:
    with pytest.raises(ValidationError):
        CreatePurchaseRequisitionSchema(
            title="Duplicate positions",
            line_items=[
                PurchaseRequisitionLineCreate(
                    description="First",
                    position=0,
                ),
                PurchaseRequisitionLineCreate(
                    description="Second",
                    position=0,
                ),
            ],
        )


def test_line_rejects_non_positive_quantity() -> None:
    with pytest.raises(ValidationError):
        PurchaseRequisitionLineCreate(
            description="Invalid quantity",
            quantity="0",
        )


def test_create_schema_rejects_invalid_currency() -> None:
    with pytest.raises(ValidationError):
        CreatePurchaseRequisitionSchema(
            title="Invalid currency",
            currency="N1",
        )


def test_update_schema_rejects_blank_title() -> None:
    with pytest.raises(ValidationError):
        UpdatePurchaseRequisitionSchema(
            title="   ",
        )


def test_rejection_requires_a_reason() -> None:
    with pytest.raises(ValidationError):
        RejectPurchaseRequisitionSchema(
            reason="   ",
        )
