"""
Unit tests for canonical access-control bootstrap helpers.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import app.security.access_control as access_control
from app.models.permission import Permission
from app.models.role import Role


pytestmark = pytest.mark.unit


def test_ensure_canonical_role_rejects_unknown_role() -> None:
    db = MagicMock()

    with pytest.raises(
        ValueError,
        match="Unknown canonical role: DoesNotExist",
    ):
        access_control.ensure_canonical_role(
            db=db,
            role_name="DoesNotExist",
        )


def test_ensure_canonical_role_synchronizes_owner_permissions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = MagicMock()

    permission_records = {
        name: SimpleNamespace(
            id=f"permission-{index}",
            name=name,
        )
        for index, name in enumerate(
            access_control.PERMISSIONS
        )
    }

    owner_role = SimpleNamespace(
        id="owner-role-id",
        name="Owner",
    )

    get_or_create_permission = MagicMock(
        side_effect=lambda **kwargs: (
            permission_records[kwargs["name"]],
            True,
            True,
        )
    )
    get_or_create_role = MagicMock(
        return_value=(owner_role, True, True)
    )
    synchronize_role_permissions = MagicMock()

    monkeypatch.setattr(
        access_control,
        "get_or_create_permission",
        get_or_create_permission,
    )
    monkeypatch.setattr(
        access_control,
        "get_or_create_role",
        get_or_create_role,
    )
    monkeypatch.setattr(
        access_control,
        "synchronize_role_permissions",
        synchronize_role_permissions,
    )

    result = access_control.ensure_canonical_role(
        db=db,
        role_name=access_control.CANONICAL_OWNER_ROLE_NAME,
    )

    assert result is owner_role

    assert (
        get_or_create_permission.call_count
        == len(access_control.PERMISSIONS)
    )

    get_or_create_role.assert_called_once_with(
        db=db,
        name="Owner",
        description=(
            "Full administrative control over an organization."
        ),
    )

    synchronize_role_permissions.assert_called_once_with(
        db=db,
        role=owner_role,
        permission_names=set(
            access_control.ROLE_DEFINITIONS["Owner"]["permissions"]
        ),
        permission_records=permission_records,
    )


def test_ensure_canonical_role_passes_permission_catalogue_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = MagicMock()

    permission = Permission(
        name="organizations.read",
        description="Read organizations.",
    )
    owner_role = Role(
        name="Owner",
        description=(
            "Full administrative control over an organization."
        ),
        is_system=True,
    )

    monkeypatch.setattr(
        access_control,
        "PERMISSIONS",
        {
            "organizations.read": (
                "Read organizations."
            ),
        },
    )
    monkeypatch.setattr(
        access_control,
        "ROLE_DEFINITIONS",
        {
            "Owner": {
                "description": (
                    "Full administrative control over an organization."
                ),
                "permissions": {
                    "organizations.read",
                },
            },
        },
    )

    get_or_create_permission = MagicMock(
        return_value=(permission, True, True)
    )
    get_or_create_role = MagicMock(
        return_value=(owner_role, True, True)
    )
    synchronize_role_permissions = MagicMock()

    monkeypatch.setattr(
        access_control,
        "get_or_create_permission",
        get_or_create_permission,
    )
    monkeypatch.setattr(
        access_control,
        "get_or_create_role",
        get_or_create_role,
    )
    monkeypatch.setattr(
        access_control,
        "synchronize_role_permissions",
        synchronize_role_permissions,
    )

    result = access_control.ensure_canonical_role(
        db=db,
        role_name="Owner",
    )

    assert result is owner_role

    get_or_create_permission.assert_called_once_with(
        db=db,
        name="organizations.read",
        description="Read organizations.",
    )

    synchronize_role_permissions.assert_called_once_with(
        db=db,
        role=owner_role,
        permission_names={"organizations.read"},
        permission_records={
            "organizations.read": permission,
        },
    )
