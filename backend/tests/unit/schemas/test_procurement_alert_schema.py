"""Schema tests for procurement workflow alerts."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.procurement_alert import (
    ProcurementAlertDispatchRequest,
    ProcurementAlertPreferenceUpdate,
)


def test_preference_update_accepts_one_field() -> None:
    payload = ProcurementAlertPreferenceUpdate(
        delivery_lead_days=5
    )
    assert payload.delivery_lead_days == 5


def test_preference_update_requires_one_field() -> None:
    with pytest.raises(ValidationError):
        ProcurementAlertPreferenceUpdate()


def test_delivery_lead_days_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        ProcurementAlertPreferenceUpdate(
            delivery_lead_days=-1
        )


def test_payment_lead_days_rejects_more_than_thirty() -> None:
    with pytest.raises(ValidationError):
        ProcurementAlertPreferenceUpdate(
            payment_lead_days=31
        )


def test_dispatch_request_accepts_business_date() -> None:
    payload = ProcurementAlertDispatchRequest(
        as_of_date=date(2026, 7, 27)
    )
    assert payload.as_of_date == date(2026, 7, 27)
