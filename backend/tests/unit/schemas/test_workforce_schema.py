"""Workforce schema validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.workforce import (
    CreateWorkforceProfileSchema,
    UpdateWorkforceProfileSchema,
)


def test_create_workforce_schema_normalizes_skills() -> None:
    payload = CreateWorkforceProfileSchema(
        full_name="  Ada Worker  ",
        skills=[
            "  Borehole drilling ",
            "Pump installation",
            "borehole drilling",
            "",
        ],
    )

    assert payload.full_name == "Ada Worker"
    assert payload.skills == [
        "Borehole drilling",
        "Pump installation",
    ]


def test_update_workforce_schema_preserves_patch_semantics() -> None:
    empty_payload = UpdateWorkforceProfileSchema()

    assert empty_payload.model_dump(exclude_unset=True) == {}

    payload = UpdateWorkforceProfileSchema(
        skills=[],
    )

    assert payload.model_dump(exclude_unset=True) == {
        "skills": [],
    }


def test_update_workforce_schema_rejects_null_skills() -> None:
    with pytest.raises(ValidationError):
        UpdateWorkforceProfileSchema.model_validate(
            {"skills": None}
        )

def test_create_workforce_schema_rejects_non_string_skills() -> None:
    with pytest.raises(ValidationError):
        CreateWorkforceProfileSchema(
            full_name="Ada Worker",
            skills=["Borehole drilling", 42],
        )


def test_update_workforce_schema_rejects_non_string_skills() -> None:
    with pytest.raises(ValidationError):
        UpdateWorkforceProfileSchema.model_validate(
            {"skills": ["Borehole drilling", 42]}
        )
