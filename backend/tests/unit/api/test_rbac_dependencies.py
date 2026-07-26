"""Unit tests for organization context and permission dependencies."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.deps import (
    OrganizationContext,
    get_organization_context,
    require_all_permissions,
    require_any_permission,
    require_permission,
)


pytestmark = pytest.mark.unit


def make_context(
    *permission_names: str,
    organization_active: bool = True,
) -> OrganizationContext:
    organization = SimpleNamespace(
        id=uuid.uuid4(),
        is_active=organization_active,
    )
    role = SimpleNamespace(
        permissions=[
            SimpleNamespace(name=name)
            for name in permission_names
        ]
    )
    current_user = SimpleNamespace(id=uuid.uuid4())
    membership = SimpleNamespace(
        organization=organization,
        user=current_user,
        role=role,
    )

    return OrganizationContext(
        organization=organization,
        membership=membership,
        current_user=current_user,
    )


def test_permission_names_are_normalized() -> None:
    context = make_context(
        " Customers.Read ",
        "WORK_ORDERS.UPDATE",
    )

    assert context.permission_names == {
        "customers.read",
        "work_orders.update",
    }


def test_require_permission_rejects_blank_configuration() -> None:
    with pytest.raises(
        ValueError,
        match="permission name",
    ):
        require_permission("   ")


def test_require_permission_returns_context_when_granted() -> None:
    context = make_context("customers.read")
    dependency = require_permission(" CUSTOMERS.READ ")

    assert dependency(context=context) is context


def test_require_permission_returns_403_when_missing() -> None:
    context = make_context("customers.read")
    dependency = require_permission("customers.update")

    with pytest.raises(HTTPException) as exc_info:
        dependency(context=context)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == (
        "You do not have permission to perform this action."
    )


def test_require_any_permission_rejects_empty_configuration() -> None:
    with pytest.raises(
        ValueError,
        match="At least one permission",
    ):
        require_any_permission("", "   ")


def test_require_any_permission_accepts_one_granted_permission() -> None:
    context = make_context("customers.read")
    dependency = require_any_permission(
        "customers.update",
        "CUSTOMERS.READ",
    )

    assert dependency(context=context) is context


def test_require_any_permission_returns_403_when_none_are_granted() -> None:
    context = make_context("customers.read")
    dependency = require_any_permission(
        "customers.create",
        "customers.update",
    )

    with pytest.raises(HTTPException) as exc_info:
        dependency(context=context)

    assert exc_info.value.status_code == 403


def test_require_all_permissions_rejects_empty_configuration() -> None:
    with pytest.raises(
        ValueError,
        match="At least one permission",
    ):
        require_all_permissions("", "   ")


def test_require_all_permissions_accepts_complete_grant() -> None:
    context = make_context(
        "memberships.create",
        "roles.assign",
    )
    dependency = require_all_permissions(
        " MEMBERSHIPS.CREATE ",
        "ROLES.ASSIGN",
    )

    assert dependency(context=context) is context


def test_require_all_permissions_returns_403_when_one_is_missing() -> None:
    context = make_context("memberships.create")
    dependency = require_all_permissions(
        "memberships.create",
        "roles.assign",
    )

    with pytest.raises(HTTPException) as exc_info:
        dependency(context=context)

    assert exc_info.value.status_code == 403


def test_organization_context_hides_unrelated_organization() -> None:
    db = MagicMock()
    current_user = SimpleNamespace(id=uuid.uuid4())
    organization_id = uuid.uuid4()

    (
        db.query.return_value
        .options.return_value
        .filter.return_value
        .first.return_value
    ) = None

    with pytest.raises(HTTPException) as exc_info:
        get_organization_context(
            organization_id=organization_id,
            current_user=current_user,
            db=db,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Organization not found."


def test_organization_context_rejects_inactive_organization() -> None:
    db = MagicMock()
    current_user = SimpleNamespace(id=uuid.uuid4())
    membership = SimpleNamespace(
        organization=SimpleNamespace(
            id=uuid.uuid4(),
            is_active=False,
        ),
        user=current_user,
        role=SimpleNamespace(permissions=[]),
    )

    (
        db.query.return_value
        .options.return_value
        .filter.return_value
        .first.return_value
    ) = membership

    with pytest.raises(HTTPException) as exc_info:
        get_organization_context(
            organization_id=membership.organization.id,
            current_user=current_user,
            db=db,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == (
        "This organization is inactive."
    )


def test_organization_context_returns_active_membership() -> None:
    db = MagicMock()
    current_user = SimpleNamespace(id=uuid.uuid4())
    organization = SimpleNamespace(
        id=uuid.uuid4(),
        is_active=True,
    )
    role = SimpleNamespace(
        permissions=[
            SimpleNamespace(name="organizations.read"),
        ]
    )
    membership = SimpleNamespace(
        organization=organization,
        user=current_user,
        role=role,
    )

    (
        db.query.return_value
        .options.return_value
        .filter.return_value
        .first.return_value
    ) = membership

    context = get_organization_context(
        organization_id=organization.id,
        current_user=current_user,
        db=db,
    )

    assert context.organization is organization
    assert context.membership is membership
    assert context.current_user is current_user
    assert context.permission_names == {
        "organizations.read",
    }
