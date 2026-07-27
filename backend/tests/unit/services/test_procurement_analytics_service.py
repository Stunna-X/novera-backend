"""Unit tests for procurement analytics service calculations."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.schemas.procurement_analytics import ProcurementSettlementStatus
from app.services.procurement_analytics_service import (
    ProcurementAnalyticsService,
)


def test_normalize_date_range_defaults_to_thirty_days() -> None:
    date_from, date_to = ProcurementAnalyticsService.normalize_date_range(
        None,
        date(2026, 7, 27),
    )
    assert date_to == date(2026, 7, 27)
    assert date_from == date_to - timedelta(days=29)


def test_normalize_date_range_rejects_inverted_range() -> None:
    with pytest.raises(HTTPException) as exc_info:
        ProcurementAnalyticsService.normalize_date_range(
            date(2026, 7, 28),
            date(2026, 7, 27),
        )
    assert exc_info.value.status_code == 422


def test_normalize_date_range_rejects_more_than_one_year() -> None:
    with pytest.raises(HTTPException) as exc_info:
        ProcurementAnalyticsService.normalize_date_range(
            date(2025, 1, 1),
            date(2026, 7, 27),
        )
    assert exc_info.value.status_code == 422


def test_normalize_currency() -> None:
    assert ProcurementAnalyticsService.normalize_currency(" ngn ") == "NGN"
    assert ProcurementAnalyticsService.normalize_currency(None) is None


def test_normalize_currency_rejects_invalid_length() -> None:
    with pytest.raises(HTTPException) as exc_info:
        ProcurementAnalyticsService.normalize_currency("US")
    assert exc_info.value.status_code == 422


@pytest.mark.parametrize(
    ("total", "paid", "due", "as_of", "expected"),
    [
        (
            Decimal("100"),
            Decimal("100"),
            date(2026, 7, 1),
            date(2026, 7, 27),
            ProcurementSettlementStatus.PAID,
        ),
        (
            Decimal("100"),
            Decimal("25"),
            date(2026, 8, 1),
            date(2026, 7, 27),
            ProcurementSettlementStatus.PARTIALLY_PAID,
        ),
        (
            Decimal("100"),
            Decimal("0"),
            date(2026, 8, 1),
            date(2026, 7, 27),
            ProcurementSettlementStatus.UNPAID,
        ),
        (
            Decimal("100"),
            Decimal("25"),
            date(2026, 7, 1),
            date(2026, 7, 27),
            ProcurementSettlementStatus.OVERDUE,
        ),
    ],
)
def test_settlement_status(
    total: Decimal,
    paid: Decimal,
    due: date,
    as_of: date,
    expected: ProcurementSettlementStatus,
) -> None:
    assert (
        ProcurementAnalyticsService.settlement_status(
            total_amount=total,
            amount_paid=paid,
            due_date=due,
            as_of_date=as_of,
        )
        == expected
    )


def test_exception_rate() -> None:
    assert ProcurementAnalyticsService.exception_rate(
        rejected=Decimal("1"),
        damaged=Decimal("1"),
        total_delivered=Decimal("10"),
    ) == Decimal("20.0000")


def test_exception_rate_handles_zero_total() -> None:
    assert ProcurementAnalyticsService.exception_rate(
        rejected=Decimal("0"),
        damaged=Decimal("0"),
        total_delivered=Decimal("0"),
    ) == Decimal("0.0000")
