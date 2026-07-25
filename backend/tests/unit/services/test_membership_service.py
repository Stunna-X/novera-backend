"""Unit tests for organization membership and Owner invariants."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.enums.user import UserStatus
from app.schemas.membership import (
    AddOrganizationMemberSchema,
    UpdateMembershipRoleSchema,
)
from app.services.membership_service import MembershipService


pytestmark = pytest.mark.unit


def make_role(name: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
    )


def make_membership(
    role_name: str,
    *,
    organization_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    organization_id = organization_id or uuid.uuid4()

    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=organization_id,
        user_id=uuid.uuid4(),
        role_id=uuid.uuid4(),
        role=make_role(role_name),
        user=SimpleNamespace(id=uuid.uuid4()),
    )


def make_user(
    *,
    status: UserStatus = UserStatus.ACTIVE,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="member@example.com",
        status=status,
    )


@pytest.fixture
def service() -> MembershipService:
    instance = MembershipService(MagicMock())
    instance.users = MagicMock()
    instance.roles = MagicMock()
    instance.organizations = MagicMock()
    instance.memberships = MagicMock()
    return instance


def test_non_owner_cannot_manage_owner_memberships(
    service: MembershipService,
) -> None:
    requester_membership = make_membership("Administrator")

    with pytest.raises(HTTPException) as exc_info:
        service._require_owner_for_owner_action(
            requester_membership
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == (
        "Only an Owner can manage Owner memberships."
    )


def test_owner_can_manage_owner_memberships(
    service: MembershipService,
) -> None:
    requester_membership = make_membership(" OWNER ")

    service._require_owner_for_owner_action(
        requester_membership
    )


def test_sole_owner_cannot_be_demoted_or_removed(
    service: MembershipService,
) -> None:
    owner_membership = make_membership("Owner")
    service._count_owners = MagicMock(return_value=1)

    with pytest.raises(HTTPException) as exc_info:
        service._ensure_not_sole_owner(owner_membership)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == (
        "The organization's only Owner cannot "
        "be removed or assigned another role."
    )


def test_owner_change_is_allowed_when_another_owner_exists(
    service: MembershipService,
) -> None:
    owner_membership = make_membership("Owner")
    service._count_owners = MagicMock(return_value=2)

    service._ensure_not_sole_owner(owner_membership)


def test_non_owner_does_not_trigger_owner_count(
    service: MembershipService,
) -> None:
    membership = make_membership("Supervisor")
    service._count_owners = MagicMock()

    service._ensure_not_sole_owner(membership)

    service._count_owners.assert_not_called()


def test_add_member_rejects_unknown_user(
    service: MembershipService,
) -> None:
    organization_id = uuid.uuid4()
    current_user = make_user()
    service._get_requester_membership = MagicMock(
        return_value=make_membership(
            "Owner",
            organization_id=organization_id,
        )
    )
    service.users.get_by_email.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        service.add_member(
            organization_id=organization_id,
            payload=AddOrganizationMemberSchema(
                email="missing@example.com",
                role_name="Technician",
            ),
            current_user=current_user,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.parametrize(
    "target_status",
    [
        UserStatus.INACTIVE,
        UserStatus.LOCKED,
    ],
)
def test_add_member_rejects_unavailable_user(
    service: MembershipService,
    target_status: UserStatus,
) -> None:
    organization_id = uuid.uuid4()
    current_user = make_user()
    target_user = make_user(status=target_status)
    service._get_requester_membership = MagicMock(
        return_value=make_membership(
            "Owner",
            organization_id=organization_id,
        )
    )
    service.users.get_by_email.return_value = target_user

    with pytest.raises(HTTPException) as exc_info:
        service.add_member(
            organization_id=organization_id,
            payload=AddOrganizationMemberSchema(
                email=target_user.email,
                role_name="Technician",
            ),
            current_user=current_user,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == (
        "The selected user account is not active."
    )


def test_add_member_rejects_duplicate_membership(
    service: MembershipService,
) -> None:
    organization_id = uuid.uuid4()
    current_user = make_user()
    target_user = make_user()
    service._get_requester_membership = MagicMock(
        return_value=make_membership(
            "Owner",
            organization_id=organization_id,
        )
    )
    service.users.get_by_email.return_value = target_user
    service.memberships.membership_exists.return_value = True

    with pytest.raises(HTTPException) as exc_info:
        service.add_member(
            organization_id=organization_id,
            payload=AddOrganizationMemberSchema(
                email=target_user.email,
                role_name="Technician",
            ),
            current_user=current_user,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == (
        "This user already belongs to the organization."
    )


def test_non_owner_cannot_assign_owner_role(
    service: MembershipService,
) -> None:
    organization_id = uuid.uuid4()
    current_user = make_user()
    target_user = make_user()
    service._get_requester_membership = MagicMock(
        return_value=make_membership(
            "Administrator",
            organization_id=organization_id,
        )
    )
    service.users.get_by_email.return_value = target_user
    service.memberships.membership_exists.return_value = False
    service._get_role_or_404 = MagicMock(
        return_value=make_role("Owner")
    )

    with pytest.raises(HTTPException) as exc_info:
        service.add_member(
            organization_id=organization_id,
            payload=AddOrganizationMemberSchema(
                email=target_user.email,
                role_name="Owner",
            ),
            current_user=current_user,
        )

    assert exc_info.value.status_code == 403
    service.memberships.create_membership.assert_not_called()


def test_non_owner_cannot_demote_owner(
    service: MembershipService,
) -> None:
    organization_id = uuid.uuid4()
    current_user = make_user()
    target_membership = make_membership(
        "Owner",
        organization_id=organization_id,
    )
    service._get_requester_membership = MagicMock(
        return_value=make_membership(
            "Administrator",
            organization_id=organization_id,
        )
    )
    service._get_target_membership_or_404 = MagicMock(
        return_value=target_membership
    )
    service._get_role_or_404 = MagicMock(
        return_value=make_role("Technician")
    )

    with pytest.raises(HTTPException) as exc_info:
        service.update_member_role(
            organization_id=organization_id,
            membership_id=target_membership.id,
            payload=UpdateMembershipRoleSchema(
                role_name="Technician"
            ),
            current_user=current_user,
        )

    assert exc_info.value.status_code == 403
    service.memberships.update_membership.assert_not_called()


def test_sole_owner_cannot_be_demoted(
    service: MembershipService,
) -> None:
    organization_id = uuid.uuid4()
    current_user = make_user()
    requester = make_membership(
        "Owner",
        organization_id=organization_id,
    )
    target_membership = make_membership(
        "Owner",
        organization_id=organization_id,
    )
    service._get_requester_membership = MagicMock(
        return_value=requester
    )
    service._get_target_membership_or_404 = MagicMock(
        return_value=target_membership
    )
    service._get_role_or_404 = MagicMock(
        return_value=make_role("Technician")
    )
    service._count_owners = MagicMock(return_value=1)

    with pytest.raises(HTTPException) as exc_info:
        service.update_member_role(
            organization_id=organization_id,
            membership_id=target_membership.id,
            payload=UpdateMembershipRoleSchema(
                role_name="Technician"
            ),
            current_user=current_user,
        )

    assert exc_info.value.status_code == 409
    service.memberships.update_membership.assert_not_called()


def test_assigning_same_role_is_idempotent(
    service: MembershipService,
) -> None:
    organization_id = uuid.uuid4()
    current_user = make_user()
    role = make_role("Technician")
    target_membership = make_membership(
        "Technician",
        organization_id=organization_id,
    )
    target_membership.role = role
    target_membership.role_id = role.id
    service._get_requester_membership = MagicMock(
        return_value=make_membership(
            "Owner",
            organization_id=organization_id,
        )
    )
    service._get_target_membership_or_404 = MagicMock(
        return_value=target_membership
    )
    service._get_role_or_404 = MagicMock(return_value=role)

    result = service.update_member_role(
        organization_id=organization_id,
        membership_id=target_membership.id,
        payload=UpdateMembershipRoleSchema(
            role_name="Technician"
        ),
        current_user=current_user,
    )

    assert result is target_membership
    service.memberships.update_membership.assert_not_called()


def test_non_owner_cannot_remove_owner(
    service: MembershipService,
) -> None:
    organization_id = uuid.uuid4()
    current_user = make_user()
    target_membership = make_membership(
        "Owner",
        organization_id=organization_id,
    )
    service._get_requester_membership = MagicMock(
        return_value=make_membership(
            "Administrator",
            organization_id=organization_id,
        )
    )
    service._get_target_membership_or_404 = MagicMock(
        return_value=target_membership
    )

    with pytest.raises(HTTPException) as exc_info:
        service.remove_member(
            organization_id=organization_id,
            membership_id=target_membership.id,
            current_user=current_user,
        )

    assert exc_info.value.status_code == 403
    service.memberships.delete_membership.assert_not_called()


def test_sole_owner_cannot_remove_self(
    service: MembershipService,
) -> None:
    organization_id = uuid.uuid4()
    current_user = make_user()
    owner_membership = make_membership(
        "Owner",
        organization_id=organization_id,
    )
    service._get_requester_membership = MagicMock(
        return_value=owner_membership
    )
    service._get_target_membership_or_404 = MagicMock(
        return_value=owner_membership
    )
    service._count_owners = MagicMock(return_value=1)

    with pytest.raises(HTTPException) as exc_info:
        service.remove_member(
            organization_id=organization_id,
            membership_id=owner_membership.id,
            current_user=current_user,
        )

    assert exc_info.value.status_code == 409
    service.memberships.delete_membership.assert_not_called()
