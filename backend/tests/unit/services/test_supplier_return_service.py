"""Pure helper tests for supplier return and debit-note service."""

from decimal import Decimal

from app.services.supplier_return_service import SupplierReturnService


def test_quantity_quantizes_to_three_places() -> None:
    assert SupplierReturnService._quantity(
        Decimal("1.23456")
    ) == Decimal("1.235")


def test_cost_quantizes_to_four_places() -> None:
    assert SupplierReturnService._cost(
        Decimal("10.55555")
    ) == Decimal("10.5556")


def test_money_quantizes_to_two_places() -> None:
    assert SupplierReturnService._money(
        Decimal("10.555")
    ) == Decimal("10.56")


def test_rate_quantizes_to_four_places() -> None:
    assert SupplierReturnService._rate(
        Decimal("7.12345")
    ) == Decimal("7.1235")


def test_generated_return_number_has_prefix() -> None:
    assert SupplierReturnService._generated_return_number().startswith(
        "SR-"
    )


def test_generated_debit_note_number_has_prefix() -> None:
    assert (
        SupplierReturnService._generated_debit_note_number()
        .startswith("DN-")
    )


def test_generated_credit_payment_number_has_prefix() -> None:
    assert (
        SupplierReturnService._generated_credit_payment_number()
        .startswith("CR-")
    )
