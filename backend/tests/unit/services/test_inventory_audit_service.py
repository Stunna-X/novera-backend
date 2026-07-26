"""Unit coverage for inventory audit integration."""

from __future__ import annotations

import inspect
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import app.api.v1.inventory.router as inventory_router
from app.schemas.inventory import (
    CreateInventoryLocationSchema,
    ReceiveInventoryStockSchema,
)
from app.services.inventory_service import InventoryService


pytestmark = pytest.mark.unit


INVENTORY_MUTATION_METHODS = (
    "create_location",
    "update_location",
    "deactivate_location",
    "reactivate_location",
    "create_item",
    "update_item",
    "deactivate_item",
    "reactivate_item",
    "receive_stock",
    "issue_stock",
    "return_stock",
    "adjust_stock",
    "transfer_stock",
    "create_reservation",
    "consume_reservation",
    "release_reservation",
)

INVENTORY_MUTATION_ROUTES = (
    inventory_router.create_inventory_location,
    inventory_router.update_inventory_location,
    inventory_router.deactivate_inventory_location,
    inventory_router.reactivate_inventory_location,
    inventory_router.create_inventory_item,
    inventory_router.update_inventory_item,
    inventory_router.deactivate_inventory_item,
    inventory_router.reactivate_inventory_item,
    inventory_router.receive_inventory_stock,
    inventory_router.issue_inventory_stock,
    inventory_router.return_inventory_stock,
    inventory_router.adjust_inventory_stock,
    inventory_router.transfer_inventory_stock,
    inventory_router.create_inventory_reservation,
    inventory_router.consume_inventory_reservation,
    inventory_router.release_inventory_reservation,
)


@dataclass
class BalanceStub:
    """Minimum balance contract required by receive-stock tests."""

    organization_id: uuid.UUID
    item_id: uuid.UUID
    location_id: uuid.UUID
    quantity_on_hand: Decimal
    quantity_reserved: Decimal
    average_unit_cost: Decimal
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    last_movement_at: object | None = None

    @property
    def available_quantity(self) -> Decimal:
        """Return unreserved stock."""

        return (
            Decimal(self.quantity_on_hand)
            - Decimal(self.quantity_reserved)
        )


@pytest.fixture
def service() -> InventoryService:
    """Build an inventory service with isolated collaborators."""

    db = MagicMock()
    instance = InventoryService(db)
    instance.inventory = MagicMock()
    instance.work_orders = MagicMock()
    instance.audit_logs = MagicMock()

    return instance


def _attach_id(model: object) -> object:
    """Simulate repository flush assigning a UUID."""

    if getattr(model, "id", None) is None:
        setattr(
            model,
            "id",
            uuid.uuid4(),
        )

    return model


def _make_item(
    organization_id: uuid.UUID,
) -> SimpleNamespace:
    """Build the item fields used by stock receipt logic."""

    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=organization_id,
        currency="NGN",
        default_unit_cost=Decimal("2.0000"),
        is_active=True,
    )


def test_every_inventory_mutation_records_an_audit_event() -> None:
    """Every service mutation must include the shared audit writer."""

    missing = [
        method_name
        for method_name in INVENTORY_MUTATION_METHODS
        if "_record_audit_event("
        not in inspect.getsource(
            getattr(
                InventoryService,
                method_name,
            )
        )
    ]

    assert missing == []


def test_every_inventory_mutation_route_propagates_membership() -> None:
    """API mutations must pass both authenticated actor identifiers."""

    missing = [
        route.__name__
        for route in INVENTORY_MUTATION_ROUTES
        if (
            "actor_user_id=context.current_user.id"
            not in inspect.getsource(route)
            or (
                "actor_membership_id="
                "context.membership.id"
            )
            not in inspect.getsource(route)
        )
    ]

    assert missing == []


