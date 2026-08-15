"""Metadata tests for supplier-payment tables."""

from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from app.models.supplier_payment import (
    SupplierPayment,
    SupplierPaymentAllocation,
)


def _constraint_names(table, constraint_type) -> set[str]:
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, constraint_type)
        and constraint.name is not None
    }


def _index_names(table) -> set[str]:
    return {
        index.name
        for index in table.indexes
        if isinstance(index, Index)
        and index.name is not None
    }


def test_supplier_payment_table_name() -> None:
    assert SupplierPayment.__table__.name == "supplier_payments"


def test_supplier_payment_allocation_table_name() -> None:
    assert (
        SupplierPaymentAllocation.__table__.name
        == "supplier_payment_allocations"
    )


def test_supplier_payment_constraints_are_registered() -> None:
    table = SupplierPayment.__table__
    checks = _constraint_names(table, CheckConstraint)
    uniques = _constraint_names(table, UniqueConstraint)

    assert "ck_supplier_payments_status_valid" in checks
    assert "ck_supplier_payments_method_valid" in checks
    assert "ck_supplier_payments_total_amount_positive" in checks
    assert "ck_supplier_payments_reversal_state_valid" in checks
    assert "uq_supplier_payments_organization_number" in uniques
    assert "uq_supplier_payments_supplier_reference" in uniques


def test_supplier_payment_allocation_constraints_are_registered() -> None:
    table = SupplierPaymentAllocation.__table__
    checks = _constraint_names(table, CheckConstraint)
    uniques = _constraint_names(table, UniqueConstraint)

    assert (
        "ck_supplier_payment_allocations_amount_positive"
        in checks
    )
    assert (
        "uq_supplier_payment_allocations_bill"
        in uniques
    )
    assert (
        "uq_supplier_payment_allocations_position"
        in uniques
    )


def test_supplier_payment_indexes_are_registered() -> None:
    indexes = _index_names(SupplierPayment.__table__)

    assert "ix_supplier_payments_organization_supplier" in indexes
    assert "ix_supplier_payments_organization_date" in indexes
    assert "ix_supplier_payments_organization_status" in indexes


def test_supplier_payment_relationships_are_registered() -> None:
    relationships = SupplierPayment.__mapper__.relationships
    allocation_relationships = (
        SupplierPaymentAllocation.__mapper__.relationships
    )

    assert "allocations" in relationships
    assert relationships["allocations"].cascade.delete_orphan is True
    assert "supplier_payment" in allocation_relationships
    assert "supplier_bill" in allocation_relationships
