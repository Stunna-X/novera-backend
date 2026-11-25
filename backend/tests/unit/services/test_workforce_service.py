"""Unit tests for workforce profile business logic."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.schemas.workforce import (
    CreateWorkforceProfileSchema,
    UpdateWorkforceProfileSchema,
)
from app.services.workforce_service import WorkforceService


pytestmark = pytest.mark.unit


def make_profile(
    *,
    organization_id: uuid.UUID | None = None,
    full_name: str = "Joseph Employee",
    status: str = "active",
    is_active: bool = True,
) -> SimpleNamespace:
    """Build a standalone employee profile without database access."""

    now = datetime.now(UTC)

    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=organization_id or uuid.uuid4(),
        full_name=full_name,
        job_title="Driller",
        employment_type="full_time",
        phone="08012345678",
        status=status,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def service() -> WorkforceService:
    instance = WorkforceService(MagicMock())
    instance.workforce = MagicMock()
    return instance


def test_build_response_contains_standalone_employee_fields() -> None:
    profile = make_profile()

    response = WorkforceService._build_response(profile)

    assert response.id == profile.id
    assert response.organization_id == profile.organization_id
    assert response.full_name == profile.full_name
    assert response.job_title == profile.job_title
    assert response.employment_type == profile.employment_type
    assert response.phone == profile.phone
    assert response.status == profile.status
    assert response.is_active is True


def test_create_profile_creates_standalone_employee(
    service: WorkforceService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization_id = uuid.uuid4()
    loaded_profile = make_profile(
        organization_id=organization_id,
        full_name="Ada Worker",
    )

    def build_profile(**kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            id=loaded_profile.id,
            **kwargs,
        )

    monkeypatch.setattr(
        "app.services.workforce_service.WorkforceProfile",
        build_profile,
    )
    service.workforce.create_profile.side_effect = lambda profile: profile
    service.workforce.get_by_id_for_organization.return_value = (
        loaded_profile
    )

    response = service.create_profile(
        organization_id=organization_id,
        payload=CreateWorkforceProfileSchema(
            full_name="Ada Worker",
            job_title="Driller",
            employment_type="full_time",
        ),
    )

    created_profile = service.workforce.create_profile.call_args.args[0]

    assert created_profile.organization_id == organization_id
    assert created_profile.full_name == "Ada Worker"
    assert created_profile.job_title == "Driller"
    assert created_profile.employment_type == "full_time"
    assert response.full_name == "Ada Worker"
    service.db.rollback.assert_not_called()


def test_create_profile_rolls_back_integrity_error(
    service: WorkforceService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workforce_service.WorkforceProfile",
        lambda **kwargs: SimpleNamespace(
            id=uuid.uuid4(),
            **kwargs,
        ),
    )
    service.workforce.create_profile.side_effect = IntegrityError(
        "INSERT",
        {},
        Exception("constraint violation"),
    )

    with pytest.raises(HTTPException) as exc_info:
        service.create_profile(
            organization_id=uuid.uuid4(),
            payload=CreateWorkforceProfileSchema(
                full_name="Joseph Employee",
            ),
        )

    assert exc_info.value.status_code == 409
    assert "conflicts" in exc_info.value.detail
    service.db.rollback.assert_called_once()


def test_create_profile_returns_error_if_created_record_cannot_be_loaded(
    service: WorkforceService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_profile = SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(
        "app.services.workforce_service.WorkforceProfile",
        lambda **kwargs: created_profile,
    )
    service.workforce.create_profile.return_value = created_profile
    service.workforce.get_by_id_for_organization.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        service.create_profile(
            organization_id=uuid.uuid4(),
            payload=CreateWorkforceProfileSchema(
                full_name="Joseph Employee",
            ),
        )

    assert exc_info.value.status_code == 500


def test_update_profile_preserves_omitted_fields(
    service: WorkforceService,
) -> None:
    organization_id = uuid.uuid4()
    profile = make_profile(organization_id=organization_id)
    service._get_profile_or_404 = MagicMock(return_value=profile)
    service.workforce.update_profile.side_effect = lambda item: item

    response = service.update_profile(
        organization_id=organization_id,
        profile_id=profile.id,
        payload=UpdateWorkforceProfileSchema(
            job_title="Senior Driller",
        ),
    )

    assert profile.job_title == "Senior Driller"
    assert profile.full_name == "Joseph Employee"
    assert profile.phone == "08012345678"
    assert response.full_name == "Joseph Employee"
    service.workforce.update_profile.assert_called_once_with(profile)


def test_update_profile_changes_only_supplied_status(
    service: WorkforceService,
) -> None:
    profile = make_profile()
    service._get_profile_or_404 = MagicMock(return_value=profile)
    service.workforce.update_profile.side_effect = lambda item: item

    response = service.update_profile(
        organization_id=profile.organization_id,
        profile_id=profile.id,
        payload=UpdateWorkforceProfileSchema(status="inactive"),
    )

    assert profile.status == "inactive"
    assert profile.is_active is True
    assert response.status == "inactive"
    assert response.is_active is True


@pytest.mark.parametrize(
    ("field_name", "expected_detail"),
    [
        ("full_name", "Employee name cannot be null."),
        ("status", "Workforce status cannot be null."),
    ],
)
def test_update_profile_rejects_null_non_nullable_fields(
    service: WorkforceService,
    field_name: str,
    expected_detail: str,
) -> None:
    profile = make_profile()
    service._get_profile_or_404 = MagicMock(return_value=profile)

    payload = UpdateWorkforceProfileSchema.model_validate(
        {field_name: None}
    )

    with pytest.raises(HTTPException) as exc_info:
        service.update_profile(
            organization_id=profile.organization_id,
            profile_id=profile.id,
            payload=payload,
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == expected_detail
    service.workforce.update_profile.assert_not_called()


def test_deactivate_profile_uses_repository(
    service: WorkforceService,
) -> None:
    profile = make_profile()
    service._get_profile_or_404 = MagicMock(return_value=profile)

    result = service.deactivate_profile(
        organization_id=profile.organization_id,
        profile_id=profile.id,
    )

    assert result is None
    service.workforce.deactivate_profile.assert_called_once_with(profile)


def test_reactivate_profile_uses_repository_for_inactive_profile(
    service: WorkforceService,
) -> None:
    profile = make_profile(is_active=False, status="inactive")
    reactivated_profile = make_profile(
        organization_id=profile.organization_id,
        is_active=True,
        status="active",
    )
    service._get_profile_or_404 = MagicMock(return_value=profile)
    service.workforce.reactivate_profile.return_value = reactivated_profile

    response = service.reactivate_profile(
        organization_id=profile.organization_id,
        profile_id=profile.id,
    )

    service.workforce.reactivate_profile.assert_called_once_with(profile)
    assert response.is_active is True
    assert response.status == "active"


def test_reactivate_profile_does_not_repeat_active_transition(
    service: WorkforceService,
) -> None:
    profile = make_profile()
    service._get_profile_or_404 = MagicMock(return_value=profile)

    response = service.reactivate_profile(
        organization_id=profile.organization_id,
        profile_id=profile.id,
    )

    service.workforce.reactivate_profile.assert_not_called()
    assert response.is_active is True
