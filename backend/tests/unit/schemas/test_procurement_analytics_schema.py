"""Unit tests for procurement analytics response schemas."""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.procurement_analytics import (
    ProcurementCurrencyAmount,
    ProcurementDateRangeResponse,
    SupplierSpendItem,
)


def test_currency_amount_normalizes_currency() -> None:
    metric = ProcurementCurrencyAmount(
        currency="ngn",
        amount=Decimal("100.00"),
    )
    assert metric.currency == "NGN"


def test_currency_amount_rejects_negative_amount() -> None:
    with pytest.raises(ValidationError):
        ProcurementCurrencyAmount(
            currency="NGN",
            amount=Decimal("-0.01"),
        )


def test_date_range_rejects_inverted_dates() -> None:
    with pytest.raises(ValidationError):
        ProcurementDateRangeResponse(
            organization_id=uuid4(),
            generated_at=datetime.now(timezone.utc),
            date_from=date(2026, 7, 31),
            date_to=date(2026, 7, 1),
        )


def test_supplier_spend_accepts_zero_activity() -> None:
    item = SupplierSpendItem(
        supplier_id=uuid4(),
        supplier_code="SUP-001",
        supplier_name="Example Supplier",
        currency="usd",
        bill_count=0,
        payment_count=0,
        billed_amount=Decimal("0"),
        paid_amount=Decimal("0"),
        outstanding_amount=Decimal("0"),
    )
    assert item.currency == "USD"
