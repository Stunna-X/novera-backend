"""
Invoice repository.

Contains organization-scoped persistence and reporting operations
for invoices, invoice line items, customer payments, and approved
billable work-order expenses.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, or_
from sqlalchemy.orm import (
    Session,
    joinedload,
    selectinload,
)

from app.enums.invoice import InvoiceStatus
from app.enums.work_order_expense import WorkOrderExpenseStatus
from app.models.invoice import (
    Invoice,
    InvoiceLineItem,
    InvoicePayment,
)
from app.models.work_order import WorkOrder
from app.models.work_order_expense import WorkOrderExpense
from app.repositories.base import BaseRepository


class InvoiceRepository(
    BaseRepository[Invoice]
):
    """
    Repository for organization-scoped invoice operations.

    Mutation methods flush instead of committing so the service
    can persist the invoice, related records, and activity event
    as one transaction.
    """

    def __init__(
        self,
        db: Session,
    ):
        super().__init__(
            db,
            Invoice,
        )

    @staticmethod
    def _invoice_options():
        """
        Return eager-loading options for invoice responses.
        """

        return (
            joinedload(
                Invoice.organization
            ),
            joinedload(
                Invoice.customer
            ),
            joinedload(
                Invoice.work_order
            ),
            joinedload(
                Invoice.created_by
            ),
            joinedload(
                Invoice.issued_by
            ),
            joinedload(
                Invoice.voided_by
            ),
            selectinload(
                Invoice.line_items
            ).joinedload(
                InvoiceLineItem.work_order_expense
            ),
            selectinload(
                Invoice.payments
            ).joinedload(
                InvoicePayment.recorded_by
            ),
            selectinload(
                Invoice.payments
            ).joinedload(
                InvoicePayment.reversed_by
            ),
        )

    def create_invoice(
        self,
        invoice: Invoice,
    ) -> Invoice:
        """
        Add a new invoice to the current transaction.
        """

        invoice.invoice_number = (
            invoice.invoice_number.strip().upper()
        )

        invoice.currency = (
            invoice.currency.strip().upper()
        )

        invoice.customer_name = (
            invoice.customer_name.strip()
        )

        self.db.add(
            invoice
        )

        self.db.flush()

        return invoice

    def get_for_organization(
        self,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> Invoice | None:
        """
        Retrieve one organization-scoped invoice.
        """

        query = (
            self.db.query(
                Invoice
            )
            .options(
                *self._invoice_options()
            )
            .populate_existing()
            .filter(
                Invoice.id == invoice_id,
                Invoice.organization_id
                == organization_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                Invoice.is_active.is_(True)
            )

        return query.first()

    def list_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        invoice_status: str | None = None,
        currency: str | None = None,
        customer_id: uuid.UUID | None = None,
        work_order_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        include_inactive: bool = False,
    ) -> list[Invoice]:
        """
        List invoices with optional organization filters.
        """

        query = (
            self.db.query(
                Invoice
            )
            .options(
                *self._invoice_options()
            )
            .populate_existing()
            .filter(
                Invoice.organization_id
                == organization_id
            )
        )

        if not include_inactive:
            query = query.filter(
                Invoice.is_active.is_(True)
            )

        if invoice_status:
            query = query.filter(
                Invoice.status
                == invoice_status
            )

        if currency:
            query = query.filter(
                Invoice.currency
                == currency
            )

        if customer_id:
            query = query.filter(
                Invoice.customer_id
                == customer_id
            )

        if work_order_id:
            query = query.filter(
                Invoice.work_order_id
                == work_order_id
            )

        if date_from:
            query = query.filter(
                Invoice.invoice_date
                >= date_from
            )

        if date_to:
            query = query.filter(
                Invoice.invoice_date
                <= date_to
            )

        normalized_search = (
            search.strip()
            if search
            else None
        )

        if normalized_search:
            pattern = (
                f"%{normalized_search}%"
            )

            query = query.filter(
                or_(
                    Invoice.invoice_number.ilike(
                        pattern
                    ),
                    Invoice.customer_name.ilike(
                        pattern
                    ),
                    Invoice.customer_email.ilike(
                        pattern
                    ),
                )
            )

        return (
            query.order_by(
                Invoice.invoice_date.desc(),
                Invoice.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None = None,
        invoice_status: str | None = None,
        currency: str | None = None,
        customer_id: uuid.UUID | None = None,
        work_order_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        include_inactive: bool = False,
    ) -> int:
        """
        Count invoices matching organization filters.
        """

        query = (
            self.db.query(
                func.count(
                    Invoice.id
                )
            )
            .filter(
                Invoice.organization_id
                == organization_id
            )
        )

        if not include_inactive:
            query = query.filter(
                Invoice.is_active.is_(True)
            )

        if invoice_status:
            query = query.filter(
                Invoice.status
                == invoice_status
            )

        if currency:
            query = query.filter(
                Invoice.currency
                == currency
            )

        if customer_id:
            query = query.filter(
                Invoice.customer_id
                == customer_id
            )

        if work_order_id:
            query = query.filter(
                Invoice.work_order_id
                == work_order_id
            )

        if date_from:
            query = query.filter(
                Invoice.invoice_date
                >= date_from
            )

        if date_to:
            query = query.filter(
                Invoice.invoice_date
                <= date_to
            )

        normalized_search = (
            search.strip()
            if search
            else None
        )

        if normalized_search:
            pattern = (
                f"%{normalized_search}%"
            )

            query = query.filter(
                or_(
                    Invoice.invoice_number.ilike(
                        pattern
                    ),
                    Invoice.customer_name.ilike(
                        pattern
                    ),
                    Invoice.customer_email.ilike(
                        pattern
                    ),
                )
            )

        return query.scalar() or 0

    def number_exists(
        self,
        organization_id: uuid.UUID,
        invoice_number: str,
    ) -> bool:
        """
        Check invoice-number uniqueness in an organization.
        """

        normalized_number = (
            invoice_number.strip().lower()
        )

        return (
            self.db.query(
                Invoice.id
            )
            .filter(
                Invoice.organization_id
                == organization_id,
                func.lower(
                    Invoice.invoice_number
                )
                == normalized_number,
            )
            .first()
            is not None
        )

    def update_invoice(
        self,
        invoice: Invoice,
    ) -> Invoice:
        """
        Flush invoice changes in the current transaction.
        """

        invoice.invoice_number = (
            invoice.invoice_number.strip().upper()
        )

        invoice.currency = (
            invoice.currency.strip().upper()
        )

        invoice.customer_name = (
            invoice.customer_name.strip()
        )

        self.db.add(
            invoice
        )

        self.db.flush()

        return invoice

    def add_line_item(
        self,
        line_item: InvoiceLineItem,
    ) -> InvoiceLineItem:
        """
        Add an invoice line item to the transaction.
        """

        line_item.description = (
            line_item.description.strip()
        )

        self.db.add(
            line_item
        )

        self.db.flush()

        return line_item

    def update_line_item(
        self,
        line_item: InvoiceLineItem,
    ) -> InvoiceLineItem:
        """
        Flush invoice line-item changes.
        """

        line_item.description = (
            line_item.description.strip()
        )

        self.db.add(
            line_item
        )

        self.db.flush()

        return line_item

    def get_line_item(
        self,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> InvoiceLineItem | None:
        """
        Retrieve one organization-scoped invoice line item.
        """

        query = (
            self.db.query(
                InvoiceLineItem
            )
            .join(
                Invoice,
                Invoice.id
                == InvoiceLineItem.invoice_id,
            )
            .options(
                joinedload(
                    InvoiceLineItem.work_order_expense
                )
            )
            .filter(
                Invoice.organization_id
                == organization_id,
                Invoice.id
                == invoice_id,
                InvoiceLineItem.id
                == line_item_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                InvoiceLineItem.is_active.is_(True)
            )

        return query.first()

    def get_line_item_by_expense(
        self,
        invoice_id: uuid.UUID,
        expense_id: uuid.UUID,
    ) -> InvoiceLineItem | None:
        """
        Find an existing active or inactive expense line.
        """

        return (
            self.db.query(
                InvoiceLineItem
            )
            .filter(
                InvoiceLineItem.invoice_id
                == invoice_id,
                InvoiceLineItem.work_order_expense_id
                == expense_id,
            )
            .first()
        )

    def next_line_position(
        self,
        invoice_id: uuid.UUID,
    ) -> int:
        """
        Return the next append position for an invoice.
        """

        maximum = (
            self.db.query(
                func.max(
                    InvoiceLineItem.position
                )
            )
            .filter(
                InvoiceLineItem.invoice_id
                == invoice_id
            )
            .scalar()
        )

        return (
            int(maximum) + 1
            if maximum is not None
            else 0
        )

    def line_position_exists(
        self,
        invoice_id: uuid.UUID,
        position: int,
        *,
        exclude_line_item_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Check whether an invoice position is occupied.
        """

        query = (
            self.db.query(
                InvoiceLineItem.id
            )
            .filter(
                InvoiceLineItem.invoice_id
                == invoice_id,
                InvoiceLineItem.position
                == position,
            )
        )

        if exclude_line_item_id is not None:
            query = query.filter(
                InvoiceLineItem.id
                != exclude_line_item_id
            )

        return query.first() is not None

    def expense_already_invoiced(
        self,
        organization_id: uuid.UUID,
        expense_id: uuid.UUID,
        *,
        exclude_invoice_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Check whether an expense appears on another invoice.

        Void invoices, inactive invoices, and inactive lines
        do not prevent an expense from being invoiced again.
        """

        query = (
            self.db.query(
                InvoiceLineItem.id
            )
            .join(
                Invoice,
                Invoice.id
                == InvoiceLineItem.invoice_id,
            )
            .filter(
                Invoice.organization_id
                == organization_id,
                InvoiceLineItem.work_order_expense_id
                == expense_id,
                InvoiceLineItem.is_active.is_(True),
                Invoice.is_active.is_(True),
                Invoice.status
                != InvoiceStatus.VOID.value,
            )
        )

        if exclude_invoice_id is not None:
            query = query.filter(
                Invoice.id
                != exclude_invoice_id
            )

        return query.first() is not None

    def get_billable_expense(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        expense_id: uuid.UUID,
        currency: str,
    ) -> WorkOrderExpense | None:
        """
        Return one expense eligible for invoicing.
        """

        return (
            self.db.query(
                WorkOrderExpense
            )
            .join(
                WorkOrder,
                WorkOrder.id
                == WorkOrderExpense.work_order_id,
            )
            .filter(
                WorkOrder.organization_id
                == organization_id,
                WorkOrder.id
                == work_order_id,
                WorkOrder.is_active.is_(True),
                WorkOrderExpense.id
                == expense_id,
                WorkOrderExpense.is_active.is_(True),
                WorkOrderExpense.is_billable.is_(True),
                WorkOrderExpense.status
                == WorkOrderExpenseStatus.APPROVED.value,
                WorkOrderExpense.currency
                == currency,
            )
            .first()
        )

    def add_payment(
        self,
        payment: InvoicePayment,
    ) -> InvoicePayment:
        """
        Add an invoice payment to the transaction.
        """

        self.db.add(
            payment
        )

        self.db.flush()

        return payment

    def update_payment(
        self,
        payment: InvoicePayment,
    ) -> InvoicePayment:
        """
        Flush invoice payment changes.
        """

        self.db.add(
            payment
        )

        self.db.flush()

        return payment

    def get_payment(
        self,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        payment_id: uuid.UUID,
    ) -> InvoicePayment | None:
        """
        Retrieve one organization-scoped invoice payment.
        """

        return (
            self.db.query(
                InvoicePayment
            )
            .join(
                Invoice,
                Invoice.id
                == InvoicePayment.invoice_id,
            )
            .options(
                joinedload(
                    InvoicePayment.recorded_by
                ),
                joinedload(
                    InvoicePayment.reversed_by
                ),
            )
            .filter(
                Invoice.organization_id
                == organization_id,
                Invoice.id
                == invoice_id,
                InvoicePayment.id
                == payment_id,
            )
            .first()
        )

    def active_payment_total(
        self,
        invoice_id: uuid.UUID,
    ) -> Decimal:
        """
        Return the total of all non-reversed payments.
        """

        value = (
            self.db.query(
                func.coalesce(
                    func.sum(
                        InvoicePayment.amount
                    ),
                    Decimal("0.00"),
                )
            )
            .filter(
                InvoicePayment.invoice_id
                == invoice_id,
                InvoicePayment.is_reversed.is_(False),
            )
            .scalar()
        )

        return Decimal(
            value or 0
        )

    def summary_by_currency(
        self,
        organization_id: uuid.UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        include_inactive: bool = False,
    ) -> list[tuple]:
        """
        Return invoice totals grouped by currency.

        Draft and void invoice values are excluded from financial
        totals but remain represented in their status counts.
        """

        billable_statuses = {
            InvoiceStatus.ISSUED.value,
            InvoiceStatus.PARTIALLY_PAID.value,
            InvoiceStatus.PAID.value,
        }

        outstanding_statuses = {
            InvoiceStatus.ISSUED.value,
            InvoiceStatus.PARTIALLY_PAID.value,
        }

        query = (
            self.db.query(
                Invoice.currency,
                func.count(
                    Invoice.id
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Invoice.status.in_(
                                    billable_statuses
                                ),
                                Invoice.total_amount,
                            ),
                            else_=Decimal("0.00"),
                        )
                    ),
                    Decimal("0.00"),
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Invoice.status.in_(
                                    billable_statuses
                                ),
                                Invoice.amount_paid,
                            ),
                            else_=Decimal("0.00"),
                        )
                    ),
                    Decimal("0.00"),
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Invoice.status.in_(
                                    outstanding_statuses
                                ),
                                Invoice.balance_due,
                            ),
                            else_=Decimal("0.00"),
                        )
                    ),
                    Decimal("0.00"),
                ),
                func.sum(
                    case(
                        (
                            Invoice.status
                            == InvoiceStatus.DRAFT.value,
                            1,
                        ),
                        else_=0,
                    )
                ),
                func.sum(
                    case(
                        (
                            Invoice.status
                            == InvoiceStatus.ISSUED.value,
                            1,
                        ),
                        else_=0,
                    )
                ),
                func.sum(
                    case(
                        (
                            Invoice.status
                            == (
                                InvoiceStatus
                                .PARTIALLY_PAID
                                .value
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                func.sum(
                    case(
                        (
                            Invoice.status
                            == InvoiceStatus.PAID.value,
                            1,
                        ),
                        else_=0,
                    )
                ),
                func.sum(
                    case(
                        (
                            Invoice.status
                            == InvoiceStatus.VOID.value,
                            1,
                        ),
                        else_=0,
                    )
                ),
            )
            .filter(
                Invoice.organization_id
                == organization_id
            )
        )

        if not include_inactive:
            query = query.filter(
                Invoice.is_active.is_(True)
            )

        if date_from:
            query = query.filter(
                Invoice.invoice_date
                >= date_from
            )

        if date_to:
            query = query.filter(
                Invoice.invoice_date
                <= date_to
            )

        return (
            query.group_by(
                Invoice.currency
            )
            .order_by(
                Invoice.currency.asc()
            )
            .all()
        )