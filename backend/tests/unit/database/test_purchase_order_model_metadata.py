"""Metadata tests for purchase order tables."""

from app.models.purchase_order import (
    PurchaseOrder,
    PurchaseOrderLineItem,
)


def test_purchase_order_table_metadata() -> None:
    table = PurchaseOrder.__table__

    assert table.name == "purchase_orders"
    assert "organization_id" in table.c
    assert "purchase_order_number" in table.c
    assert "source_requisition_id" in table.c
    assert "supplier_id" in table.c
    assert "subtotal" in table.c
    assert "total_amount" in table.c

    constraint_names = {
        constraint.name
        for constraint in table.constraints
        if constraint.name is not None
    }

    assert (
        "uq_purchase_orders_organization_number"
        in constraint_names
    )
    assert (
        "uq_purchase_orders_organization_requisition"
        in constraint_names
    )
    assert "ck_purchase_orders_status_valid" in constraint_names


def test_purchase_order_line_metadata() -> None:
    table = PurchaseOrderLineItem.__table__

    assert table.name == "purchase_order_line_items"
    assert "purchase_order_id" in table.c
    assert "source_requisition_line_id" in table.c
    assert "quantity_ordered" in table.c
    assert "quantity_received" in table.c
    assert "line_total" in table.c

    constraint_names = {
        constraint.name
        for constraint in table.constraints
        if constraint.name is not None
    }

    assert (
        "uq_purchase_order_lines_position"
        in constraint_names
    )
    assert (
        "ck_purchase_order_line_items_quantity_received_within_ordered"
        in constraint_names
    )
    assert (
        "ck_purchase_order_line_items_discount_within_subtotal"
        in constraint_names
    )


def test_line_relationship_uses_delete_orphan_cascade() -> None:
    relationship = PurchaseOrder.line_items.property

    assert "delete-orphan" in relationship.cascade
    assert relationship.passive_deletes is True