def test_location_creation_records_actor_scoped_audit(
    service: InventoryService,
) -> None:
    """Catalogue creation must write an actor-scoped audit event."""

    organization_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    actor_membership_id = uuid.uuid4()

    service.inventory.location_code_exists.return_value = False
    service.inventory.create_location.side_effect = _attach_id

    created = service.create_location(
        organization_id=organization_id,
        payload=CreateInventoryLocationSchema(
            code="abu-main",
            name="Abuja Main Store",
            location_type="warehouse",
        ),
        actor_user_id=actor_user_id,
        actor_membership_id=actor_membership_id,
    )

    call = service.audit_logs.record_event.call_args

    assert call.kwargs["organization_id"] == organization_id
    assert call.kwargs["commit"] is False

    event = call.kwargs["payload"]

    assert event.actor_user_id == actor_user_id
    assert event.actor_membership_id == actor_membership_id
    assert event.action == "inventory_location_created"
    assert event.entity_type == "inventory_location"
    assert event.entity_id == created.id
    assert event.details == {
        "location_type": "warehouse",
    }

    service.db.commit.assert_called_once_with()


def test_stock_receipt_audit_excludes_sensitive_operation_values(
    service: InventoryService,
) -> None:
    """Stock audits must identify the operation without copying payload data."""

    organization_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    actor_membership_id = uuid.uuid4()
    location_id = uuid.uuid4()
    item = _make_item(organization_id)

    balance = BalanceStub(
        organization_id=organization_id,
        item_id=item.id,
        location_id=location_id,
        quantity_on_hand=Decimal("10.000"),
        quantity_reserved=Decimal("1.000"),
        average_unit_cost=Decimal("2.0000"),
    )

    service._get_item_or_404 = MagicMock(
        return_value=item
    )
    service._get_location_or_404 = MagicMock(
        return_value=object()
    )
    service._get_balance_for_update = MagicMock(
        return_value=balance
    )
    service.inventory.create_movement.side_effect = (
        _attach_id
    )
    service._reload_operation_result = MagicMock(
        return_value=object()
    )

    service.receive_stock(
        organization_id=organization_id,
        payload=ReceiveInventoryStockSchema(
            item_id=item.id,
            location_id=location_id,
            quantity=Decimal("5.000"),
            unit_cost=Decimal("4.0000"),
            currency="NGN",
            reference_type="purchase_order",
            reference_id="PO-SECRET-1001",
            notes="Supplier account information.",
            details={
                "supplier_bank_reference": "PRIVATE",
            },
        ),
        actor_user_id=actor_user_id,
        actor_membership_id=actor_membership_id,
    )

    event = (
        service.audit_logs.record_event
        .call_args.kwargs["payload"]
    )

    assert event.action == "inventory_stock_received"
    assert event.entity_type == "inventory_movement"
    assert event.actor_user_id == actor_user_id
    assert event.actor_membership_id == actor_membership_id
    assert event.details == {
        "item_id": str(item.id),
        "location_id": str(location_id),
        "movement_type": "receipt",
    }

    serialized = event.model_dump_json()

    for forbidden_value in (
        "5.000",
        "4.0000",
        "PO-SECRET-1001",
        "Supplier account information.",
        "PRIVATE",
    ):
        assert forbidden_value not in serialized


def test_audit_failure_rolls_back_inventory_transaction(
    service: InventoryService,
) -> None:
    """An audit failure must prevent the business mutation from committing."""

    service.inventory.location_code_exists.return_value = False
    service.inventory.create_location.side_effect = _attach_id
    service.audit_logs.record_event.side_effect = RuntimeError(
        "audit unavailable"
    )

    with pytest.raises(
        RuntimeError,
        match="audit unavailable",
    ):
        service.create_location(
            organization_id=uuid.uuid4(),
            payload=CreateInventoryLocationSchema(
                code="ROLLBACK",
                name="Rollback Store",
            ),
            actor_user_id=uuid.uuid4(),
            actor_membership_id=uuid.uuid4(),
        )

    service.db.rollback.assert_called_once_with()
    service.db.commit.assert_not_called()
