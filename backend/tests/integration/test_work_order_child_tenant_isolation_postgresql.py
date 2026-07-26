"""
PostgreSQL tenant-isolation tests for work-order child resources.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Protocol

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.schemas.work_order_checklist import (
    WorkOrderChecklistItemCreate,
    WorkOrderChecklistItemUpdate,
)
from app.schemas.work_order_expense import (
    WorkOrderExpenseCreate,
    WorkOrderExpenseUpdate,
)
from app.schemas.work_order_note import (
    WorkOrderNoteCreate,
    WorkOrderNoteUpdate,
)
from app.services.work_order_checklist_service import (
    WorkOrderChecklistService,
)
from app.services.work_order_expense_service import (
    WorkOrderExpenseService,
)
from app.services.work_order_note_service import (
    WorkOrderNoteService,
)


class TenantIntegrationData(Protocol):
    """
    Minimum fixture contract required by these tests.
    """

    organization_id: uuid.UUID
    other_organization_id: uuid.UUID
    actor_user_id: uuid.UUID
    work_order_id: uuid.UUID


def _assert_not_found(
    error: pytest.ExceptionInfo[HTTPException],
) -> None:
    """
    Assert an information-leak-safe not-found response.
    """

    assert error.value.status_code == 404


def test_checklist_item_cannot_cross_organization_boundary(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: TenantIntegrationData,
) -> None:
    """
    A foreign organization must not access checklist resources.
    """

    token = uuid.uuid4().hex
    original_title = f"Inspect casing {token[:10]}"

    with integration_session_factory() as db:
        created = WorkOrderChecklistService(db).create_item(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            work_order_id=(
                inventory_integration_data.work_order_id
            ),
            payload=WorkOrderChecklistItemCreate(
                title=original_title,
                description=(
                    "Confirm casing condition before deployment."
                ),
                is_required=True,
            ),
            actor_user_id=(
                inventory_integration_data.actor_user_id
            ),
        )

        item_id = created.id

    with integration_session_factory() as db:
        service = WorkOrderChecklistService(db)

        with pytest.raises(HTTPException) as read_error:
            service.get_item(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                work_order_id=(
                    inventory_integration_data.work_order_id
                ),
                item_id=item_id,
            )

        _assert_not_found(read_error)

        with pytest.raises(HTTPException) as list_error:
            service.list_items(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                work_order_id=(
                    inventory_integration_data.work_order_id
                ),
            )

        _assert_not_found(list_error)

        with pytest.raises(HTTPException) as progress_error:
            service.get_progress(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                work_order_id=(
                    inventory_integration_data.work_order_id
                ),
            )

        _assert_not_found(progress_error)

        with pytest.raises(HTTPException) as update_error:
            service.update_item(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                work_order_id=(
                    inventory_integration_data.work_order_id
                ),
                item_id=item_id,
                payload=WorkOrderChecklistItemUpdate(
                    title="Cross-tenant checklist overwrite",
                ),
                actor_user_id=(
                    inventory_integration_data.actor_user_id
                ),
            )

        _assert_not_found(update_error)

        with pytest.raises(
            HTTPException
        ) as deactivate_error:
            service.deactivate_item(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                work_order_id=(
                    inventory_integration_data.work_order_id
                ),
                item_id=item_id,
                actor_user_id=(
                    inventory_integration_data.actor_user_id
                ),
            )

        _assert_not_found(deactivate_error)

        original = service.get_item(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            work_order_id=(
                inventory_integration_data.work_order_id
            ),
            item_id=item_id,
        )

        assert original.title == original_title
        assert original.is_active is True


def test_work_order_note_cannot_cross_organization_boundary(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: TenantIntegrationData,
) -> None:
    """
    A foreign organization must not access work-order notes.
    """

    token = uuid.uuid4().hex
    original_body = (
        f"Field conditions recorded for isolation test {token[:10]}."
    )

    with integration_session_factory() as db:
        created = WorkOrderNoteService(db).create_note(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            work_order_id=(
                inventory_integration_data.work_order_id
            ),
            payload=WorkOrderNoteCreate(
                body=original_body,
                attachments=[],
            ),
            actor_user_id=(
                inventory_integration_data.actor_user_id
            ),
        )

        note_id = created.id

    with integration_session_factory() as db:
        service = WorkOrderNoteService(db)

        with pytest.raises(HTTPException) as read_error:
            service.get_note(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                work_order_id=(
                    inventory_integration_data.work_order_id
                ),
                note_id=note_id,
            )

        _assert_not_found(read_error)

        with pytest.raises(HTTPException) as list_error:
            service.list_notes(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                work_order_id=(
                    inventory_integration_data.work_order_id
                ),
            )

        _assert_not_found(list_error)

        with pytest.raises(HTTPException) as update_error:
            service.update_note(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                work_order_id=(
                    inventory_integration_data.work_order_id
                ),
                note_id=note_id,
                payload=WorkOrderNoteUpdate(
                    body="Cross-tenant note overwrite.",
                ),
                actor_user_id=(
                    inventory_integration_data.actor_user_id
                ),
            )

        _assert_not_found(update_error)

        with pytest.raises(
            HTTPException
        ) as deactivate_error:
            service.deactivate_note(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                work_order_id=(
                    inventory_integration_data.work_order_id
                ),
                note_id=note_id,
                actor_user_id=(
                    inventory_integration_data.actor_user_id
                ),
            )

        _assert_not_found(deactivate_error)

        original = service.get_note(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            work_order_id=(
                inventory_integration_data.work_order_id
            ),
            note_id=note_id,
        )

        assert original.body == original_body
        assert original.is_active is True


def test_work_order_expense_cannot_cross_organization_boundary(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: TenantIntegrationData,
) -> None:
    """
    A foreign organization must not access work-order expenses.
    """

    token = uuid.uuid4().hex
    original_description = (
        f"Isolation test transport expense {token[:10]}"
    )

    with integration_session_factory() as db:
        created = WorkOrderExpenseService(db).create_expense(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            work_order_id=(
                inventory_integration_data.work_order_id
            ),
            payload=WorkOrderExpenseCreate(
                category="transport",
                description=original_description,
                quantity=Decimal("2.000"),
                unit_cost=Decimal("1500.0000"),
                currency="NGN",
                expense_date=date.today(),
                vendor_name="Tenant Isolation Transport",
                is_billable=True,
            ),
            actor_user_id=(
                inventory_integration_data.actor_user_id
            ),
        )

        expense_id = created.id

    with integration_session_factory() as db:
        service = WorkOrderExpenseService(db)

        with pytest.raises(HTTPException) as read_error:
            service.get_expense(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                work_order_id=(
                    inventory_integration_data.work_order_id
                ),
                expense_id=expense_id,
            )

        _assert_not_found(read_error)

        with pytest.raises(HTTPException) as list_error:
            service.list_expenses(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                work_order_id=(
                    inventory_integration_data.work_order_id
                ),
            )

        _assert_not_found(list_error)

        with pytest.raises(HTTPException) as summary_error:
            service.get_summary(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                work_order_id=(
                    inventory_integration_data.work_order_id
                ),
            )

        _assert_not_found(summary_error)

        with pytest.raises(HTTPException) as update_error:
            service.update_expense(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                work_order_id=(
                    inventory_integration_data.work_order_id
                ),
                expense_id=expense_id,
                payload=WorkOrderExpenseUpdate(
                    description=(
                        "Cross-tenant expense overwrite"
                    ),
                ),
                actor_user_id=(
                    inventory_integration_data.actor_user_id
                ),
            )

        _assert_not_found(update_error)

        with pytest.raises(
            HTTPException
        ) as deactivate_error:
            service.deactivate_expense(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                work_order_id=(
                    inventory_integration_data.work_order_id
                ),
                expense_id=expense_id,
                actor_user_id=(
                    inventory_integration_data.actor_user_id
                ),
            )

        _assert_not_found(deactivate_error)

        original = service.get_expense(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            work_order_id=(
                inventory_integration_data.work_order_id
            ),
            expense_id=expense_id,
        )

        assert original.description == original_description
        assert original.is_active is True
