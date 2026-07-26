"""
PostgreSQL tenant-isolation tests for financial resources.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Protocol

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.models.work_order import WorkOrder
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceIssueRequest,
    InvoiceLineItemCreate,
    InvoiceLineItemUpdate,
    InvoiceManualLineItemCreate,
    InvoicePaymentCreate,
    InvoicePaymentReverse,
    InvoiceUpdate,
)
from app.schemas.quote import (
    QuoteCreate,
    QuoteLineItemCreate,
    QuoteLineItemUpdate,
    QuoteUpdate,
)
from app.services.invoice_service import InvoiceService
from app.services.quote_service import QuoteService


class TenantIntegrationData(Protocol):
    """
    Minimum fixture contract required by these tests.
    """

    organization_id: uuid.UUID
    other_organization_id: uuid.UUID
    actor_user_id: uuid.UUID
    work_order_id: uuid.UUID


def _assert_not_found(
    error: pytest.ExceptionInfo[HTTPException],
) -> None:
    """
    Assert an information-leak-safe not-found response.
    """

    assert error.value.status_code == 404


def test_quote_resources_cannot_cross_organization_boundary(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: TenantIntegrationData,
) -> None:
    """
    Foreign organizations must not access quotes or line items.
    """

    token = uuid.uuid4().hex
    today = date.today()
    original_title = f"Borehole Proposal {token[:10]}"
    original_line_description = (
        f"Complete borehole drilling package {token[:10]}"
    )

    with integration_session_factory() as db:
        work_order = db.get(
            WorkOrder,
            inventory_integration_data.work_order_id,
        )

        assert work_order is not None

        quote = QuoteService(db).create_quote(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            payload=QuoteCreate(
                customer_id=work_order.customer_id,
                title=original_title,
                description=(
                    "Financial tenant-isolation regression quote."
                ),
                currency="NGN",
                quote_date=today,
                valid_until=today + timedelta(days=30),
                notes="Original quote notes.",
                line_items=[
                    QuoteLineItemCreate(
                        description=original_line_description,
                        quantity=Decimal("1.000"),
                        unit_price=Decimal("250000.00"),
                    ),
                ],
            ),
            actor_user_id=(
                inventory_integration_data.actor_user_id
            ),
        )

        quote_id = quote.id
        line_item_id = quote.line_items[0].id

    with integration_session_factory() as db:
        service = QuoteService(db)
        foreign_organization_id = (
            inventory_integration_data.other_organization_id
        )
        actor_user_id = (
            inventory_integration_data.actor_user_id
        )

        with pytest.raises(HTTPException) as read_error:
            service.get_quote(
                organization_id=foreign_organization_id,
                quote_id=quote_id,
            )

        _assert_not_found(read_error)

        foreign_quotes = service.list_quotes(
            organization_id=foreign_organization_id,
        )

        assert all(
            item.id != quote_id
            for item in foreign_quotes.items
        )

        with pytest.raises(
            HTTPException
        ) as activity_error:
            service.list_activities(
                organization_id=foreign_organization_id,
                quote_id=quote_id,
            )

        _assert_not_found(activity_error)

        with pytest.raises(HTTPException) as update_error:
            service.update_quote(
                organization_id=foreign_organization_id,
                quote_id=quote_id,
                payload=QuoteUpdate(
                    title="Cross-tenant quote overwrite",
                    notes="Unauthorized quote mutation.",
                ),
                actor_user_id=actor_user_id,
            )

        _assert_not_found(update_error)

        with pytest.raises(
            HTTPException
        ) as add_line_error:
            service.add_line_item(
                organization_id=foreign_organization_id,
                quote_id=quote_id,
                payload=QuoteLineItemCreate(
                    description="Unauthorized line item",
                    quantity=Decimal("1.000"),
                    unit_price=Decimal("1.00"),
                ),
                actor_user_id=actor_user_id,
            )

        _assert_not_found(add_line_error)

        with pytest.raises(
            HTTPException
        ) as update_line_error:
            service.update_line_item(
                organization_id=foreign_organization_id,
                quote_id=quote_id,
                line_item_id=line_item_id,
                payload=QuoteLineItemUpdate(
                    description=(
                        "Cross-tenant line-item overwrite"
                    ),
                    unit_price=Decimal("1.00"),
                ),
                actor_user_id=actor_user_id,
            )

        _assert_not_found(update_line_error)

        with pytest.raises(
            HTTPException
        ) as remove_line_error:
            service.remove_line_item(
                organization_id=foreign_organization_id,
                quote_id=quote_id,
                line_item_id=line_item_id,
                actor_user_id=actor_user_id,
            )

        _assert_not_found(remove_line_error)

        original_quote = service.get_quote(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            quote_id=quote_id,
        )

        assert original_quote.title == original_title
        assert len(original_quote.line_items) == 1
        assert (
            original_quote.line_items[0].description
            == original_line_description
        )
        assert (
            original_quote.line_items[0].unit_price
            == Decimal("250000.00")
        )
        assert original_quote.is_active is True


def test_invoice_resources_cannot_cross_organization_boundary(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: TenantIntegrationData,
) -> None:
    """
    Foreign organizations must not access invoices or payments.
    """

    token = uuid.uuid4().hex
    today = date.today()
    original_notes = (
        f"Financial isolation invoice {token[:10]}"
    )
    original_line_description = (
        f"Borehole mobilization fee {token[:10]}"
    )

    with integration_session_factory() as db:
        invoice = InvoiceService(db).create_invoice(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            work_order_id=(
                inventory_integration_data.work_order_id
            ),
            payload=InvoiceCreate(
                currency="NGN",
                invoice_date=today,
                due_date=today + timedelta(days=30),
                notes=original_notes,
                expense_ids=[],
                manual_line_items=[
                    InvoiceManualLineItemCreate(
                        description=original_line_description,
                        quantity=Decimal("1.000"),
                        unit_price=Decimal("120000.00"),
                    ),
                ],
            ),
            actor_user_id=(
                inventory_integration_data.actor_user_id
            ),
        )

        invoice_id = invoice.id
        line_item_id = invoice.line_items[0].id

    with integration_session_factory() as db:
        service = InvoiceService(db)
        foreign_organization_id = (
            inventory_integration_data.other_organization_id
        )
        primary_organization_id = (
            inventory_integration_data.organization_id
        )
        actor_user_id = (
            inventory_integration_data.actor_user_id
        )

        with pytest.raises(HTTPException) as read_error:
            service.get_invoice(
                organization_id=foreign_organization_id,
                invoice_id=invoice_id,
            )

        _assert_not_found(read_error)

        foreign_invoices = service.list_invoices(
            organization_id=foreign_organization_id,
        )

        assert all(
            item.id != invoice_id
            for item in foreign_invoices.items
        )

        with pytest.raises(HTTPException) as update_error:
            service.update_invoice(
                organization_id=foreign_organization_id,
                invoice_id=invoice_id,
                payload=InvoiceUpdate(
                    notes="Unauthorized invoice mutation.",
                ),
                actor_user_id=actor_user_id,
            )

        _assert_not_found(update_error)

        with pytest.raises(
            HTTPException
        ) as add_line_error:
            service.add_manual_line_item(
                organization_id=foreign_organization_id,
                invoice_id=invoice_id,
                payload=InvoiceLineItemCreate(
                    description="Unauthorized invoice line",
                    quantity=Decimal("1.000"),
                    unit_price=Decimal("1.00"),
                ),
                actor_user_id=actor_user_id,
            )

        _assert_not_found(add_line_error)

        with pytest.raises(
            HTTPException
        ) as update_line_error:
            service.update_line_item(
                organization_id=foreign_organization_id,
                invoice_id=invoice_id,
                line_item_id=line_item_id,
                payload=InvoiceLineItemUpdate(
                    description=(
                        "Cross-tenant invoice-line overwrite"
                    ),
                    unit_price=Decimal("1.00"),
                ),
                actor_user_id=actor_user_id,
            )

        _assert_not_found(update_line_error)

        with pytest.raises(
            HTTPException
        ) as remove_line_error:
            service.remove_line_item(
                organization_id=foreign_organization_id,
                invoice_id=invoice_id,
                line_item_id=line_item_id,
                actor_user_id=actor_user_id,
            )

        _assert_not_found(remove_line_error)

        with pytest.raises(HTTPException) as issue_error:
            service.issue_invoice(
                organization_id=foreign_organization_id,
                invoice_id=invoice_id,
                payload=InvoiceIssueRequest(
                    note="Unauthorized issue attempt.",
                ),
                actor_user_id=actor_user_id,
            )

        _assert_not_found(issue_error)

        with pytest.raises(
            HTTPException
        ) as payment_error:
            service.record_payment(
                organization_id=foreign_organization_id,
                invoice_id=invoice_id,
                payload=InvoicePaymentCreate(
                    amount=Decimal("1000.00"),
                    payment_date=today,
                    payment_method="bank_transfer",
                    reference_number=f"INVALID-{token[:10]}",
                ),
                actor_user_id=actor_user_id,
            )

        _assert_not_found(payment_error)

        unchanged_invoice = service.get_invoice(
            organization_id=primary_organization_id,
            invoice_id=invoice_id,
        )

        assert unchanged_invoice.notes == original_notes
        assert len(unchanged_invoice.line_items) == 1
        assert (
            unchanged_invoice.line_items[0].description
            == original_line_description
        )
        assert (
            unchanged_invoice.line_items[0].unit_price
            == Decimal("120000.00")
        )
        assert unchanged_invoice.amount_paid == Decimal("0.00")
        assert unchanged_invoice.is_active is True

        service.issue_invoice(
            organization_id=primary_organization_id,
            invoice_id=invoice_id,
            payload=InvoiceIssueRequest(
                note="Issued by the legitimate tenant.",
            ),
            actor_user_id=actor_user_id,
        )

        paid_invoice = service.record_payment(
            organization_id=primary_organization_id,
            invoice_id=invoice_id,
            payload=InvoicePaymentCreate(
                amount=Decimal("20000.00"),
                payment_date=today,
                payment_method="bank_transfer",
                reference_number=f"PAY-{token[:10]}",
                notes="Legitimate partial payment.",
            ),
            actor_user_id=actor_user_id,
        )

        payment_id = paid_invoice.payments[-1].id

        with pytest.raises(
            HTTPException
        ) as reverse_payment_error:
            service.reverse_payment(
                organization_id=foreign_organization_id,
                invoice_id=invoice_id,
                payment_id=payment_id,
                payload=InvoicePaymentReverse(
                    reason="Unauthorized reversal attempt.",
                ),
                actor_user_id=actor_user_id,
            )

        _assert_not_found(reverse_payment_error)

        final_invoice = service.get_invoice(
            organization_id=primary_organization_id,
            invoice_id=invoice_id,
        )

        matching_payments = [
            payment
            for payment in final_invoice.payments
            if payment.id == payment_id
        ]

        assert len(matching_payments) == 1
        assert matching_payments[0].is_reversed is False
        assert (
            final_invoice.amount_paid
            == Decimal("20000.00")
        )
