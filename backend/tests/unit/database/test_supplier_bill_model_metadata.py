"""Metadata tests for supplier bill and match tables."""

from app.models.supplier_bill import (
    SupplierBill,
    SupplierBillLineItem,
    SupplierBillMatchResult,
)


def _constraint_names(model) -> set[str]:
    return {
        constraint.name
        for constraint in model.__table__.constraints
        if constraint.name is not None
    }


def test_supplier_bill_table_metadata() -> None:
    table = SupplierBill.__table__

    assert table.name == "supplier_bills"
    assert "organization_id" in table.c
    assert "supplier_id" in table.c
    assert "purchase_order_id" in table.c
    assert "supplier_invoice_number" in table.c
    assert "match_status" in table.c
    assert "approved_at" in table.c

    names = _constraint_names(SupplierBill)
    assert "uq_supplier_bills_organization_number" in names
    assert "uq_supplier_bills_supplier_invoice" in names
    assert "ck_supplier_bills_status_valid" in names
    assert "ck_supplier_bills_match_status_valid" in names


def test_supplier_bill_line_metadata() -> None:
    table = SupplierBillLineItem.__table__

    assert table.name == "supplier_bill_line_items"
    assert "purchase_order_line_item_id" in table.c
    assert "quantity_billed" in table.c
    assert "unit_price" in table.c
    assert "line_total" in table.c

    names = _constraint_names(SupplierBillLineItem)
    assert "uq_supplier_bill_lines_purchase_order_line" in names
    assert "ck_supplier_bill_line_items_quantity_billed_positive" in names


def test_supplier_bill_match_result_metadata() -> None:
    table = SupplierBillMatchResult.__table__

    assert table.name == "supplier_bill_match_results"
    assert "quantity_received" in table.c
    assert "quantity_variance" in table.c
    assert "unit_price_variance" in table.c
    assert "quantity_within_tolerance" in table.c
    assert "price_within_tolerance" in table.c
    assert "reasons" in table.c

    names = _constraint_names(SupplierBillMatchResult)
    assert "uq_supplier_bill_match_results_line" in names
    assert "ck_supplier_bill_match_results_status_valid" in names


def test_supplier_bill_relationships_are_delete_safe() -> None:
    assert "delete-orphan" in SupplierBill.line_items.property.cascade
    assert SupplierBill.line_items.property.passive_deletes is True
    assert "delete-orphan" in (
        SupplierBillLineItem.match_result.property.cascade
    )
    assert (
        SupplierBillLineItem.match_result.property.passive_deletes
        is True
    )
