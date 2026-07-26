"""PostgreSQL API coverage for organization document settings."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy.orm import Session, sessionmaker

from app.database.session import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.role import Role
from app.models.user import User


pytestmark = pytest.mark.integration


PASSWORD = "DocumentSettingsTest!42"

SENSITIVE_ORGANIZATION_FIELDS = {
    "business_address",
    "tax_identification_number",
    "vat_number",
    "bank_name",
    "bank_account_name",
    "bank_account_number",
    "bank_routing_number",
    "payment_instructions",
    "default_invoice_terms",
    "default_quote_terms",
    "invoice_footer",
    "quote_footer",
}


@pytest.fixture
def api_client(
    integration_session_factory: sessionmaker[Session],
) -> Iterator[TestClient]:
    """
    Provide a TestClient bound to the migrated PostgreSQL test database.
    """

    def override_get_db() -> Iterator[Session]:
        db = integration_session_factory()

        try:
            yield db
        finally:
            db.close()

    previous_override = app.dependency_overrides.get(
        get_db
    )

    app.dependency_overrides[get_db] = (
        override_get_db
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(
                get_db,
                None,
            )
        else:
            app.dependency_overrides[get_db] = (
                previous_override
            )


def _bearer(
    access_token: str,
) -> dict[str, str]:
    """
    Build one bearer authorization header.
    """

    return {
        "Authorization": f"Bearer {access_token}",
    }


def _register_user(
    client: TestClient,
    *,
    email: str,
    first_name: str,
    last_name: str,
) -> dict[str, object]:
    """
    Register one user and return the authentication payload.
    """

    response = client.post(
        "/api/v1/auth/register",
        json={
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "password": PASSWORD,
        },
    )

    assert response.status_code == 200, response.text

    payload = response.json()

    assert payload["user"]["email"] == email
    assert payload["access_token"]

    return payload


def _cleanup_records(
    session_factory: sessionmaker[Session],
    *,
    organization_ids: list[uuid.UUID],
    emails: list[str],
) -> None:
    """
    Delete organizations and users created by this test.
    """

    with session_factory() as db:
        if organization_ids:
            organizations = (
                db.query(Organization)
                .filter(
                    Organization.id.in_(
                        organization_ids
                    )
                )
                .all()
            )

            for organization in organizations:
                db.delete(
                    organization
                )

            db.flush()

        users = (
            db.query(User)
            .filter(
                User.email.in_(
                    emails
                )
            )
            .all()
        )

        for user in users:
            db.delete(
                user
            )

        db.commit()


def _assert_sensitive_fields_hidden(
    payload: dict[str, object],
) -> None:
    """
    Assert ordinary organization responses expose no protected fields.
    """

    exposed_fields = (
        SENSITIVE_ORGANIZATION_FIELDS
        .intersection(
            payload
        )
    )

    assert exposed_fields == set()


def test_document_settings_are_protected_audited_and_tenant_scoped(
    api_client: TestClient,
    integration_session_factory: sessionmaker[Session],
) -> None:
    """
    Prove document-settings response safety, RBAC, auditing, validation,
    normalization, and tenant isolation against PostgreSQL.
    """

    token = uuid.uuid4().hex

    owner_email = (
        f"document-owner-{token}@tests.novera.app"
    )
    viewer_email = (
        f"document-viewer-{token}@tests.novera.app"
    )
    foreign_owner_email = (
        f"document-foreign-{token}@tests.novera.app"
    )

    created_organization_ids: list[uuid.UUID] = []

    try:
        owner_auth = _register_user(
            api_client,
            email=owner_email,
            first_name="Document",
            last_name="Owner",
        )
        viewer_auth = _register_user(
            api_client,
            email=viewer_email,
            first_name="Document",
            last_name="Viewer",
        )
        foreign_owner_auth = _register_user(
            api_client,
            email=foreign_owner_email,
            first_name="Foreign",
            last_name="Owner",
        )

        owner_access_token = str(
            owner_auth["access_token"]
        )
        viewer_access_token = str(
            viewer_auth["access_token"]
        )
        foreign_access_token = str(
            foreign_owner_auth["access_token"]
        )

        create_response = api_client.post(
            "/api/v1/organizations",
            headers=_bearer(
                owner_access_token
            ),
            json={
                "name": (
                    "Document Settings Operations "
                    f"{token[:8]}"
                ),
                "country": "Nigeria",
                "timezone": "Africa/Lagos",
                "business_address": (
                    "12 Initial Street, Abuja"
                ),
                "tax_identification_number": (
                    "TIN-INITIAL-001"
                ),
                "vat_number": "VAT-INITIAL-001",
                "bank_name": "Initial Bank",
                "bank_account_name": (
                    "Document Settings Limited"
                ),
                "bank_account_number": (
                    "1111111111"
                ),
                "bank_routing_number": (
                    "INITIAL-ROUTING"
                ),
                "payment_instructions": (
                    "Pay using the initial account."
                ),
                "default_invoice_terms": (
                    "Payment due within 30 days."
                ),
                "default_quote_terms": (
                    "Quote valid for 30 days."
                ),
                "invoice_footer": (
                    "Initial invoice footer."
                ),
                "quote_footer": (
                    "Initial quote footer."
                ),
            },
        )

        assert (
            create_response.status_code
            == 201
        ), create_response.text

        created_organization = (
            create_response.json()
        )

        _assert_sensitive_fields_hidden(
            created_organization
        )

        organization_id = uuid.UUID(
            created_organization["id"]
        )

        created_organization_ids.append(
            organization_id
        )

        organization_path = (
            f"/api/v1/organizations/"
            f"{organization_id}"
        )
        settings_path = (
            f"{organization_path}/"
            "document-settings"
        )

        owner_general_response = api_client.get(
            organization_path,
            headers=_bearer(
                owner_access_token
            ),
        )

        assert (
            owner_general_response.status_code
            == 200
        ), owner_general_response.text

        _assert_sensitive_fields_hidden(
            owner_general_response.json()
        )

        foreign_create_response = api_client.post(
            "/api/v1/organizations",
            headers=_bearer(
                foreign_access_token
            ),
            json={
                "name": (
                    "Foreign Document Operations "
                    f"{token[:8]}"
                ),
                "country": "Nigeria",
                "timezone": "Africa/Lagos",
                "bank_account_number": (
                    "9999999999"
                ),
            },
        )

        assert (
            foreign_create_response.status_code
            == 201
        ), foreign_create_response.text

        foreign_organization_id = uuid.UUID(
            foreign_create_response.json()["id"]
        )

        created_organization_ids.append(
            foreign_organization_id
        )

        foreign_settings_path = (
            f"/api/v1/organizations/"
            f"{foreign_organization_id}/"
            "document-settings"
        )

        with integration_session_factory() as db:
            viewer_user = (
                db.query(User)
                .filter(
                    User.email == viewer_email
                )
                .one()
            )

            viewer_role = (
                db.query(Role)
                .filter(
                    func.lower(Role.name)
                    == "viewer"
                )
                .one()
            )

            viewer_membership = Membership(
                organization_id=organization_id,
                user_id=viewer_user.id,
                role_id=viewer_role.id,
            )

            db.add(
                viewer_membership
            )
            db.commit()

        viewer_general_response = api_client.get(
            organization_path,
            headers=_bearer(
                viewer_access_token
            ),
        )

        assert (
            viewer_general_response.status_code
            == 200
        ), viewer_general_response.text

        _assert_sensitive_fields_hidden(
            viewer_general_response.json()
        )

        owner_settings_response = api_client.get(
            settings_path,
            headers=_bearer(
                owner_access_token
            ),
        )

        assert (
            owner_settings_response.status_code
            == 200
        ), owner_settings_response.text

        initial_settings = (
            owner_settings_response.json()
        )

        assert (
            uuid.UUID(
                initial_settings["organization_id"]
            )
            == organization_id
        )
        assert (
            initial_settings["business_address"]
            == "12 Initial Street, Abuja"
        )
        assert (
            initial_settings[
                "tax_identification_number"
            ]
            == "TIN-INITIAL-001"
        )
        assert (
            initial_settings["bank_name"]
            == "Initial Bank"
        )
        assert (
            initial_settings[
                "bank_account_number"
            ]
            == "1111111111"
        )
        assert (
            initial_settings[
                "default_invoice_terms"
            ]
            == "Payment due within 30 days."
        )

        viewer_settings_response = api_client.get(
            settings_path,
            headers=_bearer(
                viewer_access_token
            ),
        )

        assert (
            viewer_settings_response.status_code
            == 403
        )

        viewer_update_response = api_client.patch(
            settings_path,
            headers=_bearer(
                viewer_access_token
            ),
            json={
                "bank_account_number": (
                    "VIEWER-MUST-NOT-UPDATE"
                ),
            },
        )

        assert (
            viewer_update_response.status_code
            == 403
        )

        foreign_user_primary_response = api_client.get(
            settings_path,
            headers=_bearer(
                foreign_access_token
            ),
        )

        assert (
            foreign_user_primary_response.status_code
            == 404
        )

        owner_foreign_response = api_client.get(
            foreign_settings_path,
            headers=_bearer(
                owner_access_token
            ),
        )

        assert (
            owner_foreign_response.status_code
            == 404
        )

        general_sensitive_update_response = (
            api_client.patch(
                organization_path,
                headers=_bearer(
                    owner_access_token
                ),
                json={
                    "bank_account_number": (
                        "MUST-USE-SETTINGS-ENDPOINT"
                    ),
                },
            )
        )

        assert (
            general_sensitive_update_response.status_code
            == 422
        )

        unknown_field_response = api_client.patch(
            settings_path,
            headers=_bearer(
                owner_access_token
            ),
            json={
                "company_logo": (
                    "https://example.com/logo.png"
                ),
            },
        )

        assert (
            unknown_field_response.status_code
            == 422
        )

        oversized_field_response = api_client.patch(
            settings_path,
            headers=_bearer(
                owner_access_token
            ),
            json={
                "invoice_footer": "x" * 2001,
            },
        )

        assert (
            oversized_field_response.status_code
            == 422
        )

        update_response = api_client.patch(
            settings_path,
            headers=_bearer(
                owner_access_token
            ),
            json={
                "business_address": "   ",
                "bank_account_number": (
                    "  0123456789  "
                ),
                "default_invoice_terms": (
                    "  Payment due within 14 days.  "
                ),
                "invoice_footer": (
                    "  Thank you for your business.  "
                ),
            },
        )

        assert (
            update_response.status_code
            == 200
        ), update_response.text

        updated_settings = update_response.json()

        assert (
            updated_settings["business_address"]
            is None
        )
        assert (
            updated_settings[
                "bank_account_number"
            ]
            == "0123456789"
        )
        assert (
            updated_settings[
                "default_invoice_terms"
            ]
            == "Payment due within 14 days."
        )
        assert (
            updated_settings["invoice_footer"]
            == "Thank you for your business."
        )

        refreshed_settings_response = api_client.get(
            settings_path,
            headers=_bearer(
                owner_access_token
            ),
        )

        assert (
            refreshed_settings_response.status_code
            == 200
        )

        refreshed_settings = (
            refreshed_settings_response.json()
        )

        assert (
            refreshed_settings["business_address"]
            is None
        )
        assert (
            refreshed_settings[
                "bank_account_number"
            ]
            == "0123456789"
        )

        with integration_session_factory() as db:
            owner_user = (
                db.query(User)
                .filter(
                    User.email == owner_email
                )
                .one()
            )

            owner_membership = (
                db.query(Membership)
                .filter(
                    Membership.organization_id
                    == organization_id,
                    Membership.user_id
                    == owner_user.id,
                )
                .one()
            )

            audit_logs = (
                db.query(AuditLog)
                .filter(
                    AuditLog.organization_id
                    == organization_id,
                    AuditLog.action
                    == (
                        "organization_document_"
                        "settings_updated"
                    ),
                )
                .all()
            )

            assert len(audit_logs) == 1

            audit_log = audit_logs[0]

            assert (
                audit_log.actor_user_id
                == owner_user.id
            )
            assert (
                audit_log.actor_membership_id
                == owner_membership.id
            )
            assert (
                audit_log.entity_type
                == (
                    "organization_document_"
                    "settings"
                )
            )
            assert (
                audit_log.entity_id
                == organization_id
            )
            assert audit_log.status == "success"
            assert audit_log.details == {
                "changed_fields": [
                    "bank_account_number",
                    "business_address",
                    "default_invoice_terms",
                    "invoice_footer",
                ],
                "changed_field_count": 4,
            }

            audit_details = str(
                audit_log.details
            )

            assert (
                "0123456789"
                not in audit_details
            )
            assert (
                "Payment due within 14 days"
                not in audit_details
            )
            assert (
                "Thank you for your business"
                not in audit_details
            )

    finally:
        _cleanup_records(
            integration_session_factory,
            organization_ids=(
                created_organization_ids
            ),
            emails=[
                owner_email,
                viewer_email,
                foreign_owner_email,
            ],
        )