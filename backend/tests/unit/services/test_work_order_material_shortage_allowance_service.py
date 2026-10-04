"""
Lifecycle and safety tests for work-order material shortage allowances.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.schemas.work_order_material_shortage_allowance import (
    WorkOrderMaterialShortageAllowanceApprove,
    WorkOrderMaterialShortageAllowanceCancel,
    WorkOrderMaterialShortageAllowanceCreate,
    WorkOrderMaterialShortageAllowanceReject,
    WorkOrderMaterialShortageAllowanceUpdate,
)
from app.services.work_order_material_shortage_allowance_service import (
    WorkOrderMaterialShortageAllowanceService,
)


pytestmark = pytest.mark.unit


def make_work_order(
    *,
    status: str = "in_progress",
    is_active: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        status=status,
        is_active=is_active,
    )


def make_requirement(
    *,
    required_quantity: Decimal = Decimal("90"),
    work_order_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    inventory_item_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=organization_id or uuid.uuid4(),
        work_order_id=work_order_id or uuid.uuid4(),
        inventory_item_id=inventory_item_id or uuid.uuid4(),
        required_quantity=required_quantity,
        is_active=True,
    )


def make_allowance(
    *,
    requirement: SimpleNamespace,
    status: str = "draft",
    requested_quantity: Decimal = Decimal("60"),
    approved_quantity: Decimal = Decimal("0"),
    is_active: bool = True,
) -> SimpleNamespace:
    now = datetime.now(UTC)

    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=requirement.organization_id,
        work_order_id=requirement.work_order_id,
        work_order_material_requirement_id=requirement.id,
        requested_quantity=requested_quantity,
        approved_quantity=approved_quantity,
        status=status,
        reason="Material shortage requires field authorization.",
        notes=None,
        details={},
        created_by_user_id=uuid.uuid4(),
        submitted_by_user_id=None,
        approved_by_user_id=None,
        rejected_by_user_id=None,
        cancelled_by_user_id=None,
        submitted_at=None,
        approved_at=None,
        rejected_at=None,
        cancelled_at=None,
        rejection_reason=None,
        cancellation_reason=None,
        is_active=is_active,
        created_at=now,
        updated_at=now,
        work_order_material_requirement=requirement,
    )


def configure_common_repositories(
    service: WorkOrderMaterialShortageAllowanceService,
) -> None:
    service.work_orders = MagicMock()
    service.allowances = MagicMock()
    service.materials = MagicMock()
    service.activities = MagicMock()


def configure_live_shortage(
    service: WorkOrderMaterialShortageAllowanceService,
    requirement: SimpleNamespace,
    *,
    missing_quantity: Decimal,
) -> None:
    """
    Configure the material repository so _live_shortage() calculates
    the requested physical shortage.
    """
    required = requirement.required_quantity

    covered = max(
        required - missing_quantity,
        Decimal("0"),
    )

    service.materials.get_stock_totals.return_value = {
        requirement.inventory_item_id: {
            "quantity_on_hand": covered,
            "quantity_reserved": Decimal("0"),
            "active_location_count": 1,
        }
    }

    service.materials.get_work_order_reservation_totals.return_value = {}


def configure_create_persistence(
    service: WorkOrderMaterialShortageAllowanceService,
    requirement: SimpleNamespace,
) -> None:
    """
    Model the create -> flush -> reload persistence flow used by the service.

    The real repository flushes the new allowance, which causes SQLAlchemy
    defaults such as id and timestamps to be populated. The repository also
    reloads the material requirement relationship before the service builds
    its response. The mock must reproduce those persistence guarantees.
    """
    created_allowances: list[SimpleNamespace] = []

    def create_allowance(allowance: SimpleNamespace) -> SimpleNamespace:
        now = datetime.now(UTC)

        # Simulate database/SQLAlchemy-generated defaults.
        if allowance.id is None:
            allowance.id = uuid.uuid4()

        if allowance.created_at is None:
            allowance.created_at = now

        if allowance.updated_at is None:
            allowance.updated_at = now

        # Simulate the relationship restored by the repository query.
        allowance.work_order_material_requirement = requirement

        created_allowances.append(allowance)
        return allowance

    def get_created_allowance(**_: object) -> SimpleNamespace:
        return created_allowances[-1]

    service.allowances.create.side_effect = create_allowance
    service.allowances.get_for_work_order.side_effect = (
        get_created_allowance
    )

@pytest.fixture
def service() -> WorkOrderMaterialShortageAllowanceService:
    return WorkOrderMaterialShortageAllowanceService(MagicMock())


def test_create_allowance_creates_draft_without_changing_inventory(
    service: WorkOrderMaterialShortageAllowanceService,
) -> None:
    configure_common_repositories(service)

    work_order = make_work_order()

    requirement = make_requirement(
        required_quantity=Decimal("90"),
        work_order_id=work_order.id,
        organization_id=work_order.organization_id,
    )

    service.work_orders.get_for_organization.return_value = work_order
    service.materials.get_for_work_order.return_value = requirement
    service.allowances.get_for_requirement.return_value = None

    configure_live_shortage(
        service,
        requirement,
        missing_quantity=Decimal("60"),
    )
    configure_create_persistence(
        service,
        requirement,
    )

    payload = WorkOrderMaterialShortageAllowanceCreate(
        requested_quantity=Decimal("60"),
        reason="Proceed with field work despite current stock shortage.",
    )

    response = service.create_allowance(
        organization_id=work_order.organization_id,
        work_order_id=work_order.id,
        requirement_id=requirement.id,
        payload=payload,
        actor_user_id=uuid.uuid4(),
    )

    assert response.status == "draft"
    assert response.requested_quantity == Decimal("60.000")
    assert response.approved_quantity == Decimal("0.000")
    assert response.current_missing_quantity == Decimal("60.000")

    allowance = service.allowances.create.call_args.args[0]

    assert allowance.status == "draft"
    assert allowance.requested_quantity == Decimal("60.000")
    assert allowance.approved_quantity == Decimal("0.000")

    service.activities.create_activity.assert_called_once()

    service.materials.get_stock_totals.assert_called()
    service.materials.get_work_order_reservation_totals.assert_called()

    # Allowances never mutate physical inventory.
    service.materials.update.assert_not_called()
    service.materials.create.assert_not_called()
    service.materials.delete.assert_not_called()


def test_create_allowance_rejects_request_above_live_shortage(
    service: WorkOrderMaterialShortageAllowanceService,
) -> None:
    configure_common_repositories(service)

    work_order = make_work_order()

    requirement = make_requirement(
        required_quantity=Decimal("90"),
        work_order_id=work_order.id,
        organization_id=work_order.organization_id,
    )

    service.work_orders.get_for_organization.return_value = work_order
    service.materials.get_for_work_order.return_value = requirement
    service.allowances.get_for_requirement.return_value = None

    configure_live_shortage(
        service,
        requirement,
        missing_quantity=Decimal("60"),
    )

    payload = WorkOrderMaterialShortageAllowanceCreate(
        requested_quantity=Decimal("61"),
        reason="Attempting to authorize more than the live shortage.",
    )

    with pytest.raises(HTTPException) as exc_info:
        service.create_allowance(
            organization_id=work_order.organization_id,
            work_order_id=work_order.id,
            requirement_id=requirement.id,
            payload=payload,
            actor_user_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 409
    service.allowances.create.assert_not_called()


def test_update_rejected_allowance_returns_it_to_draft(
    service: WorkOrderMaterialShortageAllowanceService,
) -> None:
    configure_common_repositories(service)

    work_order = make_work_order()

    requirement = make_requirement(
        work_order_id=work_order.id,
        organization_id=work_order.organization_id,
    )

    allowance = make_allowance(
        requirement=requirement,
        status="rejected",
    )

    allowance.rejection_reason = "Need better justification."
    allowance.rejected_at = datetime.now(UTC)
    allowance.rejected_by_user_id = uuid.uuid4()

    service.work_orders.get_for_organization.return_value = work_order
    service.allowances.get_for_work_order.return_value = allowance
    service.materials.get_for_work_order.return_value = requirement

    configure_live_shortage(
        service,
        requirement,
        missing_quantity=Decimal("60"),
    )

    payload = WorkOrderMaterialShortageAllowanceUpdate(
        requested_quantity=Decimal("55"),
        reason="Updated justification for field execution.",
    )

    response = service.update_allowance(
        organization_id=work_order.organization_id,
        work_order_id=work_order.id,
        allowance_id=allowance.id,
        payload=payload,
        actor_user_id=uuid.uuid4(),
    )

    assert response.status == "draft"
    assert response.requested_quantity == Decimal("55.000")
    assert response.rejection_reason is None
    assert response.rejected_at is None
    assert response.rejected_by_user_id is None
    assert response.approved_quantity == Decimal("0.000")

    service.allowances.update.assert_called_once()
    service.activities.create_activity.assert_called_once()


def test_submit_changes_draft_to_submitted(
    service: WorkOrderMaterialShortageAllowanceService,
) -> None:
    configure_common_repositories(service)

    work_order = make_work_order()

    requirement = make_requirement(
        work_order_id=work_order.id,
        organization_id=work_order.organization_id,
    )

    allowance = make_allowance(
        requirement=requirement,
        status="draft",
    )

    service.work_orders.get_for_organization.return_value = work_order
    service.allowances.get_for_work_order.return_value = allowance
    service.materials.get_for_work_order.return_value = requirement

    configure_live_shortage(
        service,
        requirement,
        missing_quantity=Decimal("60"),
    )

    response = service.submit_allowance(
        organization_id=work_order.organization_id,
        work_order_id=work_order.id,
        allowance_id=allowance.id,
        actor_user_id=uuid.uuid4(),
    )

    assert response.status == "submitted"
    assert allowance.status == "submitted"
    assert allowance.submitted_at is not None
    assert allowance.submitted_by_user_id is not None

    service.allowances.update.assert_called_once()
    service.activities.create_activity.assert_called_once()


def test_approve_submitted_allowance_rechecks_live_shortage(
    service: WorkOrderMaterialShortageAllowanceService,
) -> None:
    configure_common_repositories(service)

    work_order = make_work_order()

    requirement = make_requirement(
        required_quantity=Decimal("90"),
        work_order_id=work_order.id,
        organization_id=work_order.organization_id,
    )

    allowance = make_allowance(
        requirement=requirement,
        status="submitted",
        requested_quantity=Decimal("60"),
    )

    service.work_orders.get_for_organization.return_value = work_order
    service.allowances.get_for_work_order.return_value = allowance
    service.allowances.get_for_requirement.return_value = allowance
    service.materials.get_for_work_order.return_value = requirement

    # Shortage has reduced from 60 to 40 after submission.
    configure_live_shortage(
        service,
        requirement,
        missing_quantity=Decimal("40"),
    )

    payload = WorkOrderMaterialShortageAllowanceApprove(
        approved_quantity=Decimal("60"),
    )

    with pytest.raises(HTTPException) as exc_info:
        service.approve_allowance(
            organization_id=work_order.organization_id,
            work_order_id=work_order.id,
            allowance_id=allowance.id,
            payload=payload,
            actor_user_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 409
    assert allowance.status == "submitted"
    assert allowance.approved_quantity == Decimal("0")

    service.activities.create_activity.assert_not_called()


def test_approve_does_not_modify_physical_inventory(
    service: WorkOrderMaterialShortageAllowanceService,
) -> None:
    configure_common_repositories(service)

    work_order = make_work_order()

    requirement = make_requirement(
        required_quantity=Decimal("90"),
        work_order_id=work_order.id,
        organization_id=work_order.organization_id,
    )

    allowance = make_allowance(
        requirement=requirement,
        status="submitted",
        requested_quantity=Decimal("60"),
    )

    service.work_orders.get_for_organization.return_value = work_order
    service.allowances.get_for_work_order.return_value = allowance
    service.allowances.get_for_requirement.return_value = allowance
    service.materials.get_for_work_order.return_value = requirement

    configure_live_shortage(
        service,
        requirement,
        missing_quantity=Decimal("60"),
    )

    payload = WorkOrderMaterialShortageAllowanceApprove(
        approved_quantity=Decimal("60"),
    )

    response = service.approve_allowance(
        organization_id=work_order.organization_id,
        work_order_id=work_order.id,
        allowance_id=allowance.id,
        payload=payload,
        actor_user_id=uuid.uuid4(),
    )

    assert response.status == "approved"
    assert response.approved_quantity == Decimal("60.000")

    service.allowances.update.assert_called_once()

    # Approval authorizes workflow only; it does not change physical stock.
    service.materials.update.assert_not_called()
    service.materials.create.assert_not_called()
    service.materials.delete.assert_not_called()


def test_reject_changes_submitted_to_rejected(
    service: WorkOrderMaterialShortageAllowanceService,
) -> None:
    configure_common_repositories(service)

    work_order = make_work_order()

    requirement = make_requirement(
        work_order_id=work_order.id,
        organization_id=work_order.organization_id,
    )

    allowance = make_allowance(
        requirement=requirement,
        status="submitted",
        requested_quantity=Decimal("60"),
    )

    service.work_orders.get_for_organization.return_value = work_order
    service.allowances.get_for_work_order.return_value = allowance
    service.materials.get_for_work_order.return_value = requirement

    configure_live_shortage(
        service,
        requirement,
        missing_quantity=Decimal("60"),
    )

    payload = WorkOrderMaterialShortageAllowanceReject(
        rejection_reason="Provide a more specific operational justification.",
    )

    response = service.reject_allowance(
        organization_id=work_order.organization_id,
        work_order_id=work_order.id,
        allowance_id=allowance.id,
        payload=payload,
        actor_user_id=uuid.uuid4(),
    )

    assert response.status == "rejected"
    assert response.rejection_reason == (
        "Provide a more specific operational justification."
    )
    assert response.approved_quantity == Decimal("0")

    service.allowances.update.assert_called_once()
    service.activities.create_activity.assert_called_once()


def test_cancel_approved_allowance_marks_it_inactive(
    service: WorkOrderMaterialShortageAllowanceService,
) -> None:
    configure_common_repositories(service)

    work_order = make_work_order()

    requirement = make_requirement(
        work_order_id=work_order.id,
        organization_id=work_order.organization_id,
    )

    allowance = make_allowance(
        requirement=requirement,
        status="approved",
        requested_quantity=Decimal("60"),
        approved_quantity=Decimal("60"),
    )

    service.work_orders.get_for_organization.return_value = work_order
    service.allowances.get_for_work_order.return_value = allowance
    service.materials.get_for_work_order.return_value = requirement

    configure_live_shortage(
        service,
        requirement,
        missing_quantity=Decimal("60"),
    )

    payload = WorkOrderMaterialShortageAllowanceCancel(
        cancellation_reason="Material became available before field execution.",
    )

    response = service.cancel_allowance(
        organization_id=work_order.organization_id,
        work_order_id=work_order.id,
        allowance_id=allowance.id,
        payload=payload,
        actor_user_id=uuid.uuid4(),
    )

    assert response.status == "cancelled"
    assert response.is_active is False
    assert response.cancellation_reason == (
        "Material became available before field execution."
    )
    assert response.cancelled_at is not None
    assert response.cancelled_by_user_id is not None

    service.allowances.update.assert_called_once()
    service.activities.create_activity.assert_called_once()


@pytest.mark.parametrize(
    "work_order_status",
    ["completed", "cancelled"],
)
def test_terminal_work_order_cannot_create_allowance(
    service: WorkOrderMaterialShortageAllowanceService,
    work_order_status: str,
) -> None:
    configure_common_repositories(service)

    work_order = make_work_order(
        status=work_order_status,
    )

    service.work_orders.get_for_organization.return_value = work_order

    payload = WorkOrderMaterialShortageAllowanceCreate(
        requested_quantity=Decimal("60"),
        reason="Attempt to authorize a terminal work order.",
    )

    with pytest.raises(HTTPException) as exc_info:
        service.create_allowance(
            organization_id=work_order.organization_id,
            work_order_id=work_order.id,
            requirement_id=uuid.uuid4(),
            payload=payload,
            actor_user_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 409
    service.allowances.create.assert_not_called()


def test_duplicate_allowance_is_rejected(
    service: WorkOrderMaterialShortageAllowanceService,
) -> None:
    configure_common_repositories(service)

    work_order = make_work_order()

    requirement = make_requirement(
        work_order_id=work_order.id,
        organization_id=work_order.organization_id,
    )

    existing_allowance = make_allowance(
        requirement=requirement,
    )

    service.work_orders.get_for_organization.return_value = work_order
    service.materials.get_for_work_order.return_value = requirement
    service.allowances.get_for_requirement.return_value = (
        existing_allowance
    )

    payload = WorkOrderMaterialShortageAllowanceCreate(
        requested_quantity=Decimal("60"),
        reason="Second allowance for the same requirement.",
    )

    with pytest.raises(HTTPException) as exc_info:
        service.create_allowance(
            organization_id=work_order.organization_id,
            work_order_id=work_order.id,
            requirement_id=requirement.id,
            payload=payload,
            actor_user_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 409
    service.allowances.create.assert_not_called()
def test_cancel_submitted_allowance_marks_it_inactive(
    service: WorkOrderMaterialShortageAllowanceService,
) -> None:
    configure_common_repositories(service)

    work_order = make_work_order()

    requirement = make_requirement(
        work_order_id=work_order.id,
        organization_id=work_order.organization_id,
    )

    allowance = make_allowance(
        requirement=requirement,
        status="submitted",
        requested_quantity=Decimal("60"),
    )

    service.work_orders.get_for_organization.return_value = work_order
    service.allowances.get_for_work_order.return_value = allowance
    service.materials.get_for_work_order.return_value = requirement

    configure_live_shortage(
        service,
        requirement,
        missing_quantity=Decimal("60"),
    )

    payload = WorkOrderMaterialShortageAllowanceCancel(
        cancellation_reason="Cancel submitted allowance before field execution.",
    )

    response = service.cancel_allowance(
        organization_id=work_order.organization_id,
        work_order_id=work_order.id,
        allowance_id=allowance.id,
        payload=payload,
        actor_user_id=uuid.uuid4(),
    )

    assert response.status == "cancelled"
    assert response.is_active is False
    assert response.cancellation_reason == (
        "Cancel submitted allowance before field execution."
    )
    assert response.cancelled_at is not None
    assert response.cancelled_by_user_id is not None

    service.allowances.update.assert_called_once()
    service.activities.create_activity.assert_called_once()

