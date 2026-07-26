"""PostgreSQL concurrency and atomicity tests for Inventory."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.models.inventory import (
    InventoryBalance,
    InventoryMovement,
    InventoryReservation,
)
from app.schemas.inventory import (
    CreateInventoryReservationSchema,
    IssueInventoryStockSchema,
    ReceiveInventoryStockSchema,
    TransferInventoryStockSchema,
)
from app.services.inventory_service import InventoryService
from tests.integration.conftest import InventoryIntegrationData


pytestmark = pytest.mark.integration


def _receive(
    session_factory: sessionmaker[Session],
    data: InventoryIntegrationData,
    *,
    quantity: str,
    location_id: Any | None = None,
    reference_id: str | None = None,
) -> None:
    """Receive stock using an independent committed session."""

    with session_factory() as db:
        InventoryService(db).receive_stock(
            organization_id=data.organization_id,
            payload=ReceiveInventoryStockSchema(
                item_id=data.item_id,
                location_id=(
                    location_id
                    if location_id is not None
                    else data.source_location_id
                ),
                quantity=Decimal(quantity),
                unit_cost=Decimal("2500.0000"),
                currency="NGN",
                reference_type="integration_test",
                reference_id=reference_id,
            ),
            actor_user_id=data.actor_user_id,
        )


def _balance(
    db: Session,
    data: InventoryIntegrationData,
    location_id: Any,
) -> InventoryBalance | None:
    """Return one tenant-scoped item-location balance."""

    return (
        db.query(InventoryBalance)
        .filter(
            InventoryBalance.organization_id
            == data.organization_id,
            InventoryBalance.item_id == data.item_id,
            InventoryBalance.location_id == location_id,
        )
        .one_or_none()
    )


def test_concurrent_first_receipts_create_one_balance(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: InventoryIntegrationData,
) -> None:
    """Concurrent first receipts must not create duplicate balances."""

    barrier = threading.Barrier(2)

    def worker(reference_id: str) -> None:
        barrier.wait(timeout=10)
        _receive(
            integration_session_factory,
            inventory_integration_data,
            quantity="10.000",
            reference_id=reference_id,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(worker, "first-receipt-a"),
            executor.submit(worker, "first-receipt-b"),
        ]

        for future in futures:
            future.result(timeout=30)

    with integration_session_factory() as db:
        balances = (
            db.query(InventoryBalance)
            .filter(
                InventoryBalance.organization_id
                == inventory_integration_data.organization_id,
                InventoryBalance.item_id
                == inventory_integration_data.item_id,
                InventoryBalance.location_id
                == inventory_integration_data.source_location_id,
            )
            .all()
        )

        assert len(balances) == 1
        assert balances[0].quantity_on_hand == Decimal("20.000")

        movement_count = (
            db.query(func.count(InventoryMovement.id))
            .filter(
                InventoryMovement.organization_id
                == inventory_integration_data.organization_id,
                InventoryMovement.item_id
                == inventory_integration_data.item_id,
                InventoryMovement.location_id
                == inventory_integration_data.source_location_id,
                InventoryMovement.movement_type == "receipt",
            )
            .scalar()
        )

        assert movement_count == 2


def test_concurrent_issues_cannot_overdraw_stock(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: InventoryIntegrationData,
) -> None:
    """Row locking must allow only one competing oversized issue."""

    _receive(
        integration_session_factory,
        inventory_integration_data,
        quantity="50.000",
    )

    barrier = threading.Barrier(2)

    def worker(reference_id: str) -> tuple[str, int | None]:
        with integration_session_factory() as db:
            barrier.wait(timeout=10)

            try:
                InventoryService(db).issue_stock(
                    organization_id=(
                        inventory_integration_data.organization_id
                    ),
                    payload=IssueInventoryStockSchema(
                        item_id=inventory_integration_data.item_id,
                        location_id=(
                            inventory_integration_data
                            .source_location_id
                        ),
                        quantity=Decimal("40.000"),
                        reference_type="integration_test",
                        reference_id=reference_id,
                    ),
                    actor_user_id=(
                        inventory_integration_data.actor_user_id
                    ),
                )

                return "success", None

            except HTTPException as exc:
                db.rollback()
                return "error", exc.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [
            future.result(timeout=30)
            for future in (
                executor.submit(worker, "issue-a"),
                executor.submit(worker, "issue-b"),
            )
        ]

    assert sorted(results) == [
        ("error", 409),
        ("success", None),
    ]

    with integration_session_factory() as db:
        balance = _balance(
            db,
            inventory_integration_data,
            inventory_integration_data.source_location_id,
        )

        assert balance is not None
        assert balance.quantity_on_hand == Decimal("10.000")
        assert balance.quantity_reserved == Decimal("0.000")

        issue_count = (
            db.query(func.count(InventoryMovement.id))
            .filter(
                InventoryMovement.organization_id
                == inventory_integration_data.organization_id,
                InventoryMovement.movement_type == "issue",
            )
            .scalar()
        )

        assert issue_count == 1


def test_concurrent_reservations_cannot_exceed_available_stock(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: InventoryIntegrationData,
) -> None:
    """Competing reservations must serialize on the balance row."""

    _receive(
        integration_session_factory,
        inventory_integration_data,
        quantity="50.000",
    )

    barrier = threading.Barrier(2)

    def worker(work_order_id: Any) -> tuple[str, int | None]:
        with integration_session_factory() as db:
            barrier.wait(timeout=10)

            try:
                InventoryService(db).create_reservation(
                    organization_id=(
                        inventory_integration_data.organization_id
                    ),
                    payload=CreateInventoryReservationSchema(
                        item_id=inventory_integration_data.item_id,
                        location_id=(
                            inventory_integration_data
                            .source_location_id
                        ),
                        work_order_id=work_order_id,
                        quantity=Decimal("40.000"),
                    ),
                    actor_user_id=(
                        inventory_integration_data.actor_user_id
                    ),
                )

                return "success", None

            except HTTPException as exc:
                db.rollback()
                return "error", exc.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [
            future.result(timeout=30)
            for future in (
                executor.submit(
                    worker,
                    inventory_integration_data.work_order_id,
                ),
                executor.submit(
                    worker,
                    inventory_integration_data.second_work_order_id,
                ),
            )
        ]

    assert sorted(results) == [
        ("error", 409),
        ("success", None),
    ]

    with integration_session_factory() as db:
        balance = _balance(
            db,
            inventory_integration_data,
            inventory_integration_data.source_location_id,
        )

        assert balance is not None
        assert balance.quantity_on_hand == Decimal("50.000")
        assert balance.quantity_reserved == Decimal("40.000")

        reservations = (
            db.query(InventoryReservation)
            .filter(
                InventoryReservation.organization_id
                == inventory_integration_data.organization_id,
                InventoryReservation.status == "active",
            )
            .all()
        )

        assert len(reservations) == 1
        assert reservations[0].quantity_reserved == Decimal(
            "40.000"
        )


def test_transfer_rolls_back_balances_and_ledger_together(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: InventoryIntegrationData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A movement-ledger failure must roll back both balances."""

    _receive(
        integration_session_factory,
        inventory_integration_data,
        quantity="100.000",
    )

    with integration_session_factory() as db:
        service = InventoryService(db)

        def fail_create_movements(
            movements: list[InventoryMovement],
        ) -> list[InventoryMovement]:
            del movements
            raise SQLAlchemyError(
                "forced transfer-ledger failure"
            )

        monkeypatch.setattr(
            service.inventory,
            "create_movements",
            fail_create_movements,
        )

        with pytest.raises(SQLAlchemyError):
            service.transfer_stock(
                organization_id=(
                    inventory_integration_data.organization_id
                ),
                payload=TransferInventoryStockSchema(
                    item_id=inventory_integration_data.item_id,
                    source_location_id=(
                        inventory_integration_data.source_location_id
                    ),
                    destination_location_id=(
                        inventory_integration_data
                        .destination_location_id
                    ),
                    quantity=Decimal("30.000"),
                ),
                actor_user_id=(
                    inventory_integration_data.actor_user_id
                ),
            )

    with integration_session_factory() as db:
        source = _balance(
            db,
            inventory_integration_data,
            inventory_integration_data.source_location_id,
        )
        destination = _balance(
            db,
            inventory_integration_data,
            inventory_integration_data.destination_location_id,
        )

        assert source is not None
        assert source.quantity_on_hand == Decimal("100.000")
        assert destination is None

        transfer_count = (
            db.query(func.count(InventoryMovement.id))
            .filter(
                InventoryMovement.organization_id
                == inventory_integration_data.organization_id,
                InventoryMovement.movement_type.in_(
                    ["transfer_in", "transfer_out"]
                ),
            )
            .scalar()
        )

        assert transfer_count == 0


