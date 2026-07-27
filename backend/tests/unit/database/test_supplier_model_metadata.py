"""Supplier model metadata alignment tests."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from app.models.supplier import Supplier


def test_supplier_table_constraints_are_tenant_scoped() -> None:
    unique_names = {
        constraint.name
        for constraint in Supplier.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert {
        "uq_suppliers_organization_code",
        "uq_suppliers_organization_tax_id",
        "uq_suppliers_organization_registration_number",
    }.issubset(unique_names)

    check_names = {
        constraint.name
        for constraint in Supplier.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert {
        "ck_suppliers_type_valid",
        "ck_suppliers_payment_terms_days_valid",
        "ck_suppliers_currency_length_valid",
    }.issubset(check_names)


def test_supplier_indexes_include_tenant_query_paths() -> None:
    index_names = {
        index.name
        for index in Supplier.__table__.indexes
        if isinstance(index, Index)
    }

    assert {
        "ix_suppliers_organization_name",
        "ix_suppliers_organization_active",
        "ix_suppliers_organization_type",
        "ix_suppliers_organization_category",
        "ix_suppliers_organization_id",
        "ix_suppliers_email",
    }.issubset(index_names)


def test_supplier_server_defaults_match_migration_contract() -> None:
    columns = Supplier.__table__.c

    assert columns.supplier_type.server_default is not None
    assert columns.payment_terms_days.server_default is not None
    assert columns.currency.server_default is not None
    assert columns.details.server_default is not None
    assert columns.is_active.server_default is not None
