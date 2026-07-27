"""Metadata tests for goods receipt tables."""

from app.models.goods_receipt import (
    GoodsReceipt,
    GoodsReceiptLineItem,
)


def test_goods_receipt_table_metadata() -> None:
    table = GoodsReceipt.__table__

    assert table.name == "goods_receipts"
    assert "organization_id" in table.c
    assert "purchase_order_id" in table.c
    assert "supplier_id" in table.c
    assert "receiving_location_id" in table.c
    assert "status" in table.c
    assert "posted_at" in table.c

    constraint_names = {
        constraint.name
        for constraint in table.constraints
        if constraint.name is not None
    }

    assert (
        "uq_goods_receipts_organization_number"
        in constraint_names
    )
    assert "ck_goods_receipts_status_valid" in constraint_names


def test_goods_receipt_line_metadata() -> None:
    table = GoodsReceiptLineItem.__table__

    assert table.name == "goods_receipt_line_items"
    assert "purchase_order_line_item_id" in table.c
    assert "inventory_movement_id" in table.c
    assert "quantity_accepted" in table.c
    assert "quantity_rejected" in table.c
    assert "quantity_damaged" in table.c

    constraint_names = {
        constraint.name
        for constraint in table.constraints
        if constraint.name is not None
    }

    assert (
        "uq_goods_receipt_lines_purchase_order_line"
        in constraint_names
    )
    assert (
        "ck_goods_receipt_line_items_delivered_quantity_positive"
        in constraint_names
    )
    assert (
        "uq_goods_receipt_lines_inventory_movement"
        in constraint_names
    )


def test_line_relationship_uses_delete_orphan_cascade() -> None:
    relationship = GoodsReceipt.line_items.property

    assert "delete-orphan" in relationship.cascade
    assert relationship.passive_deletes is True
