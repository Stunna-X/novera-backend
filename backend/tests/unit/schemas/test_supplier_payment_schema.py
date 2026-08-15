"""Unit tests for supplier-payment schemas."""

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.supplier_payment import (
    SupplierBillSettlementStatus,
    SupplierPaymentAllocationCreate,
    SupplierPaymentCreate,
    SupplierPaymentMethod,
    SupplierPaymentReverse,
    SupplierPaymentStatus,
)


def _allocation(
    *,
    bill_id: uuid.UUID | None = None,
    amount: str = "250.00",
) -> SupplierPaymentAllocationCreate:
    return SupplierPaymentAllocationCreate(
        supplier_bill_id=bill_id or uuid.uuid4(),
        amount_allocated=amount,
        notes="  First allocation  ",
    )


def test_create_normalizes_currency_and_text() -> None:
    payload = SupplierPaymentCreate(
        payment_number="  sp-001  ",
        supplier_id=uuid.uuid4(),
        currency="ngn",
        total_amount="250.00",
        reference_number="  ref-001  ",
        notes="  Settlement  ",
        allocations=[_allocation()],
    )

    assert payload.payment_number == "sp-001"
    assert payload.currency == "NGN"
    assert payload.reference_number == "ref-001"
    assert payload.notes == "Settlement"
    assert payload.allocations[0].notes == "First allocation"


def test_create_requires_allocation_total_to_equal_payment() -> None:
    with pytest.raises(ValidationError):
        SupplierPaymentCreate(
            supplier_id=uuid.uuid4(),
            total_amount="300.00",
            allocations=[_allocation(amount="250.00")],
        )


def test_create_rejects_duplicate_bill_allocations() -> None:
    bill_id = uuid.uuid4()

    with pytest.raises(ValidationError):
        SupplierPaymentCreate(
            supplier_id=uuid.uuid4(),
            total_amount="500.00",
            allocations=[
                _allocation(bill_id=bill_id),
                _allocation(bill_id=bill_id),
            ],
        )


def test_create_allows_multi_bill_payment() -> None:
    payload = SupplierPaymentCreate(
        supplier_id=uuid.uuid4(),
        total_amount="500.00",
        allocations=[
            _allocation(amount="200.00"),
            _allocation(amount="300.00"),
        ],
    )

    assert len(payload.allocations) == 2
    assert sum(
        item.amount_allocated
        for item in payload.allocations
    ) == Decimal("500.00")


def test_reversal_reason_is_trimmed() -> None:
    payload = SupplierPaymentReverse(
        reason="  Duplicate bank transfer  "
    )

    assert payload.reason == "Duplicate bank transfer"


def test_reversal_reason_rejects_blank_text() -> None:
    with pytest.raises(ValidationError):
        SupplierPaymentReverse(reason="   ")


def test_public_enum_values_are_stable() -> None:
    assert SupplierPaymentMethod.BANK_TRANSFER.value == "bank_transfer"
    assert SupplierPaymentStatus.REVERSED.value == "reversed"
    assert SupplierBillSettlementStatus.PARTIALLY_PAID.value == (
        "partially_paid"
    )
