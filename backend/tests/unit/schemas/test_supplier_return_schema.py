"""Schema tests for supplier returns and debit notes."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.supplier_return import (
    AcknowledgeSupplierDebitNoteSchema,
    CancelSupplierReturnSchema,
    CreateSupplierDebitNoteSchema,
    CreateSupplierReturnSchema,
    SettleSupplierDebitNoteSchema,
    SupplierCreditAllocationCreate,
    SupplierDebitNoteLineCreate,
    SupplierReturnLineCreate,
    SupplierReturnLineUpdate,
    UpdateSupplierDebitNoteSchema,
    UpdateSupplierReturnSchema,
)


LINE_ID = uuid.uuid4()
BILL_ID = uuid.uuid4()


def test_return_line_requires_positive_quantity() -> None:
    with pytest.raises(ValidationError):
        SupplierReturnLineCreate(
            goods_receipt_line_item_id=LINE_ID,
            quantity_source="accepted",
            quantity_returned="0",
            reason="Defective",
        )


def test_return_line_requires_reason() -> None:
    with pytest.raises(ValidationError):
        SupplierReturnLineCreate(
            goods_receipt_line_item_id=LINE_ID,
            quantity_source="damaged",
            quantity_returned="1.000",
            reason="   ",
        )


def test_return_create_rejects_duplicate_source_lines() -> None:
    with pytest.raises(ValidationError):
        CreateSupplierReturnSchema(
            goods_receipt_id=uuid.uuid4(),
            source_location_id=uuid.uuid4(),
            return_date=date(2026, 7, 27),
            reason_code="damaged",
            line_items=[
                SupplierReturnLineCreate(
                    goods_receipt_line_item_id=LINE_ID,
                    quantity_source="damaged",
                    quantity_returned="1.000",
                    reason="Cracked",
                ),
                SupplierReturnLineCreate(
                    goods_receipt_line_item_id=LINE_ID,
                    quantity_source="damaged",
                    quantity_returned="1.000",
                    reason="Cracked",
                ),
            ],
        )


def test_return_line_update_requires_field() -> None:
    with pytest.raises(ValidationError):
        SupplierReturnLineUpdate()


def test_return_update_requires_field() -> None:
    with pytest.raises(ValidationError):
        UpdateSupplierReturnSchema()


def test_return_cancellation_requires_reason() -> None:
    with pytest.raises(ValidationError):
        CancelSupplierReturnSchema(reason=" ")


def test_debit_line_inputs_validate() -> None:
    line = SupplierDebitNoteLineCreate(
        description="Returned casing",
        quantity="2.000",
        unit_of_measure="each",
        unit_price="125.5000",
        tax_rate="7.5000",
    )
    assert line.quantity == Decimal("2.000")
    assert line.tax_rate == Decimal("7.5000")


def test_debit_line_rejects_tax_above_one_hundred() -> None:
    with pytest.raises(ValidationError):
        SupplierDebitNoteLineCreate(
            description="Returned casing",
            quantity="2.000",
            unit_of_measure="each",
            unit_price="125.5000",
            tax_rate="100.0001",
        )


def test_debit_note_normalizes_currency() -> None:
    payload = CreateSupplierDebitNoteSchema(
        supplier_id=uuid.uuid4(),
        note_date=date(2026, 7, 27),
        currency="ngn",
        reason="Quality failure",
    )
    assert payload.currency == "NGN"


def test_debit_note_update_requires_field() -> None:
    with pytest.raises(ValidationError):
        UpdateSupplierDebitNoteSchema()


def test_acknowledgement_normalizes_reference() -> None:
    payload = AcknowledgeSupplierDebitNoteSchema(
        supplier_credit_reference=" cr-991 "
    )
    assert payload.supplier_credit_reference == "CR-991"


def test_settlement_rejects_duplicate_bills() -> None:
    with pytest.raises(ValidationError):
        SettleSupplierDebitNoteSchema(
            settlement_date=date(2026, 7, 27),
            allocations=[
                SupplierCreditAllocationCreate(
                    supplier_bill_id=BILL_ID,
                    amount_allocated="10.00",
                ),
                SupplierCreditAllocationCreate(
                    supplier_bill_id=BILL_ID,
                    amount_allocated="5.00",
                ),
            ],
        )


def test_settlement_requires_positive_allocation() -> None:
    with pytest.raises(ValidationError):
        SupplierCreditAllocationCreate(
            supplier_bill_id=BILL_ID,
            amount_allocated="0.00",
        )
