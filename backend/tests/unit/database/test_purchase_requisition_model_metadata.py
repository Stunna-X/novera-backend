"""Metadata tests for purchase requisition tables."""

from app.models.purchase_requisition import (
    PurchaseRequisition,
    PurchaseRequisitionLineItem,
)


def test_purchase_requisition_table_metadata() -> None:
    table = PurchaseRequisition.__table__

    assert table.name == "purchase_requisitions"
    assert "organization_id" in table.c
    assert "requisition_number" in table.c
    assert "preferred_supplier_id" in table.c
    assert "delivery_location_id" in table.c
    assert "total_estimated_amount" in table.c

    constraint_names = {
        constraint.name
        for constraint in table.constraints
        if constraint.name is not None
    }

    assert (
        "uq_purchase_requisitions_organization_number"
        in constraint_names
    )
    assert "ck_purchase_requisitions_status_valid" in constraint_names
    assert (
        "ck_purchase_requisitions_priority_valid"
        in constraint_names
    )


def test_purchase_requisition_line_metadata() -> None:
    table = PurchaseRequisitionLineItem.__table__

    assert table.name == "purchase_requisition_line_items"
    assert "requisition_id" in table.c
    assert "inventory_item_id" in table.c
    assert "preferred_supplier_id" in table.c
    assert "estimated_unit_cost" in table.c
    assert "line_total" in table.c

    constraint_names = {
        constraint.name
        for constraint in table.constraints
        if constraint.name is not None
    }

    assert (
        "uq_purchase_requisition_lines_position"
        in constraint_names
    )
    assert (
        "ck_purchase_requisition_line_items_quantity_positive"
        in constraint_names
    )


def test_line_relationship_uses_delete_orphan_cascade() -> None:
    relationship = PurchaseRequisition.line_items.property

    assert "delete-orphan" in relationship.cascade
    assert relationship.passive_deletes is True
