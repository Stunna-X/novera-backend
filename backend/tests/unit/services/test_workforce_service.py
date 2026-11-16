"""Unit tests for workforce profile business logic."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.enums.user import UserStatus
from app.schemas.workforce import (
    CreateWorkforceProfileSchema,
    UpdateWorkforceProfileSchema,
)
from app.services.workforce_service import WorkforceService


pytestmark = pytest.mark.unit


def make_profile(
    *,
    organization_id: uuid.UUID | None = None,
    membership_id: uuid.UUID | None = None,
    status: str = "active",
    is_available: bool = True,
    is_active: bool = True,
) -> SimpleNamespace:
    """Build a profile-shaped object without database access."""

    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=organization_id or uuid.uuid4(),
        full_name="Joseph Employee",
        membership_id=membership_id,
        membership=None,
        job_title="Driller",
        employment_type="full_time",
        phone=None,
        emergency_contact_name=None,
        emergency_contact_phone=None,
        skills=["drilling"],
        status=status,
        is_available=is_available,
        is_active=is_active,
        notes=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def service() -> WorkforceService:
    instance = WorkforceService(MagicMock())
    instance.workforce = MagicMock()
    return instance


def test_build_response_supports_standalone_employee() -> None:
    profile = make_profile()

    response = WorkforceService._build_response(profile)

    assert response.full_name == profile.full_name
    assert response.membership_id is None
    assert response.user_id is None
    assert response.email is None
    assert response.skills == ["drilling"]


def test_create_profile_allows_standalone_employee(
    service: WorkforceService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization_id = uuid.uuid4()
    loaded_profile = make_profile(
        organization_id=organization_id,
    )

    def build_profile(**kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            id=uuid.uuid4(),
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
            full_name="Joseph Employee",
        ),
    )

    created_profile = (
        service.workforce.create_profile.call_args.args[0]
    )

    assert created_profile.organization_id == organization_id
    assert created_profile.membership_id is None
    assert response.membership_id is None
    assert response.user_id is None
    assert response.email is None
    service.db.rollback.assert_not_called()


def test_create_profile_links_valid_membership(
    service: WorkforceService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization_id = uuid.uuid4()
    membership_id = uuid.uuid4()
    membership = SimpleNamespace(
        id=membership_id,
        user_id=uuid.uuid4(),
        user=SimpleNamespace(
            status=UserStatus.ACTIVE,
            email="employee@example.com",
        ),
    )
    loaded_profile = make_profile(
        organization_id=organization_id,
        membership_id=membership_id,
    )
    loaded_profile.membership = membership

    service.db.query.return_value.options.return_value.filter.return_value.first.return_value = (
        membership
    )
    service.workforce.get_by_membership.return_value = None

    def build_profile(**kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            id=uuid.uuid4(),
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
            full_name="Joseph Employee",
            membership_id=membership_id,
        ),
    )

    created_profile = (
        service.workforce.create_profile.call_args.args[0]
    )

    assert created_profile.membership_id == membership_id
    assert response.membership_id == membership_id
    assert response.user_id == membership.user_id
    assert response.email == "employee@example.com"


def test_create_profile_rejects_inactive_membership(
    service: WorkforceService,
) -> None:
    organization_id = uuid.uuid4()
    membership_id = uuid.uuid4()
    membership = SimpleNamespace(
        id=membership_id,
        user=SimpleNamespace(status=UserStatus.INACTIVE),
    )
    service.db.query.return_value.options.return_value.filter.return_value.first.return_value = (
        membership
    )

    with pytest.raises(HTTPException) as exc_info:
        service.create_profile(
            organization_id=organization_id,
            payload=CreateWorkforceProfileSchema(
                full_name="Joseph Employee",
                membership_id=membership_id,
            ),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == (
        "The selected user account is not active."
    )
    service.workforce.create_profile.assert_not_called()


def test_create_profile_rejects_duplicate_membership(
    service: WorkforceService,
) -> None:
    organization_id = uuid.uuid4()
    membership_id = uuid.uuid4()
    membership = SimpleNamespace(
        id=membership_id,
        user=SimpleNamespace(status=UserStatus.ACTIVE),
    )

    service.db.query.return_value.options.return_value.filter.return_value.first.return_value = (
        membership
    )
    service.workforce.get_by_membership.return_value = make_profile(
        organization_id=organization_id,
        membership_id=membership_id,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.create_profile(
            organization_id=organization_id,
            payload=CreateWorkforceProfileSchema(
                full_name="Joseph Employee",
                membership_id=membership_id,
            ),
        )

    assert exc_info.value.status_code == 409
    service.workforce.create_profile.assert_not_called()


def test_create_profile_rolls_back_integrity_error(
    service: WorkforceService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization_id = uuid.uuid4()

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
            organization_id=organization_id,
            payload=CreateWorkforceProfileSchema(
                full_name="Joseph Employee",
            ),
        )

    assert exc_info.value.status_code == 409
    service.db.rollback.assert_called_once()


def test_update_profile_preserves_omitted_fields(
    service: WorkforceService,
) -> None:
    organization_id = uuid.uuid4()
    profile = make_profile(
        organization_id=organization_id,
        is_available=False,
    )
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
    assert profile.is_available is False
    assert response.full_name == "Joseph Employee"
    service.workforce.update_profile.assert_called_once_with(profile)


def test_update_profile_forces_unavailable_for_inactive_status(
    service: WorkforceService,
) -> None:
    profile = make_profile(is_available=True)
    service._get_profile_or_404 = MagicMock(return_value=profile)
    service.workforce.update_profile.side_effect = lambda item: item

    service.update_profile(
        organization_id=profile.organization_id,
        profile_id=profile.id,
        payload=UpdateWorkforceProfileSchema(
            status="inactive",
        ),
    )

    assert profile.status == "inactive"
    assert profile.is_available is False


@pytest.mark.parametrize(
    ("field_name", "expected_detail"),
    [
        ("full_name", "Employee name cannot be null."),
        ("status", "Workforce status cannot be null."),
        ("is_available", "Availability cannot be null."),
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
    profile = make_profile(
        is_active=False,
        is_available=False,
        status="inactive",
    )
    reactivated_profile = make_profile(
        organization_id=profile.organization_id,
        is_active=True,
        is_available=True,
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
    assert response.is_available is True
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
