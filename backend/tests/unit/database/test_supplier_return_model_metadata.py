"""SQLAlchemy metadata tests for supplier returns and debit notes."""

from app.models.supplier_return import (
    SupplierCreditSettlement,
    SupplierDebitNote,
    SupplierDebitNoteLineItem,
    SupplierReturn,
    SupplierReturnLineItem,
)


def _constraint_names(model) -> set[str]:
    return {
        constraint.name
        for constraint in model.__table__.constraints
        if constraint.name is not None
    }


def test_supplier_return_table_metadata() -> None:
    assert SupplierReturn.__tablename__ == "supplier_returns"
    names = _constraint_names(SupplierReturn)
    assert "uq_supplier_returns_organization_number" in names
    assert "ck_supplier_returns_status_valid" in names
    assert "ck_supplier_returns_lifecycle_state_valid" in names


def test_supplier_return_line_metadata() -> None:
    assert (
        SupplierReturnLineItem.__tablename__
        == "supplier_return_line_items"
    )
    names = _constraint_names(SupplierReturnLineItem)
    assert "uq_supplier_return_lines_receipt_source" in names
    assert "ck_supplier_return_line_items_quantity_source_valid" in names
    assert (
        "ck_supplier_return_line_items_accepted_inventory_item_required"
        in names
    )


def test_supplier_debit_note_metadata() -> None:
    assert SupplierDebitNote.__tablename__ == "supplier_debit_notes"
    names = _constraint_names(SupplierDebitNote)
    assert "uq_supplier_debit_notes_organization_number" in names
    assert "ck_supplier_debit_notes_lifecycle_state_valid" in names


def test_supplier_debit_note_line_metadata() -> None:
    assert (
        SupplierDebitNoteLineItem.__tablename__
        == "supplier_debit_note_line_items"
    )
    names = _constraint_names(SupplierDebitNoteLineItem)
    assert "uq_supplier_debit_note_lines_position" in names
    assert "ck_supplier_debit_note_line_items_quantity_positive" in names


def test_supplier_credit_settlement_metadata() -> None:
    assert (
        SupplierCreditSettlement.__tablename__
        == "supplier_credit_settlements"
    )
    names = _constraint_names(SupplierCreditSettlement)
    assert "uq_supplier_credit_settlements_payment" in names
    assert (
        "ck_supplier_credit_settlements_amount_settled_positive"
        in names
    )


def test_return_relationship_uses_delete_orphan() -> None:
    assert "delete-orphan" in SupplierReturn.line_items.property.cascade


def test_debit_note_relationships_use_delete_orphan() -> None:
    assert "delete-orphan" in SupplierDebitNote.line_items.property.cascade
    assert "delete-orphan" in SupplierDebitNote.settlements.property.cascade
