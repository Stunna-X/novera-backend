"""SQLAlchemy metadata tests for procurement alert models."""

from __future__ import annotations

from app.models.procurement_alert import (
    ProcurementAlertDelivery,
    ProcurementAlertPreference,
)


def _constraint_names(model) -> set[str]:
    return {
        constraint.name
        for constraint in model.__table__.constraints
        if constraint.name is not None
    }


def _index_names(model) -> set[str]:
    return {
        index.name
        for index in model.__table__.indexes
    }


def test_procurement_alert_table_names() -> None:
    assert (
        ProcurementAlertPreference.__tablename__
        == "procurement_alert_preferences"
    )
    assert (
        ProcurementAlertDelivery.__tablename__
        == "procurement_alert_deliveries"
    )


def test_preference_has_organization_user_uniqueness() -> None:
    assert (
        "uq_procurement_alert_preferences_organization_user"
        in _constraint_names(ProcurementAlertPreference)
    )


def test_preference_has_lead_day_constraints() -> None:
    names = _constraint_names(ProcurementAlertPreference)
    assert any(
        name.endswith("delivery_lead_days_valid")
        for name in names
    )
    assert any(
        name.endswith("payment_lead_days_valid")
        for name in names
    )


def test_delivery_has_deduplication_uniqueness() -> None:
    assert (
        "uq_procurement_alert_deliveries_dedupe"
        in _constraint_names(ProcurementAlertDelivery)
    )


def test_delivery_has_type_and_status_constraints() -> None:
    names = _constraint_names(ProcurementAlertDelivery)
    assert any(
        name.endswith("alert_type_valid")
        for name in names
    )
    assert any(
        name.endswith("status_valid")
        for name in names
    )


def test_delivery_has_tenant_and_entity_indexes() -> None:
    names = _index_names(ProcurementAlertDelivery)
    assert (
        "ix_procurement_alert_deliveries_organization_recipient"
        in names
    )
    assert "ix_procurement_alert_deliveries_entity" in names
