"""Unit tests for protected organization document settings."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.schemas.organization_document_settings import (
    UpdateOrganizationDocumentSettingsSchema,
)
from app.services.organization_document_settings_service import (
    OrganizationDocumentSettingsService,
)


pytestmark = pytest.mark.unit


@pytest.fixture
def service() -> OrganizationDocumentSettingsService:
    instance = OrganizationDocumentSettingsService(
        MagicMock()
    )
    instance.audit_logs = MagicMock()

    return instance


def _organization() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        business_address="Abuja, Nigeria",
        tax_identification_number="TIN-001",
        vat_number="VAT-001",
        bank_name="Novera Bank",
        bank_account_name="Novera Limited",
        bank_account_number=None,
        bank_routing_number=None,
        payment_instructions=None,
        default_invoice_terms=None,
        default_quote_terms=None,
        invoice_footer=None,
        quote_footer=None,
        updated_at=datetime.now(
            UTC
        ),
    )


def test_clean_optional_text_normalizes_values() -> None:
    assert (
        OrganizationDocumentSettingsService
        ._clean_optional_text(
            None
        )
        is None
    )
    assert (
        OrganizationDocumentSettingsService
        ._clean_optional_text(
            "   "
        )
        is None
    )
    assert (
        OrganizationDocumentSettingsService
        ._clean_optional_text(
            "  Value  "
        )
        == "Value"
    )


def test_get_settings_returns_protected_values(
    service: OrganizationDocumentSettingsService,
) -> None:
    organization = _organization()

    result = service.get_settings(
        organization=organization,
    )

    assert (
        result.organization_id
        == organization.id
    )
    assert (
        result.business_address
        == "Abuja, Nigeria"
    )
    assert (
        result.tax_identification_number
        == "TIN-001"
    )
    assert result.bank_name == "Novera Bank"
    assert result.updated_at == organization.updated_at


def test_update_settings_normalizes_commits_and_audits(
    service: OrganizationDocumentSettingsService,
) -> None:
    organization = _organization()
    actor_user_id = uuid.uuid4()
    actor_membership_id = uuid.uuid4()

    result = service.update_settings(
        organization=organization,
        payload=(
            UpdateOrganizationDocumentSettingsSchema(
                business_address="   ",
                bank_account_number=(
                    "  0123456789  "
                ),
                default_invoice_terms=(
                    "  Due within 14 days.  "
                ),
                invoice_footer="  Thank you.  ",
            )
        ),
        actor_user_id=actor_user_id,
        actor_membership_id=(
            actor_membership_id
        ),
    )

    assert result.business_address is None
    assert (
        result.bank_account_number
        == "0123456789"
    )
    assert (
        result.default_invoice_terms
        == "Due within 14 days."
    )
    assert result.invoice_footer == "Thank you."

    service.db.add.assert_called_once_with(
        organization
    )
    service.db.flush.assert_called_once_with()
    service.db.commit.assert_called_once_with()
    service.db.refresh.assert_called_once_with(
        organization
    )
    service.db.rollback.assert_not_called()

    service.audit_logs.record_event.assert_called_once()

    audit_call = (
        service.audit_logs
        .record_event
        .call_args
    )

    assert (
        audit_call.kwargs["organization_id"]
        == organization.id
    )
    assert audit_call.kwargs["commit"] is False

    event = audit_call.kwargs["payload"]

    assert event.actor_user_id == actor_user_id
    assert (
        event.actor_membership_id
        == actor_membership_id
    )
    assert (
        event.action
        == "organization_document_settings_updated"
    )
    assert (
        event.entity_type
        == "organization_document_settings"
    )
    assert event.entity_id == organization.id
    assert event.status == "success"
    assert event.details == {
        "changed_fields": [
            "bank_account_number",
            "business_address",
            "default_invoice_terms",
            "invoice_footer",
        ],
        "changed_field_count": 4,
    }

    audit_details = str(
        event.details
    )

    assert "0123456789" not in audit_details
    assert "Due within 14 days" not in audit_details
    assert "Thank you" not in audit_details


def test_update_settings_noop_does_not_write_or_audit(
    service: OrganizationDocumentSettingsService,
) -> None:
    organization = _organization()

    result = service.update_settings(
        organization=organization,
        payload=(
            UpdateOrganizationDocumentSettingsSchema(
                bank_name="  Novera Bank  ",
            )
        ),
        actor_user_id=uuid.uuid4(),
        actor_membership_id=uuid.uuid4(),
    )

    assert result.bank_name == "Novera Bank"

    service.db.add.assert_not_called()
    service.db.flush.assert_not_called()
    service.db.commit.assert_not_called()
    service.db.refresh.assert_not_called()
    service.db.rollback.assert_not_called()
    service.audit_logs.record_event.assert_not_called()


def test_update_settings_rolls_back_when_audit_fails(
    service: OrganizationDocumentSettingsService,
) -> None:
    organization = _organization()

    service.audit_logs.record_event.side_effect = (
        RuntimeError(
            "audit failure"
        )
    )

    with pytest.raises(
        RuntimeError,
        match="audit failure",
    ):
        service.update_settings(
            organization=organization,
            payload=(
                UpdateOrganizationDocumentSettingsSchema(
                    quote_footer=(
                        "Updated quote footer"
                    ),
                )
            ),
            actor_user_id=uuid.uuid4(),
            actor_membership_id=uuid.uuid4(),
        )

    service.db.flush.assert_called_once_with()
    service.db.commit.assert_not_called()
    service.db.refresh.assert_not_called()
    service.db.rollback.assert_called_once_with()