def test_competing_transfers_preserve_atomic_pairing(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: InventoryIntegrationData,
) -> None:
    """Only one competing transfer may consume limited source stock."""

    _receive(
        integration_session_factory,
        inventory_integration_data,
        quantity="100.000",
    )

    barrier = threading.Barrier(2)

    def worker(destination_id: Any) -> tuple[str, int | None]:
        with integration_session_factory() as db:
            barrier.wait(timeout=10)

            try:
                InventoryService(db).transfer_stock(
                    organization_id=(
                        inventory_integration_data.organization_id
                    ),
                    payload=TransferInventoryStockSchema(
                        item_id=inventory_integration_data.item_id,
                        source_location_id=(
                            inventory_integration_data
                            .source_location_id
                        ),
                        destination_location_id=destination_id,
                        quantity=Decimal("60.000"),
                    ),
                    actor_user_id=(
                        inventory_integration_data.actor_user_id
                    ),
                )

                return "success", None

            except HTTPException as exc:
                db.rollback()
                return "error", exc.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [
            future.result(timeout=30)
            for future in (
                executor.submit(
                    worker,
                    inventory_integration_data.destination_location_id,
                ),
                executor.submit(
                    worker,
                    inventory_integration_data.alternate_location_id,
                ),
            )
        ]

    assert sorted(results) == [
        ("error", 409),
        ("success", None),
    ]

    with integration_session_factory() as db:
        source = _balance(
            db,
            inventory_integration_data,
            inventory_integration_data.source_location_id,
        )
        destination = _balance(
            db,
            inventory_integration_data,
            inventory_integration_data.destination_location_id,
        )
        alternate = _balance(
            db,
            inventory_integration_data,
            inventory_integration_data.alternate_location_id,
        )

        assert source is not None
        assert source.quantity_on_hand == Decimal("40.000")

        destination_quantities = sorted(
            [
                (
                    destination.quantity_on_hand
                    if destination is not None
                    else Decimal("0.000")
                ),
                (
                    alternate.quantity_on_hand
                    if alternate is not None
                    else Decimal("0.000")
                ),
            ]
        )

        assert destination_quantities == [
            Decimal("0.000"),
            Decimal("60.000"),
        ]

        movements = (
            db.query(InventoryMovement)
            .filter(
                InventoryMovement.organization_id
                == inventory_integration_data.organization_id,
                InventoryMovement.movement_type.in_(
                    ["transfer_in", "transfer_out"]
                ),
            )
            .all()
        )

        assert len(movements) == 2
        assert len(
            {
                movement.transfer_group_id
                for movement in movements
            }
        ) == 1
        assert {
            movement.movement_type
            for movement in movements
        } == {"transfer_in", "transfer_out"}


