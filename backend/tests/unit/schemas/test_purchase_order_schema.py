"""Unit tests for purchase order validation."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.purchase_order import (
    CancelPurchaseOrderSchema,
    CreatePurchaseOrderSchema,
    PurchaseOrderLineCreate,
    UpdatePurchaseOrderSchema,
)


def test_create_schema_normalizes_core_values() -> None:
    payload = CreatePurchaseOrderSchema(
        purchase_order_number=" po-001 ",
        supplier_id="00000000-0000-0000-0000-000000000001",
        title="  Pump supply  ",
        currency="ngn",
        supplier_reference=" quote-77 ",
        line_items=[
            PurchaseOrderLineCreate(
                description="  Submersible pump  ",
                quantity_ordered="2.500",
                unit_of_measure=" EACH ",
                unit_price="1000.0000",
                tax_rate="7.5000",
            )
        ],
    )

    assert payload.purchase_order_number == "PO-001"
    assert payload.title == "Pump supply"
    assert payload.currency == "NGN"
    assert payload.supplier_reference == "quote-77"
    assert payload.line_items[0].description == "Submersible pump"
    assert payload.line_items[0].unit_of_measure == "each"
    assert payload.line_items[0].quantity_ordered == Decimal("2.500")


def test_line_rejects_discount_above_subtotal() -> None:
    with pytest.raises(ValidationError):
        PurchaseOrderLineCreate(
            description="Invalid discount",
            quantity_ordered="2.000",
            unit_price="10.0000",
            discount_amount="20.01",
        )


def test_line_rejects_tax_rate_above_one_hundred() -> None:
    with pytest.raises(ValidationError):
        PurchaseOrderLineCreate(
            description="Invalid tax",
            tax_rate="100.0001",
        )


def test_create_schema_rejects_duplicate_positions() -> None:
    with pytest.raises(ValidationError):
        CreatePurchaseOrderSchema(
            supplier_id="00000000-0000-0000-0000-000000000001",
            title="Duplicate positions",
            line_items=[
                PurchaseOrderLineCreate(
                    description="First",
                    position=0,
                ),
                PurchaseOrderLineCreate(
                    description="Second",
                    position=0,
                ),
            ],
        )


def test_create_schema_rejects_invalid_currency() -> None:
    with pytest.raises(ValidationError):
        CreatePurchaseOrderSchema(
            supplier_id="00000000-0000-0000-0000-000000000001",
            title="Invalid currency",
            currency="N1",
        )


def test_update_schema_rejects_blank_title() -> None:
    with pytest.raises(ValidationError):
        UpdatePurchaseOrderSchema(title="   ")


def test_cancellation_requires_reason() -> None:
    with pytest.raises(ValidationError):
        CancelPurchaseOrderSchema(reason="   ")
