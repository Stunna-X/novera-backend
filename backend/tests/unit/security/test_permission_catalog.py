"""
Tests for the permission catalogue and system-role definitions.
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.scripts.seed_access_control import (
    PERMISSIONS,
    ROLE_DEFINITIONS,
    validate_definitions,
)


API_ROOT = Path("app/api")


def extract_api_permissions() -> set[str]:
    """
    Extract literal require_permission calls from API modules.
    """

    permissions: set[str] = set()

    for path in API_ROOT.rglob("*.py"):
        tree = ast.parse(
            path.read_text(encoding="utf-8-sig"),
            filename=str(path),
        )

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            if not isinstance(node.func, ast.Name):
                continue

            if node.func.id != "require_permission":
                continue

            if not node.args:
                continue

            argument = node.args[0]

            if (
                isinstance(argument, ast.Constant)
                and isinstance(argument.value, str)
            ):
                permissions.add(
                    argument.value.strip()
                )

    return permissions


def extract_route_permissions(
    relative_path: str,
) -> set[str]:
    """
    Extract permissions from one API router.
    """

    path = Path(relative_path)

    tree = ast.parse(
        path.read_text(encoding="utf-8-sig"),
        filename=str(path),
    )

    permissions: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if not isinstance(node.func, ast.Name):
            continue

        if node.func.id != "require_permission":
            continue

        if not node.args:
            continue

        argument = node.args[0]

        if (
            isinstance(argument, ast.Constant)
            and isinstance(argument.value, str)
        ):
            permissions.add(
                argument.value.strip()
            )

    return permissions


def test_access_control_definitions_are_valid() -> None:
    """
    The static permission and role catalogue is internally valid.
    """

    validate_definitions()


def test_every_api_permission_exists_in_seed_catalogue() -> None:
    """
    Every API permission must be seedable and assignable.
    """

    api_permissions = extract_api_permissions()

    missing_permissions = (
        api_permissions - set(PERMISSIONS)
    )

    assert missing_permissions == set(), (
        "API permissions missing from PERMISSIONS: "
        f"{sorted(missing_permissions)}"
    )


def test_all_role_permissions_exist_in_catalogue() -> None:
    """
    Every system-role permission must exist in the catalogue.
    """

    for role_name, definition in ROLE_DEFINITIONS.items():
        permission_names = definition["permissions"]

        assert isinstance(permission_names, set)

        unknown_permissions = (
            permission_names - set(PERMISSIONS)
        )

        assert unknown_permissions == set(), (
            f"{role_name} references unknown permissions: "
            f"{sorted(unknown_permissions)}"
        )


def test_owner_and_admin_receive_expected_catalogue() -> None:
    """
    Owner receives the full catalogue.

    Admin receives the full operational catalogue but cannot
    perform Owner-only organization-control actions.
    """

    expected_permissions = set(PERMISSIONS)

    owner_permissions = ROLE_DEFINITIONS["Owner"]["permissions"]
    admin_permissions = ROLE_DEFINITIONS["Admin"]["permissions"]

    assert owner_permissions == expected_permissions

    owner_only_permissions = {
        "organizations.deactivate",
        "roles.assign",
        "memberships.delete",
    }

    assert admin_permissions == (
        expected_permissions - owner_only_permissions
    )

def test_document_delivery_routes_use_delivery_permissions() -> None:
    """
    Delivery endpoints use dedicated permissions.
    """

    permissions = extract_route_permissions(
        "app/api/v1/document_deliveries/router.py"
    )

    assert permissions == {
        "document_deliveries.read",
        "document_deliveries.send",
    }


def test_email_outbox_routes_use_outbox_permissions() -> None:
    """
    Outbox endpoints do not depend on report-read access.
    """

    permissions = extract_route_permissions(
        "app/api/v1/email_outbox/router.py"
    )

    assert permissions == {
        "email_outbox.read",
        "email_outbox.manage",
    }