def test_inventory_queries_and_mutations_are_tenant_isolated(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: InventoryIntegrationData,
) -> None:
    """One organization cannot read or mutate another's inventory."""

    with integration_session_factory() as db:
        result = InventoryService(db).receive_stock(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            payload=ReceiveInventoryStockSchema(
                item_id=inventory_integration_data.item_id,
                location_id=(
                    inventory_integration_data.source_location_id
                ),
                quantity=Decimal("10.000"),
                unit_cost=Decimal("2500.0000"),
                currency="NGN",
            ),
            actor_user_id=(
                inventory_integration_data.actor_user_id
            ),
        )

        movement_id = result.movement.id

    with integration_session_factory() as db:
        service = InventoryService(db)

        with pytest.raises(HTTPException) as read_error:
            service.get_movement(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                movement_id=movement_id,
            )

        assert read_error.value.status_code == 404

        other_movements = service.list_movements(
            organization_id=(
                inventory_integration_data.other_organization_id
            )
        )

        assert other_movements.total == 0

        with pytest.raises(HTTPException) as mutation_error:
            service.receive_stock(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                payload=ReceiveInventoryStockSchema(
                    item_id=inventory_integration_data.item_id,
                    location_id=(
                        inventory_integration_data
                        .source_location_id
                    ),
                    quantity=Decimal("1.000"),
                    unit_cost=Decimal("2500.0000"),
                    currency="NGN",
                ),
                actor_user_id=(
                    inventory_integration_data.actor_user_id
                ),
            )

        assert mutation_error.value.status_code == 404

    with integration_session_factory() as db:
        balance = _balance(
            db,
            inventory_integration_data,
            inventory_integration_data.source_location_id,
        )

        assert balance is not None
        assert balance.quantity_on_hand == Decimal("10.000")
