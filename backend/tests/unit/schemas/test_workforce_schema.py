"""Workforce schema validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.workforce import (
    CreateWorkforceProfileSchema,
    UpdateWorkforceProfileSchema,
)


def test_create_workforce_schema_trims_full_name() -> None:
    payload = CreateWorkforceProfileSchema(
        full_name="  Ada Worker  ",
    )

    assert payload.full_name == "Ada Worker"
    assert payload.status == "active"


def test_create_workforce_schema_accepts_optional_employee_fields() -> None:
    payload = CreateWorkforceProfileSchema(
        full_name="Ada Worker",
        job_title="Driller",
        employment_type="full_time",
        phone="08012345678",
        status="active",
    )

    assert payload.job_title == "Driller"
    assert payload.employment_type == "full_time"
    assert payload.phone == "08012345678"
    assert payload.status == "active"


@pytest.mark.parametrize(
    "employment_type",
    ["full_time", "part_time", "contractor", "casual", "intern"],
)
def test_create_workforce_schema_accepts_valid_employment_types(
    employment_type: str,
) -> None:
    payload = CreateWorkforceProfileSchema(
        full_name="Ada Worker",
        employment_type=employment_type,
    )

    assert payload.employment_type == employment_type


@pytest.mark.parametrize(
    "status",
    ["active", "inactive", "on_leave", "suspended"],
)
def test_create_workforce_schema_accepts_valid_statuses(
    status: str,
) -> None:
    payload = CreateWorkforceProfileSchema(
        full_name="Ada Worker",
        status=status,
    )

    assert payload.status == status


@pytest.mark.parametrize("full_name", ["", " ", "   "])
def test_create_workforce_schema_rejects_blank_names(
    full_name: str,
) -> None:
    with pytest.raises(ValidationError):
        CreateWorkforceProfileSchema(full_name=full_name)


def test_create_workforce_schema_rejects_invalid_employment_type() -> None:
    with pytest.raises(ValidationError):
        CreateWorkforceProfileSchema(
            full_name="Ada Worker",
            employment_type="permanent",
        )


def test_create_workforce_schema_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        CreateWorkforceProfileSchema(
            full_name="Ada Worker",
            status="available",
        )


def test_update_workforce_schema_preserves_patch_semantics() -> None:
    payload = UpdateWorkforceProfileSchema()

    assert payload.model_dump(exclude_unset=True) == {}


def test_update_workforce_schema_includes_only_supplied_fields() -> None:
    payload = UpdateWorkforceProfileSchema(
        job_title="Senior Driller",
    )

    assert payload.model_dump(exclude_unset=True) == {
        "job_title": "Senior Driller",
    }


def test_update_workforce_schema_trims_updated_name() -> None:
    payload = UpdateWorkforceProfileSchema(
        full_name="  Ada Worker  ",
    )

    assert payload.full_name == "Ada Worker"


def test_update_workforce_schema_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        UpdateWorkforceProfileSchema(full_name="   ")
