"""Unit tests for work-order workforce assignments."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, sentinel

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.services.work_order_service import WorkOrderService


pytestmark = pytest.mark.unit


def make_service() -> tuple[WorkOrderService, SimpleNamespace, SimpleNamespace]:
    """Build a work-order service with mocked persistence."""

    db = MagicMock()
    service = WorkOrderService(db)

    work_order = SimpleNamespace(id=uuid.uuid4())
    workforce_profile = SimpleNamespace(
        id=uuid.uuid4(),
    )

    service._get_work_order_or_404 = MagicMock(
        return_value=work_order,
    )
    service._build_response = MagicMock(
        return_value=sentinel.work_order_response,
    )

    db.query.return_value.filter.return_value.first.return_value = (
        workforce_profile
    )

    service.work_orders.get_workforce_assignment = MagicMock(
        return_value=None,
    )
    service.work_orders.add_workforce_assignment = MagicMock()
    service.work_orders.remove_workforce_assignment = MagicMock()

    service.activities.create_activity = MagicMock(
        side_effect=lambda activity: activity,
    )

    return service, work_order, workforce_profile


def assign_workforce(
    service: WorkOrderService,
    work_order: SimpleNamespace,
    workforce_profile: SimpleNamespace,
    *,
    responsibility: str | None = None,
    custom_responsibility: str | None = None,
) -> object:
    """Call the assignment service with consistent identifiers."""

    return service.assign_workforce(
        organization_id=uuid.uuid4(),
        work_order_id=work_order.id,
        workforce_profile_id=workforce_profile.id,
        actor_user_id=uuid.uuid4(),
        responsibility=responsibility,
        custom_responsibility=custom_responsibility,
    )


def test_assign_workforce_saves_responsibility_and_activity() -> None:
    service, work_order, workforce_profile = make_service()

    result = assign_workforce(
        service,
        work_order,
        workforce_profile,
        responsibility="driller",
    )

    assert result is sentinel.work_order_response

    assignment = (
        service.work_orders.add_workforce_assignment.call_args.args[0]
    )
    assert assignment.work_order_id == work_order.id
    assert assignment.workforce_profile_id == workforce_profile.id
    assert assignment.responsibility == "driller"
    assert assignment.custom_responsibility is None

    activity = service.activities.create_activity.call_args.args[0]
    assert activity.activity_type == "workforce_assigned"
    assert activity.details == {
        "workforce_profile_id": str(workforce_profile.id),
        "responsibility": "driller",
        "custom_responsibility": None,
    }


def test_workforce_member_without_availability_field_can_be_assigned() -> None:
    service, work_order, workforce_profile = make_service()

    assign_workforce(
        service,
        work_order,
        workforce_profile,
        custom_responsibility="Site supervisor",
    )

    service.work_orders.add_workforce_assignment.assert_called_once()

    assert (
        service.work_orders.add_workforce_assignment.call_args.args[0]
        .custom_responsibility
        == "Site supervisor"
    )


def test_existing_assignment_is_idempotent() -> None:
    service, work_order, workforce_profile = make_service()
    existing_assignment = SimpleNamespace(
        responsibility="driller",
        custom_responsibility=None,
    )
    service.work_orders.get_workforce_assignment.return_value = (
        existing_assignment
    )

    assign_workforce(
        service,
        work_order,
        workforce_profile,
        responsibility="supervisor",
    )

    service.work_orders.add_workforce_assignment.assert_not_called()
    service.activities.create_activity.assert_not_called()

    service.work_orders.get_workforce_assignment.assert_called_once_with(
        work_order_id=work_order.id,
        workforce_profile_id=workforce_profile.id,
    )


def test_duplicate_assignment_integrity_error_returns_conflict() -> None:
    service, work_order, workforce_profile = make_service()

    original_error = SimpleNamespace(
        diag=SimpleNamespace(
            constraint_name="uq_work_order_workforce_assignment",
        ),
    )
    integrity_error = IntegrityError(
        "INSERT",
        {},
        original_error,
    )
    service.work_orders.add_workforce_assignment.side_effect = (
        integrity_error
    )

    with pytest.raises(HTTPException) as exc_info:
        assign_workforce(service, work_order, workforce_profile)

    assert exc_info.value.status_code == 409
    assert "already assigned" in exc_info.value.detail
    service.db.rollback.assert_called_once()
    service.activities.create_activity.assert_not_called()


def test_unrelated_integrity_error_is_reraised() -> None:
    service, work_order, workforce_profile = make_service()

    original_error = SimpleNamespace(
        diag=SimpleNamespace(
            constraint_name="some_other_constraint",
        ),
    )
    integrity_error = IntegrityError(
        "INSERT",
        {},
        original_error,
    )
    service.work_orders.add_workforce_assignment.side_effect = (
        integrity_error
    )

    with pytest.raises(IntegrityError) as exc_info:
        assign_workforce(service, work_order, workforce_profile)

    assert exc_info.value is integrity_error
    service.db.rollback.assert_called_once()
    service.activities.create_activity.assert_not_called()


def test_assignment_is_rolled_back_when_activity_recording_fails() -> None:
    service, work_order, workforce_profile = make_service()
    service.activities.create_activity.side_effect = RuntimeError(
        "Activity storage failed",
    )

    with pytest.raises(RuntimeError, match="Activity storage failed"):
        assign_workforce(service, work_order, workforce_profile)

    service.work_orders.add_workforce_assignment.assert_called_once()
    service.db.rollback.assert_called_once()


def test_removal_is_rolled_back_when_activity_recording_fails() -> None:
    service, work_order, workforce_profile = make_service()
    assignment = SimpleNamespace(
        workforce_profile_id=workforce_profile.id,
    )
    service.work_orders.get_workforce_assignment.return_value = assignment
    service.activities.create_activity.side_effect = RuntimeError(
        "Activity storage failed",
    )

    with pytest.raises(RuntimeError, match="Activity storage failed"):
        service.remove_workforce(
            organization_id=uuid.uuid4(),
            work_order_id=work_order.id,
            workforce_profile_id=workforce_profile.id,
            actor_user_id=uuid.uuid4(),
        )

    service.work_orders.remove_workforce_assignment.assert_called_once_with(
        assignment,
    )
    service.db.rollback.assert_called_once()


def test_successful_removal_records_activity() -> None:
    service, work_order, workforce_profile = make_service()
    assignment = SimpleNamespace(
        workforce_profile_id=workforce_profile.id,
    )
    service.work_orders.get_workforce_assignment.return_value = assignment

    result = service.remove_workforce(
        organization_id=uuid.uuid4(),
        work_order_id=work_order.id,
        workforce_profile_id=workforce_profile.id,
        actor_user_id=uuid.uuid4(),
    )

    assert result is None
    service.work_orders.remove_workforce_assignment.assert_called_once_with(
        assignment,
    )

    activity = service.activities.create_activity.call_args.args[0]
    assert activity.activity_type == "workforce_removed"
    assert activity.details == {
        "workforce_profile_id": str(workforce_profile.id),
    }

def test_update_workforce_responsibility_records_activity() -> None:
    service, work_order, workforce_profile = make_service()
    assignment = SimpleNamespace(
        responsibility="driller",
        custom_responsibility=None,
    )
    service.work_orders.get_workforce_assignment.return_value = assignment

    organization_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()

    result = service.update_workforce_responsibility(
        organization_id=organization_id,
        work_order_id=work_order.id,
        workforce_profile_id=workforce_profile.id,
        actor_user_id=actor_user_id,
        responsibility="supervisor",
    )

    assert result is sentinel.work_order_response
    assert assignment.responsibility == "supervisor"
    assert assignment.custom_responsibility is None
    service.db.flush.assert_called_once()

    activity = service.activities.create_activity.call_args.args[0]
    assert activity.activity_type == "workforce_responsibility_updated"
    assert activity.details == {
        "workforce_profile_id": str(workforce_profile.id),
        "previous_responsibility": "driller",
        "previous_custom_responsibility": None,
        "responsibility": "supervisor",
        "custom_responsibility": None,
    }


def test_unchanged_workforce_responsibility_records_no_activity() -> None:
    service, work_order, workforce_profile = make_service()
    assignment = SimpleNamespace(
        responsibility="driller",
        custom_responsibility=None,
    )
    service.work_orders.get_workforce_assignment.return_value = assignment

    service.update_workforce_responsibility(
        organization_id=uuid.uuid4(),
        work_order_id=work_order.id,
        workforce_profile_id=workforce_profile.id,
        actor_user_id=uuid.uuid4(),
        responsibility="driller",
    )

    service.db.flush.assert_not_called()
    service.activities.create_activity.assert_not_called()


def test_update_workforce_responsibility_requires_existing_assignment() -> None:
    service, work_order, workforce_profile = make_service()

    with pytest.raises(HTTPException) as exc_info:
        service.update_workforce_responsibility(
            organization_id=uuid.uuid4(),
            work_order_id=work_order.id,
            workforce_profile_id=workforce_profile.id,
            actor_user_id=uuid.uuid4(),
            responsibility="supervisor",
        )

    assert exc_info.value.status_code == 404
    service.db.flush.assert_not_called()
    service.activities.create_activity.assert_not_called()


def test_update_workforce_responsibility_rolls_back_on_activity_failure() -> None:
    service, work_order, workforce_profile = make_service()
    assignment = SimpleNamespace(
        responsibility="driller",
        custom_responsibility=None,
    )
    service.work_orders.get_workforce_assignment.return_value = assignment
    service.activities.create_activity.side_effect = RuntimeError(
        "activity recording failed"
    )

    with pytest.raises(RuntimeError, match="activity recording failed"):
        service.update_workforce_responsibility(
            organization_id=uuid.uuid4(),
            work_order_id=work_order.id,
            workforce_profile_id=workforce_profile.id,
            actor_user_id=uuid.uuid4(),
            responsibility="supervisor",
        )

    service.db.flush.assert_called_once()
    service.db.rollback.assert_called_once()
