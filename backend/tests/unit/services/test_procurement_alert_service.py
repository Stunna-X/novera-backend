"""Pure service tests for procurement workflow alerts."""

from __future__ import annotations

import uuid
from datetime import date

from app.services.procurement_alert_service import (
    ProcurementAlertService,
)


def test_deduplication_key_is_stable() -> None:
    entity_id = uuid.uuid4()
    first = ProcurementAlertService.deduplication_key(
        alert_type="supplier_bill_overdue",
        entity_id=entity_id,
        alert_date=date(2026, 7, 27),
    )
    second = ProcurementAlertService.deduplication_key(
        alert_type="supplier_bill_overdue",
        entity_id=entity_id,
        alert_date=date(2026, 7, 27),
    )
    assert first == second


def test_deduplication_key_changes_with_date() -> None:
    entity_id = uuid.uuid4()
    first = ProcurementAlertService.deduplication_key(
        alert_type="supplier_bill_overdue",
        entity_id=entity_id,
        alert_date=date(2026, 7, 27),
    )
    second = ProcurementAlertService.deduplication_key(
        alert_type="supplier_bill_overdue",
        entity_id=entity_id,
        alert_date=date(2026, 7, 28),
    )
    assert first != second


def test_action_url_for_requisition() -> None:
    organization_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    assert ProcurementAlertService.action_url(
        organization_id,
        "purchase_requisition",
        entity_id,
    ) == (
        f"/organizations/{organization_id}/"
        f"purchase-requisitions/{entity_id}"
    )


def test_action_url_for_purchase_order() -> None:
    organization_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    assert ProcurementAlertService.action_url(
        organization_id,
        "purchase_order",
        entity_id,
    ).endswith(f"/purchase-orders/{entity_id}")


def test_action_url_for_supplier_bill() -> None:
    organization_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    assert ProcurementAlertService.action_url(
        organization_id,
        "supplier_bill",
        entity_id,
    ).endswith(f"/supplier-bills/{entity_id}")


def test_requisition_alert_requires_approval_permission() -> None:
    assert ProcurementAlertService.permission_allows(
        "requisition_approval_required",
        {"purchase_requisitions.approve"},
    )
    assert not ProcurementAlertService.permission_allows(
        "requisition_approval_required",
        {"purchase_requisitions.read"},
    )


def test_payment_action_requires_create_permission() -> None:
    assert ProcurementAlertService.permission_allows(
        "supplier_payment_action_required",
        {"supplier_payments.create"},
    )
    assert not ProcurementAlertService.permission_allows(
        "supplier_payment_action_required",
        {"supplier_payments.read"},
    )
