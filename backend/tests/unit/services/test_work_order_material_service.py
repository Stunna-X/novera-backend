"""Readiness-calculation tests for work-order materials."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.work_order_material_service import (
    WorkOrderMaterialService,
)


pytestmark = pytest.mark.unit


def make_requirement(
    *,
    required_quantity: Decimal,
) -> SimpleNamespace:
    now = datetime.now(UTC)
    item_id = uuid.uuid4()

    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        work_order_id=uuid.uuid4(),
        inventory_item_id=item_id,
        required_quantity=required_quantity,
        notes=None,
        position=0,
        details={},
        is_active=True,
        created_by_user_id=None,
        updated_by_user_id=None,
        created_at=now,
        updated_at=now,
        inventory_item=SimpleNamespace(
            id=item_id,
            sku="PVC-001",
            name="PVC casing",
            item_type="material",
            category="Casing",
            unit_of_measure="length",
            default_unit_cost=Decimal("12500.0000"),
            currency="NGN",
            is_active=True,
        ),
    )


@pytest.fixture
def service() -> WorkOrderMaterialService:
    return WorkOrderMaterialService(MagicMock())


def test_readiness_is_available_when_stock_covers_requirement(
    service: WorkOrderMaterialService,
) -> None:
    requirement = make_requirement(
        required_quantity=Decimal("10"),
    )

    response = service._build_response(
        requirement,
        stock_totals={
            requirement.inventory_item_id: {
                "quantity_on_hand": Decimal("14"),
                "quantity_reserved": Decimal("2"),
                "active_location_count": 2,
            }
        },
        reservation_totals={},
    )

    assert response.readiness_status == "available"
    assert response.available_quantity == Decimal("12.000")
    assert response.missing_quantity == Decimal("0.000")
    assert response.coverage_percentage == Decimal("100.00")


def test_readiness_is_partial_when_only_some_stock_is_covered(
    service: WorkOrderMaterialService,
) -> None:
    requirement = make_requirement(
        required_quantity=Decimal("10"),
    )

    response = service._build_response(
        requirement,
        stock_totals={
            requirement.inventory_item_id: {
                "quantity_on_hand": Decimal("6"),
                "quantity_reserved": Decimal("1"),
                "active_location_count": 1,
            }
        },
        reservation_totals={},
    )

    assert response.readiness_status == "partial"
    assert response.covered_quantity == Decimal("5.000")
    assert response.missing_quantity == Decimal("5.000")
    assert response.coverage_percentage == Decimal("50.00")


def test_job_reservation_counts_as_secured_stock(
    service: WorkOrderMaterialService,
) -> None:
    requirement = make_requirement(
        required_quantity=Decimal("10"),
    )

    response = service._build_response(
        requirement,
        stock_totals={
            requirement.inventory_item_id: {
                "quantity_on_hand": Decimal("10"),
                "quantity_reserved": Decimal("8"),
                "active_location_count": 1,
            }
        },
        reservation_totals={
            requirement.inventory_item_id: Decimal("8"),
        },
    )

    assert response.readiness_status == "available"
    assert response.available_quantity == Decimal("2.000")
    assert response.reserved_for_work_order == Decimal("8.000")
    assert response.covered_quantity == Decimal("10.000")


def test_readiness_is_missing_without_stock(
    service: WorkOrderMaterialService,
) -> None:
    requirement = make_requirement(
        required_quantity=Decimal("4"),
    )

    response = service._build_response(
        requirement,
        stock_totals={},
        reservation_totals={},
    )

    assert response.readiness_status == "missing"
    assert response.covered_quantity == Decimal("0.000")
    assert response.missing_quantity == Decimal("4.000")
