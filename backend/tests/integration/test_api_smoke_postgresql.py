"""End-to-end PostgreSQL API smoke tests for Novera."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.models.organization import Organization
from app.models.user import User


pytestmark = pytest.mark.integration

PUBLIC_OPERATIONS = {
    ("GET", "/"),
    ("GET", "/api/v1/health"),
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/refresh"),
    ("POST", "/api/v1/auth/logout"),
}

HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
}


@pytest.fixture
def api_client() -> Iterator[TestClient]:
    """Run requests through the real FastAPI middleware and routers."""

    with TestClient(app) as client:
        yield client


def _bearer(access_token: str) -> dict[str, str]:
    """Build one bearer authorization header."""

    return {
        "Authorization": f"Bearer {access_token}",
    }


def _replace_path_parameters(path: str) -> str:
    """Replace every OpenAPI path parameter with a safe UUID."""

    return re.sub(
        r"\{[^}]+\}",
        "00000000-0000-0000-0000-000000000001",
        path,
    )


def _register_user(
    client: TestClient,
    *,
    email: str,
    first_name: str,
    last_name: str,
) -> dict[str, object]:
    """Register one user and return the authentication payload."""

    response = client.post(
        "/api/v1/auth/register",
        json={
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "password": "SmokeTestPassword!42",
        },
    )

    assert response.status_code == 200, response.text

    payload = response.json()

    assert payload["user"]["email"] == email
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["token_type"] == "Bearer"

    return payload


def _cleanup_smoke_records(
    session_factory: sessionmaker[Session],
    *,
    organization_ids: list[uuid.UUID],
    emails: list[str],
) -> None:
    """Remove records created by one API workflow."""

    with session_factory() as db:
        if organization_ids:
            organizations = (
                db.query(Organization)
                .filter(
                    Organization.id.in_(organization_ids)
                )
                .all()
            )

            for organization in organizations:
                db.delete(organization)

            db.flush()

        users = (
            db.query(User)
            .filter(
                User.email.in_(emails)
            )
            .all()
        )

        for user in users:
            db.delete(user)

        db.commit()


def test_public_health_and_cors_contract(
    api_client: TestClient,
) -> None:
    """The process, health endpoint, and configured CORS must work."""

    root_response = api_client.get("/")

    assert root_response.status_code == 200
    assert root_response.json() == {
        "application": "Novera",
        "version": "1.0.0",
        "environment": "testing",
        "status": "running",
    }

    health_response = api_client.get(
        "/api/v1/health"
    )

    assert health_response.status_code == 200
    assert health_response.json() == {
        "status": "healthy",
        "service": "Novera API",
    }

    cors_response = api_client.options(
        "/api/v1/health",
        headers={
            "Origin": (
                "https://frontend.api-smoke.test"
            ),
            "Access-Control-Request-Method": "GET",
        },
    )

    assert cors_response.status_code == 200
    assert (
        cors_response.headers[
            "access-control-allow-origin"
        ]
        == "https://frontend.api-smoke.test"
    )


def test_openapi_security_and_route_inventory(
    api_client: TestClient,
) -> None:
    """Every non-public operation must advertise authentication."""

    schema = api_client.get(
        "/openapi.json"
    ).json()

    assert len(schema["paths"]) == 212

    operations: list[
        tuple[str, str, dict[str, object]]
    ] = []

    operation_ids: list[str] = []

    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            normalized_method = method.lower()

            if normalized_method not in HTTP_METHODS:
                continue

            method_name = normalized_method.upper()

            operations.append(
                (
                    method_name,
                    path,
                    operation,
                )
            )

            operation_id = operation.get(
                "operationId"
            )

            assert isinstance(operation_id, str)
            assert operation_id

            operation_ids.append(operation_id)

            if (
                method_name,
                path,
            ) in PUBLIC_OPERATIONS:
                continue

            assert operation.get("security"), (
                f"{method_name} {path} is missing "
                "an OpenAPI security requirement."
            )

    assert len(operations) == 288
    assert len(operation_ids) == len(
        set(operation_ids)
    )


def test_unauthenticated_route_sweep_has_no_server_errors(
    api_client: TestClient,
) -> None:
    """Exercise all 288 operations without credentials."""

    schema = api_client.get(
        "/openapi.json"
    ).json()

    examined = 0

    for path, path_item in schema["paths"].items():
        request_path = _replace_path_parameters(
            path
        )

        for method, operation in path_item.items():
            del operation

            normalized_method = method.lower()

            if normalized_method not in HTTP_METHODS:
                continue

            method_name = normalized_method.upper()
            examined += 1

            request_kwargs: dict[str, object] = {}

            if method_name in {
                "POST",
                "PUT",
                "PATCH",
            }:
                request_kwargs["json"] = {}

            response = api_client.request(
                method_name,
                request_path,
                **request_kwargs,
            )

            assert response.status_code < 500, (
                f"{method_name} {path} returned "
                f"{response.status_code}: "
                f"{response.text}"
            )

            if (
                method_name,
                path,
            ) not in PUBLIC_OPERATIONS:
                assert not (
                    200 <= response.status_code < 300
                ), (
                    f"{method_name} {path} unexpectedly "
                    "succeeded without authentication."
                )

    assert examined == 288


def test_authentication_rbac_and_tenant_workflow(
    api_client: TestClient,
    integration_session_factory: sessionmaker[Session],
) -> None:
    """Run a real client workflow through auth, tenancy, and RBAC."""

    token = uuid.uuid4().hex

    owner_email = (
        f"owner-{token}@smoke.novera.app"
    )
    viewer_email = (
        f"viewer-{token}@smoke.novera.app"
    )

    created_organization_ids: list[uuid.UUID] = []

    try:
        owner_auth = _register_user(
            api_client,
            email=owner_email,
            first_name="API",
            last_name="Owner",
        )

        duplicate_response = api_client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "API",
                "last_name": "Owner",
                "email": owner_email.upper(),
                "password": "SmokeTestPassword!42",
            },
        )

        assert duplicate_response.status_code == 409

        wrong_login = api_client.post(
            "/api/v1/auth/login",
            json={
                "email": owner_email,
                "password": "WrongPassword!42",
            },
        )

        assert wrong_login.status_code == 401
        assert (
            wrong_login.headers[
                "www-authenticate"
            ]
            == "Bearer"
        )

        login_response = api_client.post(
            "/api/v1/auth/login",
            json={
                "email": owner_email,
                "password": "SmokeTestPassword!42",
            },
        )

        assert login_response.status_code == 200

        login_auth = login_response.json()
        owner_access_token = str(
            owner_auth["access_token"]
        )

        me_response = api_client.get(
            "/api/v1/auth/me",
            headers=_bearer(owner_access_token),
        )

        assert me_response.status_code == 200
        assert me_response.json()["email"] == (
            owner_email
        )

        viewer_auth = _register_user(
            api_client,
            email=viewer_email,
            first_name="API",
            last_name="Viewer",
        )

        viewer_access_token = str(
            viewer_auth["access_token"]
        )

        organization_response = api_client.post(
            "/api/v1/organizations",
            headers=_bearer(owner_access_token),
            json={
                "name": (
                    f"API Smoke Operations "
                    f"{token[:8]}"
                ),
                "country": "Nigeria",
                "timezone": "Africa/Lagos",
            },
        )

        assert (
            organization_response.status_code
            == 201
        ), organization_response.text

        organization = (
            organization_response.json()
        )

        organization_id = uuid.UUID(
            organization["id"]
        )

        created_organization_ids.append(
            organization_id
        )

        organization_path = (
            f"/api/v1/organizations/"
            f"{organization_id}"
        )

        owner_get_response = api_client.get(
            organization_path,
            headers=_bearer(owner_access_token),
        )

        assert owner_get_response.status_code == 200

        outsider_response = api_client.get(
            organization_path,
            headers=_bearer(viewer_access_token),
        )

        assert outsider_response.status_code == 404

        owner_access_response = api_client.get(
            f"{organization_path}/access",
            headers=_bearer(owner_access_token),
        )

        assert (
            owner_access_response.status_code
            == 200
        )

        owner_access = owner_access_response.json()

        assert (
            owner_access["membership"]["role"][
                "name"
            ]
            == "Owner"
        )

        owner_permissions = set(
            owner_access["membership"][
                "permission_names"
            ]
        )

        assert {
            "organizations.update",
            "memberships.create",
            "roles.assign",
        }.issubset(owner_permissions)

        assert owner_access["available_roles"]

        roles_response = api_client.get(
            f"{organization_path}/roles",
            headers=_bearer(owner_access_token),
        )

        assert roles_response.status_code == 200
        assert {
            role["name"]
            for role in roles_response.json()
        }.issuperset(
            {
                "Owner",
                "Admin",
                "Operations Manager",
                "Supervisor",
                "Technician",
                "Viewer",
            }
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

        viewer_access_response = api_client.get(
            f"{organization_path}/access",
            headers=_bearer(viewer_access_token),
        )

        assert (
            viewer_access_response.status_code
            == 200
        )

        viewer_access = viewer_access_response.json()

        assert (
            viewer_access["membership"]["role"][
                "name"
            ]
            == "Viewer"
        )

        assert (
            "organizations.update"
            not in viewer_access["membership"][
                "permission_names"
            ]
        )

        viewer_read_response = api_client.get(
            organization_path,
            headers=_bearer(viewer_access_token),
        )

        assert viewer_read_response.status_code == 200

        viewer_update_response = api_client.patch(
            organization_path,
            headers=_bearer(viewer_access_token),
            json={
                "name": "Forbidden Update",
            },
        )

        assert viewer_update_response.status_code == 403

        owner_update_response = api_client.patch(
            organization_path,
            headers=_bearer(owner_access_token),
            json={
                "name": (
                    f"API Smoke Updated "
                    f"{token[:8]}"
                ),
            },
        )

        assert owner_update_response.status_code == 200
        assert owner_update_response.json()[
            "name"
        ].startswith("API Smoke Updated")

        owner_membership_id = (
            owner_access["membership"][
                "membership_id"
            ]
        )

        sole_owner_removal = api_client.delete(
            (
                f"{organization_path}/members/"
                f"{owner_membership_id}"
            ),
            headers=_bearer(owner_access_token),
        )

        assert sole_owner_removal.status_code == 409

        old_refresh_token = str(
            login_auth["refresh_token"]
        )

        rotate_response = api_client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": old_refresh_token,
            },
        )

        assert rotate_response.status_code == 200

        rotated_refresh_token = (
            rotate_response.json()[
                "refresh_token"
            ]
        )

        assert (
            rotated_refresh_token
            != old_refresh_token
        )

        replay_response = api_client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": old_refresh_token,
            },
        )

        assert replay_response.status_code == 401

        revoked_family_response = api_client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": (
                    rotated_refresh_token
                ),
            },
        )

        assert (
            revoked_family_response.status_code
            == 401
        )

        logout_response = api_client.post(
            "/api/v1/auth/logout",
            json={
                "refresh_token": (
                    rotated_refresh_token
                ),
            },
        )

        assert logout_response.status_code == 200
        assert logout_response.json() == {
            "message": "Logged out successfully.",
        }

        deactivate_response = api_client.patch(
            f"{organization_path}/deactivate",
            headers=_bearer(owner_access_token),
        )

        assert deactivate_response.status_code == 200
        assert (
            deactivate_response.json()[
                "is_active"
            ]
            is False
        )

        inactive_access_response = api_client.get(
            organization_path,
            headers=_bearer(viewer_access_token),
        )

        assert inactive_access_response.status_code == 403

    finally:
        _cleanup_smoke_records(
            integration_session_factory,
            organization_ids=(
                created_organization_ids
            ),
            emails=[
                owner_email,
                viewer_email,
            ],
        )
