"""Supplier schema validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.supplier import (
    CreateSupplierSchema,
    UpdateSupplierSchema,
)


def test_create_supplier_schema_normalizes_input() -> None:
    payload = CreateSupplierSchema(
        code=" sup-001 ",
        name="  Acme Drilling Supplies  ",
        supplier_type=" COMPANY ",
        category="  Casing  ",
        contact_name="  Ada Vendor  ",
        email="  SALES@EXAMPLE.COM  ",
        tax_id=" tin-123 ",
        registration_number=" rc-456 ",
        currency=" ngn ",
        country="  Nigeria  ",
        notes="   ",
    )

    assert payload.code == "SUP-001"
    assert payload.name == "Acme Drilling Supplies"
    assert payload.supplier_type == "company"
    assert payload.category == "Casing"
    assert payload.contact_name == "Ada Vendor"
    assert str(payload.email) == "sales@example.com"
    assert payload.tax_id == "TIN-123"
    assert payload.registration_number == "RC-456"
    assert payload.currency == "NGN"
    assert payload.country == "Nigeria"
    assert payload.notes is None
    assert payload.details == {}


def test_create_supplier_schema_rejects_invalid_values() -> None:
    with pytest.raises(ValidationError):
        CreateSupplierSchema(
            code=" ",
            name="Supplier",
        )

    with pytest.raises(ValidationError):
        CreateSupplierSchema(
            code="SUP-001",
            name="Supplier",
            currency="NAIRA",
        )

    with pytest.raises(ValidationError):
        CreateSupplierSchema(
            code="SUP-001",
            name="Supplier",
            payment_terms_days=-1,
        )


def test_update_supplier_schema_preserves_patch_semantics() -> None:
    empty_payload = UpdateSupplierSchema()

    assert empty_payload.model_dump(exclude_unset=True) == {}

    payload = UpdateSupplierSchema(
        code=" revised-01 ",
        email=" Accounts@Example.com ",
        details={"preferred": True},
    )

    assert payload.model_dump(exclude_unset=True) == {
        "code": "REVISED-01",
        "email": "accounts@example.com",
        "details": {"preferred": True},
    }


def test_update_supplier_schema_rejects_null_required_fields() -> None:
    for field_name in (
        "code",
        "name",
        "supplier_type",
        "payment_terms_days",
        "currency",
        "details",
    ):
        with pytest.raises(ValidationError):
            UpdateSupplierSchema.model_validate(
                {field_name: None}
            )
