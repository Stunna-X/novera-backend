"""Unit tests for organization onboarding and general updates."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

import app.services.organization_service as organization_service_module
from app.models.membership import Membership
from app.models.organization import Organization
from app.schemas.organization import (
    CreateOrganizationSchema,
    UpdateOrganizationSchema,
)
from app.services.organization_service import OrganizationService


pytestmark = pytest.mark.unit


@pytest.fixture
def service() -> OrganizationService:
    instance = OrganizationService(
        MagicMock()
    )
    instance.organizations = MagicMock()
    instance.roles = MagicMock()

    return instance


def test_clean_optional_text_normalizes_blank_values() -> None:
    assert (
        OrganizationService._clean_optional_text(
            None
        )
        is None
    )
    assert (
        OrganizationService._clean_optional_text(
            "   "
        )
        is None
    )
    assert (
        OrganizationService._clean_optional_text(
            "  Value  "
        )
        == "Value"
    )


def test_unique_slug_adds_incrementing_suffix(
    service: OrganizationService,
) -> None:
    service.organizations.slug_exists.side_effect = [
        True,
        True,
        False,
    ]

    slug = service._generate_unique_slug(
        "Acme Field Services"
    )

    assert slug == "acme-field-services-3"
    assert (
        service.organizations.slug_exists.call_count
        == 3
    )


def test_invalid_organization_name_slug_is_rejected(
    service: OrganizationService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        organization_service_module,
        "slugify",
        lambda value: "",
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        service._generate_unique_slug(
            "   "
        )

    assert exc_info.value.status_code == 422


def test_existing_owner_role_is_reused(
    service: OrganizationService,
) -> None:
    owner_role = SimpleNamespace(
        id=uuid.uuid4(),
        name="Owner",
        is_system=True,
    )
    service.roles.get_by_name.return_value = (
        owner_role
    )

    result = service._get_or_create_owner_role()

    assert result is owner_role
    service.db.add.assert_not_called()
    service.db.flush.assert_not_called()


def test_missing_owner_role_is_bootstrapped(
    service: OrganizationService,
) -> None:
    service.roles.get_by_name.return_value = None

    owner_role = (
        service._get_or_create_owner_role()
    )

    assert owner_role.name == "Owner"
    assert owner_role.is_system is True
    service.db.add.assert_called_once_with(
        owner_role
    )
    service.db.flush.assert_called_once_with()


def test_create_organization_commits_owner_membership_atomically(
    service: OrganizationService,
) -> None:
    current_user = SimpleNamespace(
        id=uuid.uuid4()
    )
    owner_role = SimpleNamespace(
        id=uuid.uuid4(),
        name="Owner",
    )

    service.roles.get_by_name.return_value = (
        owner_role
    )
    service.organizations.slug_exists.return_value = (
        False
    )

    def assign_organization_id() -> None:
        for call in service.db.add.call_args_list:
            model = call.args[0]

            if (
                isinstance(
                    model,
                    Organization,
                )
                and model.id is None
            ):
                model.id = uuid.uuid4()

    service.db.flush.side_effect = (
        assign_organization_id
    )

    result = service.create_organization(
        payload=CreateOrganizationSchema(
            name="  Acme Field Services  ",
            email="OPS@EXAMPLE.COM",
            phone="  +2348000000000  ",
            country="  Nigeria  ",
            timezone="  Africa/Lagos  ",
            business_address="  Abuja  ",
            bank_name="  Novera Bank  ",
            invoice_footer="  Thank you  ",
        ),
        current_user=current_user,
    )

    added_models = [
        call.args[0]
        for call in service.db.add.call_args_list
    ]

    membership = next(
        model
        for model in added_models
        if isinstance(
            model,
            Membership,
        )
    )

    assert result.name == "Acme Field Services"
    assert result.slug == "acme-field-services"
    assert result.email == "ops@example.com"
    assert result.phone == "+2348000000000"
    assert result.country == "Nigeria"
    assert result.timezone == "Africa/Lagos"
    assert result.business_address == "Abuja"
    assert result.bank_name == "Novera Bank"
    assert result.invoice_footer == "Thank you"

    assert (
        membership.organization_id
        == result.id
    )
    assert (
        membership.user_id
        == current_user.id
    )
    assert (
        membership.role_id
        == owner_role.id
    )

    service.db.commit.assert_called_once_with()
    service.db.refresh.assert_called_once_with(
        result
    )


def test_create_organization_rolls_back_on_integrity_error(
    service: OrganizationService,
) -> None:
    current_user = SimpleNamespace(
        id=uuid.uuid4()
    )

    service.organizations.slug_exists.return_value = (
        False
    )
    service.roles.get_by_name.return_value = (
        SimpleNamespace(
            id=uuid.uuid4(),
            name="Owner",
        )
    )
    service.db.flush.side_effect = IntegrityError(
        "INSERT",
        {},
        Exception("duplicate"),
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        service.create_organization(
            payload=CreateOrganizationSchema(
                name="Acme Field Services",
            ),
            current_user=current_user,
        )

    assert exc_info.value.status_code == 409
    service.db.rollback.assert_called_once_with()
    service.db.commit.assert_not_called()


def test_update_preserves_slug_and_normalizes_general_fields(
    service: OrganizationService,
) -> None:
    organization = SimpleNamespace(
        name="Old Name",
        slug="stable-slug",
        industry=None,
        email=None,
        phone=None,
        country=None,
        timezone="UTC",
        logo_url="https://example.com/old.png",
    )

    service.organizations.update_organization.side_effect = (
        lambda model: model
    )

    result = service.update_organization(
        organization=organization,
        payload=UpdateOrganizationSchema(
            name="  New Name  ",
            phone="  +2348111111111  ",
            country="  Nigeria  ",
            timezone="  Africa/Lagos  ",
            logo_url="   ",
        ),
    )

    assert result.slug == "stable-slug"
    assert result.name == "New Name"
    assert result.phone == "+2348111111111"
    assert result.country == "Nigeria"
    assert result.timezone == "Africa/Lagos"
    assert result.logo_url is None

    service.organizations.update_organization.assert_called_once_with(
        organization
    )


def test_general_update_schema_rejects_document_settings() -> None:
    with pytest.raises(
        ValidationError
    ) as exc_info:
        UpdateOrganizationSchema(
            bank_account_number="0123456789",
            invoice_footer="Thank you",
        )

    errors = exc_info.value.errors()

    assert {
        error["loc"][0]
        for error in errors
    } == {
        "bank_account_number",
        "invoice_footer",
    }


def test_deactivate_is_idempotent(
    service: OrganizationService,
) -> None:
    organization = SimpleNamespace(
        is_active=False
    )

    result = service.deactivate_organization(
        organization
    )

    assert result is organization
    service.organizations.deactivate.assert_not_called()


def test_deactivate_active_organization_uses_repository(
    service: OrganizationService,
) -> None:
    organization = SimpleNamespace(
        is_active=True
    )
    service.organizations.deactivate.return_value = (
        organization
    )

    result = service.deactivate_organization(
        organization
    )

    assert result is organization
    service.organizations.deactivate.assert_called_once_with(
        organization
    )