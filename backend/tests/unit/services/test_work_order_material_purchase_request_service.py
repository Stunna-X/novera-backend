"""Purchase-request bridge tests for work-order shortages."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.schemas.work_order_material import (
    WorkOrderMaterialPurchaseRequestCreate,
)
from app.services.work_order_material_service import (
    SHORTAGE_REQUEST_SOURCE,
    WorkOrderMaterialService,
)


pytestmark = pytest.mark.unit


def make_shortage(
    *,
    name: str = "PVC casing",
    missing: str = "5.000",
    currency: str = "NGN",
) -> SimpleNamespace:
    requirement_id = uuid.uuid4()
    inventory_item_id = uuid.uuid4()

    return SimpleNamespace(
        id=requirement_id,
        inventory_item_id=inventory_item_id,
        required_quantity=Decimal("10.000"),
        covered_quantity=Decimal("5.000"),
        missing_quantity=Decimal(missing),
        coverage_percentage=Decimal("50.00"),
        readiness_status="partial",
        estimated_unit_cost=Decimal("2500.0000"),
        currency=currency,
        notes=None,
        item=SimpleNamespace(
            name=name,
            unit_of_measure="length",
        ),
    )


def make_service() -> WorkOrderMaterialService:
    service = WorkOrderMaterialService(MagicMock())
    service.procurement.create_requisition = MagicMock()
    service._get_work_order_or_404 = MagicMock(
        return_value=SimpleNamespace(
            id=uuid.uuid4(),
            work_order_number="WO-20260803-001",
            title="Borehole drilling",
            priority="high",
            scheduled_start=datetime(2026, 8, 10, tzinfo=UTC),
            status="scheduled",
            is_active=True,
        )
    )
    service._ensure_work_order_mutable = MagicMock()
    return service


def test_request_missing_materials_creates_draft_requisition() -> None:
    service = make_service()
    shortage = make_shortage()
    service.list_requirements = MagicMock(
        return_value=SimpleNamespace(items=[shortage])
    )
    service.purchase_requisitions.list_for_organization = (
        MagicMock(return_value=[])
    )
    requisition = SimpleNamespace(id=uuid.uuid4())
    service.procurement.create_requisition = MagicMock(
        return_value=requisition
    )
    expected = SimpleNamespace(created=True)
    service._purchase_request_response = MagicMock(
        return_value=expected
    )

    result = service.request_missing_materials(
        organization_id=uuid.uuid4(),
        work_order_id=uuid.uuid4(),
        payload=WorkOrderMaterialPurchaseRequestCreate(),
        actor_user_id=uuid.uuid4(),
        actor_membership_id=uuid.uuid4(),
    )

    assert result is expected
    call = service.procurement.create_requisition.call_args
    payload = call.kwargs["payload"]
    assert payload.work_order_id is not None
    assert payload.currency == "NGN"
    assert len(payload.line_items) == 1
    assert payload.line_items[0].quantity == Decimal("5.000")
    assert payload.line_items[0].inventory_item_id == (
        shortage.inventory_item_id
    )
    assert payload.details["source"] == SHORTAGE_REQUEST_SOURCE


def test_request_missing_materials_returns_open_generated_request() -> None:
    service = make_service()
    shortage = make_shortage()
    service.list_requirements = MagicMock(
        return_value=SimpleNamespace(items=[shortage])
    )
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        status="draft",
        details={
            "source": SHORTAGE_REQUEST_SOURCE,
            "source_requirement_ids": [str(shortage.id)],
        },
        line_items=[],
    )
    service.purchase_requisitions.list_for_organization = (
        MagicMock(return_value=[existing])
    )
    expected = SimpleNamespace(created=False)
    service._purchase_request_response = MagicMock(
        return_value=expected
    )

    result = service.request_missing_materials(
        organization_id=uuid.uuid4(),
        work_order_id=uuid.uuid4(),
        payload=WorkOrderMaterialPurchaseRequestCreate(),
        actor_user_id=uuid.uuid4(),
        actor_membership_id=uuid.uuid4(),
    )

    assert result is expected
    service.procurement.create_requisition.assert_not_called()
    service._purchase_request_response.assert_called_once_with(
        existing,
        created=False,
        source_requirement_ids=[shortage.id],
    )


def test_request_missing_materials_rejects_ready_job() -> None:
    service = make_service()
    service.list_requirements = MagicMock(
        return_value=SimpleNamespace(
            items=[
                SimpleNamespace(
                    missing_quantity=Decimal("0.000")
                )
            ]
        )
    )

    with pytest.raises(HTTPException) as raised:
        service.request_missing_materials(
            organization_id=uuid.uuid4(),
            work_order_id=uuid.uuid4(),
            payload=WorkOrderMaterialPurchaseRequestCreate(),
            actor_user_id=uuid.uuid4(),
            actor_membership_id=uuid.uuid4(),
        )

    assert raised.value.status_code == 409
    assert "no current material shortage" in raised.value.detail


def test_request_missing_materials_rejects_mixed_currencies() -> None:
    service = make_service()
    service.list_requirements = MagicMock(
        return_value=SimpleNamespace(
            items=[
                make_shortage(currency="NGN"),
                make_shortage(currency="USD"),
            ]
        )
    )
    service.purchase_requisitions.list_for_organization = (
        MagicMock(return_value=[])
    )

    with pytest.raises(HTTPException) as raised:
        service.request_missing_materials(
            organization_id=uuid.uuid4(),
            work_order_id=uuid.uuid4(),
            payload=WorkOrderMaterialPurchaseRequestCreate(),
            actor_user_id=uuid.uuid4(),
            actor_membership_id=uuid.uuid4(),
        )

    assert raised.value.status_code == 409
    assert "multiple currencies" in raised.value.detail
