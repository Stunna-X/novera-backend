"""PostgreSQL API proof for audited inventory operations."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.database.session import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User


pytestmark = pytest.mark.integration


@pytest.fixture
def api_client(
    integration_session_factory: sessionmaker[Session],
) -> Iterator[TestClient]:
    """Route API requests through the dedicated PostgreSQL test database."""

    def override_get_db() -> Iterator[Session]:
        with integration_session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client

    finally:
        app.dependency_overrides.pop(
            get_db,
            None,
        )


def _bearer(
    access_token: str,
) -> dict[str, str]:
    """Build a bearer authorization header."""

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
    """Register one API user."""

    response = client.post(
        "/api/v1/auth/register",
        json={
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "password": "InventoryAuditPassword!42",
        },
    )

    assert response.status_code == 200, response.text

    payload = response.json()

    assert payload["user"]["email"] == email
    assert payload["access_token"]

    return payload


def _create_organization(
    client: TestClient,
    *,
    access_token: str,
    name: str,
) -> uuid.UUID:
    """Create one organization and return its identifier."""

    response = client.post(
        "/api/v1/organizations",
        headers=_bearer(access_token),
        json={
            "name": name,
            "country": "Nigeria",
            "timezone": "Africa/Lagos",
        },
    )

    assert response.status_code == 201, response.text

    return uuid.UUID(
        response.json()["id"]
    )


def _cleanup_records(
    session_factory: sessionmaker[Session],
    *,
    organization_ids: list[uuid.UUID],
    emails: list[str],
) -> None:
    """Delete all organizations and users created by the test."""

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


def test_inventory_mutations_are_authorized_tenant_scoped_and_audited(
    api_client: TestClient,
    integration_session_factory: sessionmaker[Session],
) -> None:
    """
    Prove API RBAC, tenant isolation, actor attribution, and audit redaction.
    """

    token = uuid.uuid4().hex

    owner_email = (
        f"inventory-owner-{token}@tests.novera.app"
    )
    viewer_email = (
        f"inventory-viewer-{token}@tests.novera.app"
    )
    foreign_owner_email = (
        f"inventory-foreign-{token}@tests.novera.app"
    )

    created_organization_ids: list[uuid.UUID] = []

    try:
        owner_auth = _register_user(
            api_client,
            email=owner_email,
            first_name="Inventory",
            last_name="Owner",
        )
        viewer_auth = _register_user(
            api_client,
            email=viewer_email,
            first_name="Inventory",
            last_name="Viewer",
        )
        foreign_auth = _register_user(
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
            foreign_auth["access_token"]
        )

        organization_id = _create_organization(
            api_client,
            access_token=owner_access_token,
            name=f"Inventory Audit {token[:10]}",
        )
        foreign_organization_id = _create_organization(
            api_client,
            access_token=foreign_access_token,
            name=f"Foreign Inventory {token[:10]}",
        )

        created_organization_ids.extend(
            [
                organization_id,
                foreign_organization_id,
            ]
        )

        organization_path = (
            f"/api/v1/organizations/"
            f"{organization_id}"
        )
        inventory_path = (
            f"{organization_path}/inventory"
        )

        add_viewer_response = api_client.post(
            f"{organization_path}/members",
            headers=_bearer(owner_access_token),
            json={
                "email": viewer_email,
                "role_name": "Viewer",
            },
        )

        assert (
            add_viewer_response.status_code
            == 201
        ), add_viewer_response.text

        location_response = api_client.post(
            f"{inventory_path}/locations",
            headers=_bearer(owner_access_token),
            json={
                "code": "ABU-MAIN",
                "name": "Abuja Main Warehouse",
                "location_type": "warehouse",
            },
        )

        assert (
            location_response.status_code
            == 201
        ), location_response.text

        location_id = uuid.UUID(
            location_response.json()["id"]
        )

        item_response = api_client.post(
            f"{inventory_path}/items",
            headers=_bearer(owner_access_token),
            json={
                "sku": f"PIPE-{token[:8]}",
                "name": "Borehole Casing Pipe",
                "item_type": "material",
                "unit_of_measure": "length",
                "default_unit_cost": "2500.0000",
                "currency": "NGN",
                "reorder_level": "10.000",
            },
        )

        assert (
            item_response.status_code
            == 201
        ), item_response.text

        item_id = uuid.UUID(
            item_response.json()["id"]
        )

        receipt_response = api_client.post(
            f"{inventory_path}/movements/receipts",
            headers=_bearer(owner_access_token),
            json={
                "item_id": str(item_id),
                "location_id": str(location_id),
                "quantity": "25.000",
                "unit_cost": "2600.0000",
                "currency": "NGN",
                "reference_type": "purchase_order",
                "reference_id": "PO-PRIVATE-1001",
                "notes": "Supplier banking reference.",
                "details": {
                    "private_supplier_code": "SECRET",
                },
            },
        )

        assert (
            receipt_response.status_code
            == 201
        ), receipt_response.text

        movement_id = uuid.UUID(
            receipt_response.json()[
                "movement"
            ]["id"]
        )

        viewer_read_response = api_client.get(
            f"{inventory_path}/locations",
            headers=_bearer(viewer_access_token),
        )

        assert viewer_read_response.status_code == 200
        assert viewer_read_response.json()["total"] == 1

        viewer_mutation_response = api_client.post(
            f"{inventory_path}/locations",
            headers=_bearer(viewer_access_token),
            json={
                "code": "FORBIDDEN",
                "name": "Forbidden Store",
            },
        )

        assert viewer_mutation_response.status_code == 403

        foreign_read_response = api_client.get(
            f"{inventory_path}/locations",
            headers=_bearer(foreign_access_token),
        )

        assert foreign_read_response.status_code == 404

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
                    AuditLog.action.in_(
                        [
                            "inventory_location_created",
                            "inventory_item_created",
                            "inventory_stock_received",
                        ]
                    ),
                )
                .order_by(
                    AuditLog.created_at.asc(),
                    AuditLog.id.asc(),
                )
                .all()
            )

            assert len(audit_logs) == 3
            assert {
                audit_log.action
                for audit_log in audit_logs
            } == {
                "inventory_location_created",
                "inventory_item_created",
                "inventory_stock_received",
            }

            assert all(
                audit_log.actor_user_id
                == owner_user.id
                for audit_log in audit_logs
            )
            assert all(
                audit_log.actor_membership_id
                == owner_membership.id
                for audit_log in audit_logs
            )

            audit_by_action = {
                audit_log.action: audit_log
                for audit_log in audit_logs
            }

            location_audit = audit_by_action[
                "inventory_location_created"
            ]
            item_audit = audit_by_action[
                "inventory_item_created"
            ]
            receipt_audit = audit_by_action[
                "inventory_stock_received"
            ]

            assert location_audit.entity_type == (
                "inventory_location"
            )
            assert location_audit.entity_id == location_id

            assert item_audit.entity_type == (
                "inventory_item"
            )
            assert item_audit.entity_id == item_id

            assert receipt_audit.entity_type == (
                "inventory_movement"
            )
            assert receipt_audit.entity_id == movement_id
            assert receipt_audit.details == {
                "item_id": str(item_id),
                "location_id": str(location_id),
                "movement_type": "receipt",
            }

            serialized_audit = json.dumps(
                receipt_audit.details,
                sort_keys=True,
            )

            for forbidden_value in (
                "25.000",
                "2600.0000",
                "PO-PRIVATE-1001",
                "Supplier banking reference.",
                "SECRET",
            ):
                assert (
                    forbidden_value
                    not in serialized_audit
                )

    finally:
        _cleanup_records(
            integration_session_factory,
            organization_ids=created_organization_ids,
            emails=[
                owner_email,
                viewer_email,
                foreign_owner_email,
            ],
        )
