"""Unit tests for goods receipt validation."""

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.goods_receipt import (
    CancelGoodsReceiptSchema,
    CreateGoodsReceiptSchema,
    GoodsReceiptLineCreate,
    GoodsReceiptLineUpdate,
    UpdateGoodsReceiptSchema,
)


PO_ID = "00000000-0000-0000-0000-000000000001"
LINE_ID = "00000000-0000-0000-0000-000000000002"
LOCATION_ID = "00000000-0000-0000-0000-000000000003"


def test_create_schema_normalizes_values() -> None:
    payload = CreateGoodsReceiptSchema(
        goods_receipt_number=" gr-001 ",
        purchase_order_id=PO_ID,
        receiving_location_id=LOCATION_ID,
        supplier_delivery_note=" dn-77 ",
        carrier_name="  North Haulage  ",
        line_items=[
            GoodsReceiptLineCreate(
                purchase_order_line_item_id=LINE_ID,
                quantity_accepted="2.500",
            )
        ],
    )

    assert payload.goods_receipt_number == "GR-001"
    assert payload.supplier_delivery_note == "dn-77"
    assert payload.carrier_name == "North Haulage"
    assert payload.line_items[0].quantity_accepted == Decimal("2.500")


def test_line_requires_positive_delivered_quantity() -> None:
    with pytest.raises(ValidationError):
        GoodsReceiptLineCreate(
            purchase_order_line_item_id=LINE_ID,
        )


def test_rejected_quantity_requires_reason() -> None:
    with pytest.raises(ValidationError):
        GoodsReceiptLineCreate(
            purchase_order_line_item_id=LINE_ID,
            quantity_rejected="1.000",
        )


def test_damaged_quantity_requires_notes() -> None:
    with pytest.raises(ValidationError):
        GoodsReceiptLineCreate(
            purchase_order_line_item_id=LINE_ID,
            quantity_damaged="1.000",
        )


def test_create_schema_rejects_duplicate_order_lines() -> None:
    with pytest.raises(ValidationError):
        CreateGoodsReceiptSchema(
            purchase_order_id=PO_ID,
            receiving_location_id=LOCATION_ID,
            line_items=[
                GoodsReceiptLineCreate(
                    purchase_order_line_item_id=LINE_ID,
                    quantity_accepted="1.000",
                ),
                GoodsReceiptLineCreate(
                    purchase_order_line_item_id=LINE_ID,
                    quantity_rejected="1.000",
                    rejection_reason="Wrong specification",
                ),
            ],
        )


def test_create_schema_requires_timezone_aware_received_at() -> None:
    with pytest.raises(ValidationError):
        CreateGoodsReceiptSchema(
            purchase_order_id=PO_ID,
            receiving_location_id=LOCATION_ID,
            received_at=datetime(2026, 7, 27, 12, 0, 0),
        )


def test_line_update_requires_a_field() -> None:
    with pytest.raises(ValidationError):
        GoodsReceiptLineUpdate()


def test_header_update_requires_a_field() -> None:
    with pytest.raises(ValidationError):
        UpdateGoodsReceiptSchema()


def test_cancellation_requires_reason() -> None:
    with pytest.raises(ValidationError):
        CancelGoodsReceiptSchema(reason="   ")
