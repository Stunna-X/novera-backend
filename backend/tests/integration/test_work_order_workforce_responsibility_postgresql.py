"""
PostgreSQL integration tests for work-order workforce responsibilities.
"""

from __future__ import annotations

import uuid
from typing import Protocol

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.work_order import WorkOrderWorkforceAssignment
from app.models.work_order_activity import WorkOrderActivity
from app.models.workforce_profile import WorkforceProfile
from app.services.work_order_service import WorkOrderService


class InventoryIntegrationData(Protocol):
    organization_id: uuid.UUID
    actor_user_id: uuid.UUID
    work_order_id: uuid.UUID


@pytest.fixture
def workforce_assignment_data(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: InventoryIntegrationData,
) -> uuid.UUID:
    """Create a standalone workforce profile and its work-order assignment."""

    workforce_profile_id = uuid.uuid4()

    with integration_session_factory() as db:
        profile = WorkforceProfile(
            id=workforce_profile_id,
            organization_id=inventory_integration_data.organization_id,
            full_name="Integration Field Technician",
        )
        assignment = WorkOrderWorkforceAssignment(
            id=uuid.uuid4(),
            work_order_id=inventory_integration_data.work_order_id,
            workforce_profile_id=workforce_profile_id,
            responsibility="technician",
            custom_responsibility=None,
        )

        db.add_all([profile, assignment])
        db.commit()

    return workforce_profile_id


def test_update_workforce_responsibility_persists_and_records_activity(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: InventoryIntegrationData,
    workforce_assignment_data: uuid.UUID,
) -> None:
    """Persist responsibility changes and their audit activity."""

    with integration_session_factory() as db:
        service = WorkOrderService(db)

        service.update_workforce_responsibility(
            organization_id=inventory_integration_data.organization_id,
            work_order_id=inventory_integration_data.work_order_id,
            workforce_profile_id=workforce_assignment_data,
            actor_user_id=inventory_integration_data.actor_user_id,
            responsibility="supervisor",
        )

        db.commit()

    with integration_session_factory() as db:
        assignment = db.execute(
            select(WorkOrderWorkforceAssignment).where(
                WorkOrderWorkforceAssignment.work_order_id
                == inventory_integration_data.work_order_id,
                WorkOrderWorkforceAssignment.workforce_profile_id
                == workforce_assignment_data,
            )
        ).scalar_one()

        assert assignment.responsibility == "supervisor"
        assert assignment.custom_responsibility is None

        activities = db.execute(
            select(WorkOrderActivity).where(
                WorkOrderActivity.work_order_id
                == inventory_integration_data.work_order_id,
                WorkOrderActivity.activity_type
                == "workforce_responsibility_updated",
            )
        ).scalars().all()

        assert len(activities) == 1

        activity = activities[0]
        assert activity.actor_user_id == inventory_integration_data.actor_user_id
        assert activity.details == {
            "workforce_profile_id": str(workforce_assignment_data),
            "previous_responsibility": "technician",
            "previous_custom_responsibility": None,
            "responsibility": "supervisor",
            "custom_responsibility": None,
        }


def test_unchanged_workforce_responsibility_creates_no_activity(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: InventoryIntegrationData,
    workforce_assignment_data: uuid.UUID,
) -> None:
    """An unchanged responsibility must not create an audit entry."""

    with integration_session_factory() as db:
        service = WorkOrderService(db)

        service.update_workforce_responsibility(
            organization_id=inventory_integration_data.organization_id,
            work_order_id=inventory_integration_data.work_order_id,
            workforce_profile_id=workforce_assignment_data,
            actor_user_id=inventory_integration_data.actor_user_id,
            responsibility="technician",
        )

        db.commit()

    with integration_session_factory() as db:
        activities = db.execute(
            select(WorkOrderActivity).where(
                WorkOrderActivity.work_order_id
                == inventory_integration_data.work_order_id,
                WorkOrderActivity.activity_type
                == "workforce_responsibility_updated",
            )
        ).scalars().all()

        assert activities == []


def test_update_workforce_responsibility_requires_existing_assignment(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: InventoryIntegrationData,
) -> None:
    """Updating a missing assignment must return 404, not create it."""

    with integration_session_factory() as db:
        service = WorkOrderService(db)

        with pytest.raises(HTTPException) as error:
            service.update_workforce_responsibility(
                organization_id=inventory_integration_data.organization_id,
                work_order_id=inventory_integration_data.work_order_id,
                workforce_profile_id=uuid.uuid4(),
                actor_user_id=inventory_integration_data.actor_user_id,
                responsibility="supervisor",
            )

        assert error.value.status_code == 404
        assert error.value.detail == "Workforce assignment not found."

        assignment_count = db.execute(
            select(WorkOrderWorkforceAssignment).where(
                WorkOrderWorkforceAssignment.work_order_id
                == inventory_integration_data.work_order_id,
            )
        ).scalars().all()

        assert assignment_count == []
