"""Unit tests for supplier bill validation."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.supplier_bill import (
    ApproveSupplierBillSchema,
    CreateSupplierBillSchema,
    MatchSupplierBillSchema,
    SupplierBillLineCreate,
    SupplierBillLineUpdate,
    UpdateSupplierBillSchema,
    VoidSupplierBillSchema,
)


SUPPLIER_ID = "00000000-0000-0000-0000-000000000001"
PO_ID = "00000000-0000-0000-0000-000000000002"
LINE_ID = "00000000-0000-0000-0000-000000000003"
SECOND_LINE_ID = "00000000-0000-0000-0000-000000000004"


def test_create_schema_normalizes_identifiers_and_currency() -> None:
    payload = CreateSupplierBillSchema(
        supplier_bill_number=" sb-001 ",
        supplier_invoice_number=" inv-77 ",
        supplier_id=SUPPLIER_ID,
        purchase_order_id=PO_ID,
        invoice_date=date(2026, 7, 27),
        currency=" ngn ",
        line_items=[
            SupplierBillLineCreate(
                purchase_order_line_item_id=LINE_ID,
                quantity_billed="2.500",
            )
        ],
    )

    assert payload.supplier_bill_number == "SB-001"
    assert payload.supplier_invoice_number == "inv-77"
    assert payload.currency == "NGN"
    assert payload.line_items[0].quantity_billed == Decimal("2.500")


def test_create_schema_rejects_blank_supplier_invoice_number() -> None:
    with pytest.raises(ValidationError):
        CreateSupplierBillSchema(
            supplier_invoice_number="   ",
            supplier_id=SUPPLIER_ID,
            purchase_order_id=PO_ID,
            invoice_date=date(2026, 7, 27),
        )


def test_create_schema_rejects_invalid_currency() -> None:
    with pytest.raises(ValidationError):
        CreateSupplierBillSchema(
            supplier_invoice_number="INV-1",
            supplier_id=SUPPLIER_ID,
            purchase_order_id=PO_ID,
            invoice_date=date(2026, 7, 27),
            currency="N1",
        )


def test_due_date_cannot_precede_invoice_date() -> None:
    with pytest.raises(ValidationError):
        CreateSupplierBillSchema(
            supplier_invoice_number="INV-1",
            supplier_id=SUPPLIER_ID,
            purchase_order_id=PO_ID,
            invoice_date=date(2026, 7, 27),
            due_date=date(2026, 7, 26),
        )


def test_create_schema_rejects_duplicate_purchase_order_lines() -> None:
    with pytest.raises(ValidationError):
        CreateSupplierBillSchema(
            supplier_invoice_number="INV-1",
            supplier_id=SUPPLIER_ID,
            purchase_order_id=PO_ID,
            invoice_date=date(2026, 7, 27),
            line_items=[
                SupplierBillLineCreate(
                    purchase_order_line_item_id=LINE_ID,
                    quantity_billed="1.000",
                ),
                SupplierBillLineCreate(
                    purchase_order_line_item_id=LINE_ID,
                    quantity_billed="2.000",
                ),
            ],
        )


def test_distinct_purchase_order_lines_are_allowed() -> None:
    payload = CreateSupplierBillSchema(
        supplier_invoice_number="INV-1",
        supplier_id=SUPPLIER_ID,
        purchase_order_id=PO_ID,
        invoice_date=date(2026, 7, 27),
        line_items=[
            SupplierBillLineCreate(
                purchase_order_line_item_id=LINE_ID,
                quantity_billed="1.000",
            ),
            SupplierBillLineCreate(
                purchase_order_line_item_id=SECOND_LINE_ID,
                quantity_billed="2.000",
            ),
        ],
    )

    assert len(payload.line_items) == 2


def test_line_quantity_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        SupplierBillLineCreate(
            purchase_order_line_item_id=LINE_ID,
            quantity_billed="0",
        )


def test_line_tax_rate_must_not_exceed_one_hundred() -> None:
    with pytest.raises(ValidationError):
        SupplierBillLineCreate(
            purchase_order_line_item_id=LINE_ID,
            quantity_billed="1.000",
            tax_rate="100.0001",
        )


def test_line_update_requires_a_field() -> None:
    with pytest.raises(ValidationError):
        SupplierBillLineUpdate()


def test_header_update_requires_a_field() -> None:
    with pytest.raises(ValidationError):
        UpdateSupplierBillSchema()


def test_match_tolerances_are_bounded() -> None:
    with pytest.raises(ValidationError):
        MatchSupplierBillSchema(price_tolerance_percent="100.0001")


def test_exception_approval_reason_is_normalized() -> None:
    payload = ApproveSupplierBillSchema(
        override_reason="  Approved by finance director.  "
    )

    assert payload.override_reason == "Approved by finance director."


def test_blank_override_reason_becomes_none() -> None:
    payload = ApproveSupplierBillSchema(override_reason="   ")

    assert payload.override_reason is None


def test_void_reason_is_required() -> None:
    with pytest.raises(ValidationError):
        VoidSupplierBillSchema(reason="   ")
