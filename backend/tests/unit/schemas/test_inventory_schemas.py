"""Validation tests for inventory stock-operation schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.inventory import (
    AdjustInventoryStockSchema,
    CreateInventoryReservationSchema,
    ReceiveInventoryStockSchema,
    TransferInventoryStockSchema,
)


pytestmark = pytest.mark.unit


def test_receive_schema_normalizes_currency_and_blank_metadata() -> None:
    payload = ReceiveInventoryStockSchema(
        item_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        quantity=Decimal("3.500"),
        currency=" ngn ",
        reference_type="  purchase_order  ",
        reference_id="   ",
        notes="   ",
    )

    assert payload.currency == "NGN"
    assert payload.reference_type == "purchase_order"
    assert payload.reference_id is None
    assert payload.notes is None


def test_receive_schema_rejects_non_positive_quantity() -> None:
    with pytest.raises(ValidationError):
        ReceiveInventoryStockSchema(
            item_id=uuid.uuid4(),
            location_id=uuid.uuid4(),
            quantity=Decimal("0"),
        )


def test_stock_operation_rejects_naive_occurred_at() -> None:
    with pytest.raises(
        ValidationError,
        match="occurred_at must include a timezone",
    ):
        ReceiveInventoryStockSchema(
            item_id=uuid.uuid4(),
            location_id=uuid.uuid4(),
            quantity=Decimal("1"),
            occurred_at=datetime(2026, 7, 25, 12, 0, 0),
        )


def test_adjustment_schema_rejects_zero_delta() -> None:
    with pytest.raises(
        ValidationError,
        match="quantity_delta cannot be zero",
    ):
        AdjustInventoryStockSchema(
            item_id=uuid.uuid4(),
            location_id=uuid.uuid4(),
            quantity_delta=Decimal("0"),
        )


def test_reservation_schema_rejects_naive_expiry() -> None:
    with pytest.raises(
        ValidationError,
        match="expires_at must include a timezone",
    ):
        CreateInventoryReservationSchema(
            item_id=uuid.uuid4(),
            location_id=uuid.uuid4(),
            work_order_id=uuid.uuid4(),
            quantity=Decimal("2"),
            expires_at=datetime(2026, 7, 30, 12, 0, 0),
        )


def test_transfer_schema_accepts_distinct_locations() -> None:
    source_location_id = uuid.uuid4()
    destination_location_id = uuid.uuid4()

    payload = TransferInventoryStockSchema(
        item_id=uuid.uuid4(),
        source_location_id=source_location_id,
        destination_location_id=destination_location_id,
        quantity=Decimal("4.250"),
    )

    assert payload.source_location_id == source_location_id
    assert payload.destination_location_id == destination_location_id
    assert payload.quantity == Decimal("4.250")
