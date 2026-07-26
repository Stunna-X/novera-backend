"""Focused unit tests for inventory stock-operation invariants."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

import app.services.inventory_service as inventory_service_module
from app.schemas.inventory import (
    AdjustInventoryStockSchema,
    ConsumeInventoryReservationSchema,
    CreateInventoryReservationSchema,
    IssueInventoryStockSchema,
    ReceiveInventoryStockSchema,
    TransferInventoryStockSchema,
)
from app.services.inventory_service import InventoryService


pytestmark = pytest.mark.unit


@dataclass
class BalanceStub:
    organization_id: uuid.UUID
    item_id: uuid.UUID
    location_id: uuid.UUID
    quantity_on_hand: Decimal
    quantity_reserved: Decimal
    average_unit_cost: Decimal
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    last_movement_at: datetime | None = None

    @property
    def available_quantity(self) -> Decimal:
        return (
            Decimal(self.quantity_on_hand)
            - Decimal(self.quantity_reserved)
        )


@dataclass
class ReservationStub:
    organization_id: uuid.UUID
    item_id: uuid.UUID
    location_id: uuid.UUID
    work_order_id: uuid.UUID
    quantity_reserved: Decimal
    quantity_consumed: Decimal
    status: str = "active"
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    expires_at: datetime | None = None
    notes: str | None = None
    details: dict[str, object] = field(default_factory=dict)
    item: object = field(
        default_factory=lambda: SimpleNamespace(currency="NGN")
    )
    consumed_at: datetime | None = None
    released_at: datetime | None = None
    updated_by_user_id: uuid.UUID | None = None
    is_active: bool = True

    @property
    def remaining_quantity(self) -> Decimal:
        return (
            Decimal(self.quantity_reserved)
            - Decimal(self.quantity_consumed)
        )


@pytest.fixture
def service() -> InventoryService:
    db = MagicMock()
    instance = InventoryService(db)
    instance.inventory = MagicMock()
    instance.work_orders = MagicMock()
    return instance


def make_item(
    organization_id: uuid.UUID,
    *,
    currency: str = "NGN",
    default_unit_cost: Decimal = Decimal("2.0000"),
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=organization_id,
        currency=currency,
        default_unit_cost=default_unit_cost,
        is_active=True,
    )


def attach_persisted_id(model: object) -> object:
    if getattr(model, "id", None) is None:
        setattr(model, "id", uuid.uuid4())
    return model


def test_weighted_average_cost_is_quantized() -> None:
    result = InventoryService._weighted_average_cost(
        existing_quantity=Decimal("10"),
        existing_unit_cost=Decimal("2"),
        incoming_quantity=Decimal("5"),
        incoming_unit_cost=Decimal("4"),
    )

    assert result == Decimal("2.6667")


def test_item_lookup_is_organization_scoped(service: InventoryService) -> None:
    organization_id = uuid.uuid4()
    item_id = uuid.uuid4()
    service.inventory.get_item_for_organization.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        service._get_item_or_404(
            organization_id=organization_id,
            item_id=item_id,
        )

    assert exc_info.value.status_code == 404
    service.inventory.get_item_for_organization.assert_called_once_with(
        organization_id=organization_id,
        item_id=item_id,
        include_inactive=False,
        for_update=False,
    )


def test_receive_stock_updates_balance_and_records_movement(
    service: InventoryService,
) -> None:
    organization_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    location_id = uuid.uuid4()
    item = make_item(organization_id)
    balance = BalanceStub(
        organization_id=organization_id,
        item_id=item.id,
        location_id=location_id,
        quantity_on_hand=Decimal("10.000"),
        quantity_reserved=Decimal("1.000"),
        average_unit_cost=Decimal("2.0000"),
    )
    expected_result = object()

    service._get_item_or_404 = MagicMock(return_value=item)
    service._get_location_or_404 = MagicMock(return_value=object())
    service._get_balance_for_update = MagicMock(
        return_value=balance
    )
    service.inventory.create_movement.side_effect = attach_persisted_id
    service._reload_operation_result = MagicMock(
        return_value=expected_result
    )

    payload = ReceiveInventoryStockSchema(
        item_id=item.id,
        location_id=location_id,
        quantity=Decimal("5"),
        unit_cost=Decimal("4"),
        currency="NGN",
        reference_type="purchase_order",
        reference_id="PO-1001",
    )

    result = service.receive_stock(
        organization_id=organization_id,
        payload=payload,
        actor_user_id=actor_user_id,
    )

    assert result is expected_result
    assert balance.quantity_on_hand == Decimal("15.000")
    assert balance.quantity_reserved == Decimal("1.000")
    assert balance.average_unit_cost == Decimal("2.6667")

    movement = service.inventory.create_movement.call_args.args[0]
    assert movement.movement_type == "receipt"
    assert movement.quantity_delta == Decimal("5.000")
    assert movement.quantity_before == Decimal("10.000")
    assert movement.quantity_after == Decimal("15.000")
    assert movement.created_by_user_id == actor_user_id
    assert movement.details["operation"] == "receive_stock"

    service.inventory.update_balance.assert_called_once_with(balance)
    service.db.commit.assert_called_once_with()


def test_opening_balance_is_rejected_after_prior_movement(
    service: InventoryService,
) -> None:
    organization_id = uuid.uuid4()
    location_id = uuid.uuid4()
    item = make_item(organization_id)
    balance = BalanceStub(
        organization_id=organization_id,
        item_id=item.id,
        location_id=location_id,
        quantity_on_hand=Decimal("0"),
        quantity_reserved=Decimal("0"),
        average_unit_cost=Decimal("0"),
    )

    service._get_item_or_404 = MagicMock(return_value=item)
    service._get_location_or_404 = MagicMock(return_value=object())
    service._get_balance_for_update = MagicMock(
        return_value=balance
    )
    service.inventory.count_movements_for_organization.return_value = 1

    payload = ReceiveInventoryStockSchema(
        item_id=item.id,
        location_id=location_id,
        quantity=Decimal("5"),
        movement_type="opening_balance",
    )

    with pytest.raises(HTTPException) as exc_info:
        service.receive_stock(
            organization_id=organization_id,
            payload=payload,
            actor_user_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 409
    service.inventory.update_balance.assert_not_called()
    service.inventory.create_movement.assert_not_called()
    service.db.commit.assert_not_called()


def test_issue_stock_cannot_consume_reserved_quantity(
    service: InventoryService,
) -> None:
    organization_id = uuid.uuid4()
    location_id = uuid.uuid4()
    item = make_item(organization_id)
    balance = BalanceStub(
        organization_id=organization_id,
        item_id=item.id,
        location_id=location_id,
        quantity_on_hand=Decimal("10"),
        quantity_reserved=Decimal("8"),
        average_unit_cost=Decimal("2"),
    )

    service._get_item_or_404 = MagicMock(return_value=item)
    service._get_location_or_404 = MagicMock(return_value=object())
    service._get_balance_for_update = MagicMock(
        return_value=balance
    )

    payload = IssueInventoryStockSchema(
        item_id=item.id,
        location_id=location_id,
        quantity=Decimal("3"),
    )

    with pytest.raises(HTTPException) as exc_info:
        service.issue_stock(
            organization_id=organization_id,
            payload=payload,
            actor_user_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 409
    assert "Reserved stock cannot be used" in exc_info.value.detail
    assert balance.quantity_on_hand == Decimal("10")
    service.inventory.update_balance.assert_not_called()
    service.db.commit.assert_not_called()


def test_issue_stock_reduces_on_hand_but_preserves_reservation(
    service: InventoryService,
) -> None:
    organization_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    location_id = uuid.uuid4()
    item = make_item(organization_id)
    balance = BalanceStub(
        organization_id=organization_id,
        item_id=item.id,
        location_id=location_id,
        quantity_on_hand=Decimal("10"),
        quantity_reserved=Decimal("2"),
        average_unit_cost=Decimal("3.2500"),
    )
    expected_result = object()

    service._get_item_or_404 = MagicMock(return_value=item)
    service._get_location_or_404 = MagicMock(return_value=object())
    service._get_balance_for_update = MagicMock(
        return_value=balance
    )
    service.inventory.create_movement.side_effect = attach_persisted_id
    service._reload_operation_result = MagicMock(
        return_value=expected_result
    )

    result = service.issue_stock(
        organization_id=organization_id,
        payload=IssueInventoryStockSchema(
            item_id=item.id,
            location_id=location_id,
            quantity=Decimal("3"),
        ),
        actor_user_id=actor_user_id,
    )

    assert result is expected_result
    assert balance.quantity_on_hand == Decimal("7.000")
    assert balance.quantity_reserved == Decimal("2")

    movement = service.inventory.create_movement.call_args.args[0]
    assert movement.movement_type == "issue"
    assert movement.quantity_delta == Decimal("-3.000")
    assert movement.quantity_after == Decimal("7.000")
    service.db.commit.assert_called_once_with()


def test_negative_adjustment_cannot_reduce_available_stock_below_zero(
    service: InventoryService,
) -> None:
    organization_id = uuid.uuid4()
    location_id = uuid.uuid4()
    item = make_item(organization_id)
    balance = BalanceStub(
        organization_id=organization_id,
        item_id=item.id,
        location_id=location_id,
        quantity_on_hand=Decimal("5"),
        quantity_reserved=Decimal("4"),
        average_unit_cost=Decimal("1"),
    )

    service._get_item_or_404 = MagicMock(return_value=item)
    service._get_location_or_404 = MagicMock(return_value=object())
    service._get_balance_for_update = MagicMock(
        return_value=balance
    )

    with pytest.raises(HTTPException) as exc_info:
        service.adjust_stock(
            organization_id=organization_id,
            payload=AdjustInventoryStockSchema(
                item_id=item.id,
                location_id=location_id,
                quantity_delta=Decimal("-2"),
            ),
            actor_user_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 409
    assert balance.quantity_on_hand == Decimal("5")
    service.db.commit.assert_not_called()


def test_transfer_rejects_same_source_and_destination(
    service: InventoryService,
) -> None:
    location_id = uuid.uuid4()

    with pytest.raises(HTTPException) as exc_info:
        service.transfer_stock(
            organization_id=uuid.uuid4(),
            payload=TransferInventoryStockSchema(
                item_id=uuid.uuid4(),
                source_location_id=location_id,
                destination_location_id=location_id,
                quantity=Decimal("1"),
            ),
            actor_user_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 422
    service.db.commit.assert_not_called()


def test_transfer_updates_both_balances_and_creates_paired_movements(
    service: InventoryService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    source_location_id = uuid.uuid4()
    destination_location_id = uuid.uuid4()
    item = make_item(organization_id)

    source_balance = BalanceStub(
        organization_id=organization_id,
        item_id=item.id,
        location_id=source_location_id,
        quantity_on_hand=Decimal("10"),
        quantity_reserved=Decimal("2"),
        average_unit_cost=Decimal("4"),
    )
    destination_balance = BalanceStub(
        organization_id=organization_id,
        item_id=item.id,
        location_id=destination_location_id,
        quantity_on_hand=Decimal("5"),
        quantity_reserved=Decimal("0"),
        average_unit_cost=Decimal("2"),
    )

    service._get_item_or_404 = MagicMock(return_value=item)
    service._get_location_or_404 = MagicMock(return_value=object())

    balances = {
        source_location_id: source_balance,
        destination_location_id: destination_balance,
    }
    service._get_balance_for_update = MagicMock(
        side_effect=lambda **kwargs: balances[kwargs["location_id"]]
    )

    def create_movements(movements: list[object]) -> list[object]:
        for movement in movements:
            attach_persisted_id(movement)
        return movements

    service.inventory.create_movements.side_effect = create_movements
    service._get_movement_or_404 = MagicMock(
        side_effect=lambda **kwargs: kwargs["movement_id"]
    )
    service._get_balance_or_404 = MagicMock(
        side_effect=lambda **kwargs: (
            source_balance
            if kwargs["balance_id"] == source_balance.id
            else destination_balance
        )
    )

    monkeypatch.setattr(
        inventory_service_module,
        "InventoryTransferResponse",
        lambda **kwargs: kwargs,
    )

    result = service.transfer_stock(
        organization_id=organization_id,
        payload=TransferInventoryStockSchema(
            item_id=item.id,
            source_location_id=source_location_id,
            destination_location_id=destination_location_id,
            quantity=Decimal("4"),
        ),
        actor_user_id=actor_user_id,
    )

    assert source_balance.quantity_on_hand == Decimal("6.000")
    assert destination_balance.quantity_on_hand == Decimal("9.000")
    assert destination_balance.average_unit_cost == Decimal("2.8889")

    movements = service.inventory.create_movements.call_args.args[0]
    assert len(movements) == 2
    assert {movement.movement_type for movement in movements} == {
        "transfer_in",
        "transfer_out",
    }
    assert movements[0].transfer_group_id == movements[1].transfer_group_id
    assert result["transfer_group_id"] == movements[0].transfer_group_id
    assert service.inventory.update_balance.call_count == 2
    service.db.commit.assert_called_once_with()


def test_create_reservation_rejects_quantity_above_available(
    service: InventoryService,
) -> None:
    organization_id = uuid.uuid4()
    location_id = uuid.uuid4()
    item = make_item(organization_id)
    balance = BalanceStub(
        organization_id=organization_id,
        item_id=item.id,
        location_id=location_id,
        quantity_on_hand=Decimal("10"),
        quantity_reserved=Decimal("8"),
        average_unit_cost=Decimal("1"),
    )

    service._get_item_or_404 = MagicMock(return_value=item)
    service._get_location_or_404 = MagicMock(return_value=object())
    service._get_work_order_or_404 = MagicMock(return_value=object())
    service._get_balance_for_update = MagicMock(
        return_value=balance
    )

    with pytest.raises(HTTPException) as exc_info:
        service.create_reservation(
            organization_id=organization_id,
            payload=CreateInventoryReservationSchema(
                item_id=item.id,
                location_id=location_id,
                work_order_id=uuid.uuid4(),
                quantity=Decimal("3"),
            ),
            actor_user_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 409
    assert balance.quantity_reserved == Decimal("8")
    service.inventory.create_reservation.assert_not_called()
    service.db.commit.assert_not_called()


def test_create_reservation_increases_reserved_quantity(
    service: InventoryService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    location_id = uuid.uuid4()
    work_order_id = uuid.uuid4()
    item = make_item(organization_id)
    balance = BalanceStub(
        organization_id=organization_id,
        item_id=item.id,
        location_id=location_id,
        quantity_on_hand=Decimal("10"),
        quantity_reserved=Decimal("2"),
        average_unit_cost=Decimal("1"),
    )

    service._get_item_or_404 = MagicMock(return_value=item)
    service._get_location_or_404 = MagicMock(return_value=object())
    service._get_work_order_or_404 = MagicMock(return_value=object())
    service._get_balance_for_update = MagicMock(
        return_value=balance
    )
    service.inventory.create_reservation.side_effect = attach_persisted_id
    service._get_reservation_or_404 = MagicMock(
        side_effect=lambda **kwargs: kwargs["reservation_id"]
    )
    service._get_balance_or_404 = MagicMock(return_value=balance)

    monkeypatch.setattr(
        inventory_service_module,
        "InventoryReservationOperationResponse",
        lambda **kwargs: kwargs,
    )

    result = service.create_reservation(
        organization_id=organization_id,
        payload=CreateInventoryReservationSchema(
            item_id=item.id,
            location_id=location_id,
            work_order_id=work_order_id,
            quantity=Decimal("3"),
        ),
        actor_user_id=actor_user_id,
    )

    assert balance.quantity_reserved == Decimal("5.000")
    reservation = service.inventory.create_reservation.call_args.args[0]
    assert reservation.quantity_reserved == Decimal("3.000")
    assert reservation.quantity_consumed == Decimal("0")
    assert reservation.status == "active"
    assert reservation.created_by_user_id == actor_user_id
    assert result["balance"] is balance
    service.db.commit.assert_called_once_with()


def test_expired_reservation_cannot_be_consumed(
    service: InventoryService,
) -> None:
    organization_id = uuid.uuid4()
    reservation = ReservationStub(
        organization_id=organization_id,
        item_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        work_order_id=uuid.uuid4(),
        quantity_reserved=Decimal("5"),
        quantity_consumed=Decimal("0"),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    service._get_reservation_or_404 = MagicMock(
        return_value=reservation
    )

    with pytest.raises(HTTPException) as exc_info:
        service.consume_reservation(
            organization_id=organization_id,
            reservation_id=reservation.id,
            payload=ConsumeInventoryReservationSchema(
                quantity=Decimal("1")
            ),
            actor_user_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 409
    assert "expired" in exc_info.value.detail.lower()
    service.db.commit.assert_not_called()


def test_database_error_rolls_back_transaction(
    service: InventoryService,
) -> None:
    organization_id = uuid.uuid4()
    location_id = uuid.uuid4()
    item = make_item(organization_id)
    balance = BalanceStub(
        organization_id=organization_id,
        item_id=item.id,
        location_id=location_id,
        quantity_on_hand=Decimal("1"),
        quantity_reserved=Decimal("0"),
        average_unit_cost=Decimal("1"),
    )

    service._get_item_or_404 = MagicMock(return_value=item)
    service._get_location_or_404 = MagicMock(return_value=object())
    service._get_balance_for_update = MagicMock(
        return_value=balance
    )
    service.inventory.update_balance.side_effect = SQLAlchemyError(
        "database unavailable"
    )

    with pytest.raises(SQLAlchemyError):
        service.receive_stock(
            organization_id=organization_id,
            payload=ReceiveInventoryStockSchema(
                item_id=item.id,
                location_id=location_id,
                quantity=Decimal("1"),
            ),
            actor_user_id=uuid.uuid4(),
        )

    service.db.rollback.assert_called_once_with()
    service.db.commit.assert_not_called()
