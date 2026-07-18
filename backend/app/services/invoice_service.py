"""
Invoice service.

Handles organization-scoped invoice creation, expense conversion,
manual line items, totals, issuing, payments, reversals, voiding,
reporting, and transactional work-order activity recording.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.enums.invoice import (
    InvoiceLineSource,
    InvoiceStatus,
)
from app.models.invoice import (
    Invoice,
    InvoiceLineItem,
    InvoicePayment,
)
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_closeout import WorkOrderCloseout
from app.repositories.customer import CustomerRepository
from app.repositories.invoice import InvoiceRepository
from app.repositories.work_order import WorkOrderRepository
from app.services.auto_notification_service import AutoNotificationService
from app.services.auto_audit_service import AutoAuditService
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceCurrencySummary,
    InvoiceExpenseLineCreate,
    InvoiceFromCloseoutCreate,
    InvoiceIssueRequest,
    InvoiceLineItemCreate,
    InvoiceLineItemResponse,
    InvoiceLineItemUpdate,
    InvoiceListResponse,
    InvoicePaymentCreate,
    InvoicePaymentResponse,
    InvoicePaymentReverse,
    InvoiceResponse,
    InvoiceSummaryResponse,
    InvoiceUpdate,
    InvoiceVoidRequest,
)


class InvoiceService:
    """
    Handles invoice and payment business logic.

    Every mutation is committed only after the invoice change,
    related records, and work-order activity entry have all been
    flushed successfully.
    """

    MONEY_QUANTIZER = Decimal("0.01")
    MAX_MONEY = Decimal("999999999999.99")

    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.invoices = InvoiceRepository(db)
        self.customers = CustomerRepository(db)
        self.work_orders = WorkOrderRepository(db)
        self.auto_notifications = AutoNotificationService(db)
        self.auto_audit = AutoAuditService(db)

    @staticmethod
    def _utc_now() -> datetime:
        """
        Return the current timezone-aware UTC timestamp.
        """

        return datetime.now(timezone.utc)

    @classmethod
    def _money(
        cls,
        value: Decimal | int | str,
    ) -> Decimal:
        """
        Normalize a monetary value to two decimal places.
        """

        normalized = Decimal(value).quantize(
            cls.MONEY_QUANTIZER,
            rounding=ROUND_HALF_UP,
        )

        if normalized < 0:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail="Monetary values cannot be negative.",
            )

        if normalized > cls.MAX_MONEY:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=(
                    "Monetary value exceeds the supported limit."
                ),
            )

        return normalized

    @classmethod
    def _calculate_line_total(
        cls,
        quantity: Decimal,
        unit_price: Decimal,
    ) -> Decimal:
        """
        Calculate and validate one invoice line total.
        """

        return cls._money(
            Decimal(quantity) * Decimal(unit_price)
        )

    @staticmethod
    def _build_billing_address(
        customer: Any,
    ) -> str | None:
        """
        Build a readable billing address from customer fields.
        """

        parts = [
            customer.address_line_1,
            customer.address_line_2,
            customer.city,
            customer.state,
            customer.postal_code,
            customer.country,
        ]

        normalized = [
            str(part).strip()
            for part in parts
            if part is not None and str(part).strip()
        ]

        return ", ".join(normalized) or None

    @staticmethod
    def _user_fields(
        user: Any | None,
    ) -> tuple[
        str | None,
        str | None,
        str | None,
    ]:
        """
        Return a user's response-safe identity fields.
        """

        if user is None:
            return None, None, None

        return (
            user.first_name,
            user.last_name,
            user.email,
        )

    @classmethod
    def _build_line_response(
        cls,
        line_item: InvoiceLineItem,
    ) -> InvoiceLineItemResponse:
        """
        Convert a line-item model into an API response.
        """

        return InvoiceLineItemResponse(
            id=line_item.id,
            invoice_id=line_item.invoice_id,
            work_order_expense_id=(
                line_item.work_order_expense_id
            ),
            source_type=line_item.source_type,
            description=line_item.description,
            quantity=line_item.quantity,
            unit_price=line_item.unit_price,
            line_total=line_item.line_total,
            position=line_item.position,
            is_active=line_item.is_active,
            created_at=line_item.created_at,
            updated_at=line_item.updated_at,
        )

    @classmethod
    def _build_payment_response(
        cls,
        payment: InvoicePayment,
    ) -> InvoicePaymentResponse:
        """
        Convert a payment model into an API response.
        """

        recorded_first, recorded_last, recorded_email = (
            cls._user_fields(payment.recorded_by)
        )
        reversed_first, reversed_last, reversed_email = (
            cls._user_fields(payment.reversed_by)
        )

        return InvoicePaymentResponse(
            id=payment.id,
            invoice_id=payment.invoice_id,
            recorded_by_user_id=(
                payment.recorded_by_user_id
            ),
            recorded_by_first_name=recorded_first,
            recorded_by_last_name=recorded_last,
            recorded_by_email=recorded_email,
            reversed_by_user_id=(
                payment.reversed_by_user_id
            ),
            reversed_by_first_name=reversed_first,
            reversed_by_last_name=reversed_last,
            reversed_by_email=reversed_email,
            amount=payment.amount,
            currency=payment.currency,
            payment_date=payment.payment_date,
            payment_method=payment.payment_method,
            reference_number=payment.reference_number,
            notes=payment.notes,
            is_reversed=payment.is_reversed,
            reversed_at=payment.reversed_at,
            reversal_reason=payment.reversal_reason,
            created_at=payment.created_at,
            updated_at=payment.updated_at,
        )

    @classmethod
    def _build_response(
        cls,
        invoice: Invoice,
    ) -> InvoiceResponse:
        """
        Convert an invoice model into a complete API response.
        """

        created_first, created_last, created_email = (
            cls._user_fields(invoice.created_by)
        )
        issued_first, issued_last, issued_email = (
            cls._user_fields(invoice.issued_by)
        )
        voided_first, voided_last, voided_email = (
            cls._user_fields(invoice.voided_by)
        )

        line_items = sorted(
            invoice.line_items,
            key=lambda item: (
                item.position,
                item.created_at,
            ),
        )

        payments = sorted(
            invoice.payments,
            key=lambda item: (
                item.payment_date,
                item.created_at,
            ),
        )

        return InvoiceResponse(
            id=invoice.id,
            organization_id=invoice.organization_id,
            customer_id=invoice.customer_id,
            work_order_id=invoice.work_order_id,
            created_by_user_id=invoice.created_by_user_id,
            created_by_first_name=created_first,
            created_by_last_name=created_last,
            created_by_email=created_email,
            issued_by_user_id=invoice.issued_by_user_id,
            issued_by_first_name=issued_first,
            issued_by_last_name=issued_last,
            issued_by_email=issued_email,
            voided_by_user_id=invoice.voided_by_user_id,
            voided_by_first_name=voided_first,
            voided_by_last_name=voided_last,
            voided_by_email=voided_email,
            invoice_number=invoice.invoice_number,
            currency=invoice.currency,
            status=invoice.status,
            invoice_date=invoice.invoice_date,
            due_date=invoice.due_date,
            subtotal=invoice.subtotal,
            discount_amount=invoice.discount_amount,
            tax_amount=invoice.tax_amount,
            total_amount=invoice.total_amount,
            amount_paid=invoice.amount_paid,
            balance_due=invoice.balance_due,
            customer_name=invoice.customer_name,
            customer_email=invoice.customer_email,
            customer_phone=invoice.customer_phone,
            billing_address=invoice.billing_address,
            notes=invoice.notes,
            terms=invoice.terms,
            issued_at=invoice.issued_at,
            paid_at=invoice.paid_at,
            voided_at=invoice.voided_at,
            void_reason=invoice.void_reason,
            is_active=invoice.is_active,
            line_items=[
                cls._build_line_response(item)
                for item in line_items
            ],
            payments=[
                cls._build_payment_response(payment)
                for payment in payments
            ],
            created_at=invoice.created_at,
            updated_at=invoice.updated_at,
        )

    def _record_activity(
        self,
        *,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        activity_type: str,
        summary: str,
        from_status: str | None = None,
        to_status: str | None = None,
        note: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> WorkOrderActivity:
        """
        Add an activity entry to the current transaction.
        """

        activity = WorkOrderActivity(
            organization_id=organization_id,
            work_order_id=work_order_id,
            actor_user_id=actor_user_id,
            activity_type=activity_type,
            summary=summary,
            from_status=from_status,
            to_status=to_status,
            note=note,
            details=details or {},
        )

        self.db.add(activity)
        self.db.flush()

        return activity

    def _get_invoice_or_404(
        self,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> Invoice:
        """
        Retrieve an organization-scoped invoice.
        """

        invoice = self.invoices.get_for_organization(
            organization_id=organization_id,
            invoice_id=invoice_id,
            include_inactive=include_inactive,
        )

        if invoice is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found.",
            )

        return invoice

    def _get_line_or_404(
        self,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> InvoiceLineItem:
        """
        Retrieve an organization-scoped invoice line item.
        """

        line_item = self.invoices.get_line_item(
            organization_id=organization_id,
            invoice_id=invoice_id,
            line_item_id=line_item_id,
            include_inactive=include_inactive,
        )

        if line_item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice line item not found.",
            )

        return line_item

    def _get_payment_or_404(
        self,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        payment_id: uuid.UUID,
    ) -> InvoicePayment:
        """
        Retrieve an organization-scoped invoice payment.
        """

        payment = self.invoices.get_payment(
            organization_id=organization_id,
            invoice_id=invoice_id,
            payment_id=payment_id,
        )

        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice payment not found.",
            )

        return payment

    @staticmethod
    def _ensure_draft(
        invoice: Invoice,
    ) -> None:
        """
        Require an invoice to remain in draft status.
        """

        if invoice.status != InvoiceStatus.DRAFT.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only draft invoices can be edited."
                ),
            )

    @staticmethod
    def _ensure_date_range_valid(
        date_from: date | None,
        date_to: date | None,
    ) -> None:
        """
        Reject an inverted date range.
        """

        if (
            date_from is not None
            and date_to is not None
            and date_from > date_to
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=(
                    "date_from cannot be later than date_to."
                ),
            )

    def _generate_invoice_number(
        self,
        organization_id: uuid.UUID,
        invoice_date: date,
    ) -> str:
        """
        Generate a unique organization invoice number.
        """

        for _ in range(20):
            candidate = (
                f"INV-{invoice_date:%Y%m%d}-"
                f"{uuid.uuid4().hex[:6].upper()}"
            )

            if not self.invoices.number_exists(
                organization_id=organization_id,
                invoice_number=candidate,
            ):
                return candidate

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A unique invoice number could not be generated."
            ),
        )

    def _active_line_count(
        self,
        invoice_id: uuid.UUID,
    ) -> int:
        """
        Count active invoice line items.
        """

        return (
            self.db.query(
                func.count(InvoiceLineItem.id)
            )
            .filter(
                InvoiceLineItem.invoice_id == invoice_id,
                InvoiceLineItem.is_active.is_(True),
            )
            .scalar()
            or 0
        )

    def _active_line_subtotal(
        self,
        invoice_id: uuid.UUID,
    ) -> Decimal:
        """
        Sum active invoice line totals.
        """

        value = (
            self.db.query(
                func.coalesce(
                    func.sum(InvoiceLineItem.line_total),
                    Decimal("0.00"),
                )
            )
            .filter(
                InvoiceLineItem.invoice_id == invoice_id,
                InvoiceLineItem.is_active.is_(True),
            )
            .scalar()
        )

        return self._money(value or Decimal("0.00"))

    def _resolve_position(
        self,
        invoice_id: uuid.UUID,
        requested_position: int | None,
        *,
        exclude_line_item_id: uuid.UUID | None = None,
    ) -> int:
        """
        Return a free invoice line position.
        """

        if requested_position is None:
            return self.invoices.next_line_position(
                invoice_id
            )

        if self.invoices.line_position_exists(
            invoice_id=invoice_id,
            position=requested_position,
            exclude_line_item_id=exclude_line_item_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The requested invoice line position "
                    "is already occupied."
                ),
            )

        return requested_position

    def _recalculate_invoice(
        self,
        invoice: Invoice,
    ) -> Invoice:
        """
        Recalculate totals and payment-derived invoice status.
        """

        subtotal = self._active_line_subtotal(
            invoice.id
        )
        discount = self._money(
            invoice.discount_amount
        )
        tax = self._money(
            invoice.tax_amount
        )

        if discount > subtotal:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=(
                    "Invoice discount cannot exceed "
                    "the subtotal."
                ),
            )

        total = self._money(
            subtotal - discount + tax
        )
        amount_paid = self._money(
            self.invoices.active_payment_total(
                invoice.id
            )
        )

        if amount_paid > total:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Active payments exceed the invoice total."
                ),
            )

        balance_due = self._money(
            total - amount_paid
        )

        invoice.subtotal = subtotal
        invoice.total_amount = total
        invoice.amount_paid = amount_paid
        invoice.balance_due = balance_due

        if invoice.status not in {
            InvoiceStatus.DRAFT.value,
            InvoiceStatus.VOID.value,
        }:
            if amount_paid == Decimal("0.00"):
                invoice.status = InvoiceStatus.ISSUED.value
                invoice.paid_at = None
            elif amount_paid < total:
                invoice.status = (
                    InvoiceStatus.PARTIALLY_PAID.value
                )
                invoice.paid_at = None
            else:
                invoice.status = InvoiceStatus.PAID.value

                if invoice.paid_at is None:
                    invoice.paid_at = self._utc_now()

        return self.invoices.update_invoice(
            invoice
        )

    def _reload_invoice(
        self,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> Invoice:
        """
        Reload a complete invoice after a transaction.
        """

        invoice = self.invoices.get_for_organization(
            organization_id=organization_id,
            invoice_id=invoice_id,
            include_inactive=include_inactive,
        )

        if invoice is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found after save.",
            )

        return invoice

    def create_invoice(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        payload: InvoiceCreate,
        *,
        actor_user_id: uuid.UUID,
    ) -> InvoiceResponse:
        """
        Create a draft invoice from expenses and manual lines.
        """

        work_order = self.work_orders.get_for_organization(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        if work_order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work order not found.",
            )

        customer = (
            self.customers.get_by_id_for_organization(
                organization_id=organization_id,
                customer_id=work_order.customer_id,
            )
        )

        if customer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work-order customer not found.",
            )

        currency = payload.currency.strip().upper()

        eligible_expenses = []

        for expense_id in payload.expense_ids:
            expense = self.invoices.get_billable_expense(
                organization_id=organization_id,
                work_order_id=work_order_id,
                expense_id=expense_id,
                currency=currency,
            )

            if expense is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "Every expense must be active, approved, "
                        "billable, belong to this work order, and "
                        "use the invoice currency."
                    ),
                )

            if self.invoices.expense_already_invoiced(
                organization_id=organization_id,
                expense_id=expense_id,
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Expense {expense_id} has already "
                        "been invoiced."
                    ),
                )

            eligible_expenses.append(expense)

        invoice_number = self._generate_invoice_number(
            organization_id=organization_id,
            invoice_date=payload.invoice_date,
        )

        invoice = Invoice(
            organization_id=organization_id,
            customer_id=customer.id,
            work_order_id=work_order.id,
            created_by_user_id=actor_user_id,
            invoice_number=invoice_number,
            currency=currency,
            status=InvoiceStatus.DRAFT.value,
            invoice_date=payload.invoice_date,
            due_date=payload.due_date,
            subtotal=Decimal("0.00"),
            discount_amount=self._money(
                payload.discount_amount
            ),
            tax_amount=self._money(
                payload.tax_amount
            ),
            total_amount=Decimal("0.00"),
            amount_paid=Decimal("0.00"),
            balance_due=Decimal("0.00"),
            customer_name=customer.name,
            customer_email=customer.email,
            customer_phone=customer.phone,
            billing_address=(
                payload.billing_address
                or self._build_billing_address(customer)
            ),
            notes=payload.notes,
            terms=payload.terms,
        )

        try:
            created = self.invoices.create_invoice(
                invoice
            )

            for expense in eligible_expenses:
                position = self.invoices.next_line_position(
                    created.id
                )

                self.invoices.add_line_item(
                    InvoiceLineItem(
                        invoice_id=created.id,
                        work_order_expense_id=expense.id,
                        source_type=(
                            InvoiceLineSource.EXPENSE.value
                        ),
                        description=expense.description,
                        quantity=expense.quantity,
                        unit_price=expense.unit_cost,
                        line_total=expense.total_amount,
                        position=position,
                        is_active=True,
                    )
                )

            for manual_line in payload.manual_line_items:
                position = self._resolve_position(
                    created.id,
                    manual_line.position,
                )

                line_total = self._calculate_line_total(
                    quantity=manual_line.quantity,
                    unit_price=manual_line.unit_price,
                )

                self.invoices.add_line_item(
                    InvoiceLineItem(
                        invoice_id=created.id,
                        work_order_expense_id=None,
                        source_type=(
                            InvoiceLineSource.MANUAL.value
                        ),
                        description=manual_line.description,
                        quantity=manual_line.quantity,
                        unit_price=manual_line.unit_price,
                        line_total=line_total,
                        position=position,
                        is_active=True,
                    )
                )

            created = self._recalculate_invoice(
                created
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                activity_type="invoice_created",
                summary=(
                    f"Invoice {created.invoice_number} created."
                ),
                to_status=InvoiceStatus.DRAFT.value,
                details={
                    "invoice_id": str(created.id),
                    "invoice_number": created.invoice_number,
                    "currency": created.currency,
                    "subtotal": str(created.subtotal),
                    "total_amount": str(
                        created.total_amount
                    ),
                    "expense_line_count": len(
                        eligible_expenses
                    ),
                    "manual_line_count": len(
                        payload.manual_line_items
                    ),
                },
            )

            self.auto_audit.invoice_created(

                organization_id=organization_id,

                invoice=created,

                actor_user_id=actor_user_id,

                source="work_order",

            )


            self.db.commit()

            loaded = self._reload_invoice(
                organization_id=organization_id,
                invoice_id=created.id,
            )

            return self._build_response(
                loaded
            )

        except HTTPException:
            self.db.rollback()
            raise

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The invoice conflicts with an existing "
                    "invoice or line item."
                ),
            ) from exc

        except Exception:
            self.db.rollback()
            raise


    def create_invoice_from_closeout(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        payload: InvoiceFromCloseoutCreate,
        *,
        actor_user_id: uuid.UUID,
    ) -> InvoiceResponse:
        work_order = self.work_orders.get_for_organization(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        if work_order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work order not found.",
            )

        if work_order.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only completed work orders can be invoiced "
                    "from closeout."
                ),
            )

        closeout = (
            self.db.query(WorkOrderCloseout)
            .filter(
                WorkOrderCloseout.organization_id
                == organization_id,
                WorkOrderCloseout.work_order_id
                == work_order_id,
            )
            .first()
        )

        if closeout is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work-order closeout not found.",
            )

        if (
            closeout.status != "approved"
            or not closeout.is_invoice_ready
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only approved, invoice-ready closeouts "
                    "can generate final invoices."
                ),
            )

        existing_invoice = (
            self.db.query(Invoice)
            .filter(
                Invoice.organization_id == organization_id,
                Invoice.work_order_id == work_order_id,
                Invoice.is_active.is_(True),
                Invoice.status != InvoiceStatus.VOID.value,
            )
            .first()
        )

        if existing_invoice is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This work order already has an active "
                    "non-void invoice."
                ),
            )

        customer = (
            self.customers.get_by_id_for_organization(
                organization_id=organization_id,
                customer_id=work_order.customer_id,
            )
        )

        if customer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work-order customer not found.",
            )

        currency = payload.currency.strip().upper()

        invoice_number = self._generate_invoice_number(
            organization_id=organization_id,
            invoice_date=payload.invoice_date,
        )

        invoice = Invoice(
            organization_id=organization_id,
            customer_id=customer.id,
            work_order_id=work_order.id,
            created_by_user_id=actor_user_id,
            invoice_number=invoice_number,
            currency=currency,
            status=InvoiceStatus.DRAFT.value,
            invoice_date=payload.invoice_date,
            due_date=payload.due_date,
            subtotal=Decimal("0.00"),
            discount_amount=self._money(
                payload.discount_amount
            ),
            tax_amount=self._money(
                payload.tax_amount
            ),
            total_amount=Decimal("0.00"),
            amount_paid=Decimal("0.00"),
            balance_due=Decimal("0.00"),
            customer_name=customer.name,
            customer_email=customer.email,
            customer_phone=customer.phone,
            billing_address=(
                payload.billing_address
                or self._build_billing_address(customer)
            ),
            notes=(
                payload.notes
                or (
                    "Final invoice generated from approved "
                    "work-order closeout."
                )
            ),
            terms=payload.terms,
        )

        try:
            created = self.invoices.create_invoice(
                invoice
            )

            generated_closeout_line_count = 0

            if payload.include_estimated_cost_line:
                estimated_cost = self._money(
                    work_order.estimated_cost
                    or Decimal("0.00")
                )

                if estimated_cost <= Decimal("0.00"):
                    raise HTTPException(
                        status_code=(
                            status.HTTP_422_UNPROCESSABLE_ENTITY
                        ),
                        detail=(
                            "Work order estimated_cost is required "
                            "when include_estimated_cost_line is true."
                        ),
                    )

                description = (
                    payload.closeout_line_description
                    or (
                        "Final invoice for "
                        f"{work_order.work_order_number}: "
                        f"{work_order.title}"
                    )
                )

                self.invoices.add_line_item(
                    InvoiceLineItem(
                        invoice_id=created.id,
                        work_order_expense_id=None,
                        source_type=(
                            InvoiceLineSource.MANUAL.value
                        ),
                        description=description,
                        quantity=Decimal("1.000"),
                        unit_price=estimated_cost,
                        line_total=estimated_cost,
                        position=self.invoices.next_line_position(
                            created.id
                        ),
                        is_active=True,
                    )
                )

                generated_closeout_line_count = 1

            for manual_line in payload.manual_line_items:
                position = self._resolve_position(
                    created.id,
                    manual_line.position,
                )

                line_total = self._calculate_line_total(
                    quantity=manual_line.quantity,
                    unit_price=manual_line.unit_price,
                )

                self.invoices.add_line_item(
                    InvoiceLineItem(
                        invoice_id=created.id,
                        work_order_expense_id=None,
                        source_type=(
                            InvoiceLineSource.MANUAL.value
                        ),
                        description=manual_line.description,
                        quantity=manual_line.quantity,
                        unit_price=manual_line.unit_price,
                        line_total=line_total,
                        position=position,
                        is_active=True,
                    )
                )

            created = self._recalculate_invoice(
                created
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                activity_type="invoice_created_from_closeout",
                summary=(
                    f"Final invoice {created.invoice_number} "
                    "created from approved closeout."
                ),
                to_status=InvoiceStatus.DRAFT.value,
                details={
                    "invoice_id": str(created.id),
                    "invoice_number": created.invoice_number,
                    "closeout_id": str(closeout.id),
                    "currency": created.currency,
                    "subtotal": str(created.subtotal),
                    "total_amount": str(
                        created.total_amount
                    ),
                    "generated_closeout_line_count": (
                        generated_closeout_line_count
                    ),
                    "manual_line_count": len(
                        payload.manual_line_items
                    ),
                },
            )

            self.auto_audit.invoice_created(

                organization_id=organization_id,

                invoice=created,

                actor_user_id=actor_user_id,

                source="closeout",

            )


            self.db.commit()

            loaded = self._reload_invoice(
                organization_id=organization_id,
                invoice_id=created.id,
            )

            return self._build_response(
                loaded
            )

        except HTTPException:
            self.db.rollback()
            raise

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The closeout invoice conflicts with "
                    "an existing invoice or line item."
                ),
            ) from exc

        except Exception:
            self.db.rollback()
            raise


    def list_invoices(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        invoice_status: InvoiceStatus | None = None,
        currency: str | None = None,
        customer_id: uuid.UUID | None = None,
        work_order_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        include_inactive: bool = False,
    ) -> InvoiceListResponse:
        """
        List organization invoices with optional filters.
        """

        self._ensure_date_range_valid(
            date_from=date_from,
            date_to=date_to,
        )

        normalized_currency = (
            currency.strip().upper()
            if currency is not None
            else None
        )

        invoices = self.invoices.list_for_organization(
            organization_id=organization_id,
            skip=skip,
            limit=limit,
            search=search,
            invoice_status=(
                invoice_status.value
                if invoice_status is not None
                else None
            ),
            currency=normalized_currency,
            customer_id=customer_id,
            work_order_id=work_order_id,
            date_from=date_from,
            date_to=date_to,
            include_inactive=include_inactive,
        )

        total = self.invoices.count_for_organization(
            organization_id=organization_id,
            search=search,
            invoice_status=(
                invoice_status.value
                if invoice_status is not None
                else None
            ),
            currency=normalized_currency,
            customer_id=customer_id,
            work_order_id=work_order_id,
            date_from=date_from,
            date_to=date_to,
            include_inactive=include_inactive,
        )

        return InvoiceListResponse(
            items=[
                self._build_response(invoice)
                for invoice in invoices
            ],
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_invoice(
        self,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> InvoiceResponse:
        """
        Return one organization-scoped invoice.
        """

        invoice = self._get_invoice_or_404(
            organization_id=organization_id,
            invoice_id=invoice_id,
            include_inactive=include_inactive,
        )

        return self._build_response(
            invoice
        )

    def update_invoice(
        self,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        payload: InvoiceUpdate,
        *,
        actor_user_id: uuid.UUID,
    ) -> InvoiceResponse:
        """
        Update editable draft-invoice fields.
        """

        invoice = self._get_invoice_or_404(
            organization_id=organization_id,
            invoice_id=invoice_id,
        )

        self._ensure_draft(invoice)

        update_data = payload.model_dump(
            exclude_unset=True
        )

        non_nullable_fields = {
            "invoice_date",
            "discount_amount",
            "tax_amount",
        }

        for field_name in non_nullable_fields:
            if (
                field_name in update_data
                and update_data[field_name] is None
            ):
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail=(
                        f"{field_name.replace('_', ' ').title()} "
                        "cannot be null."
                    ),
                )

        effective_invoice_date = update_data.get(
            "invoice_date",
            invoice.invoice_date,
        )
        effective_due_date = update_data.get(
            "due_date",
            invoice.due_date,
        )

        if (
            effective_due_date is not None
            and effective_due_date < effective_invoice_date
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=(
                    "due_date cannot be earlier than invoice_date."
                ),
            )

        changed_fields = sorted(update_data.keys())

        for field_name, value in update_data.items():
            if field_name in {
                "discount_amount",
                "tax_amount",
            }:
                value = self._money(value)

            setattr(invoice, field_name, value)

        try:
            invoice = self._recalculate_invoice(
                invoice
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=invoice.work_order_id,
                actor_user_id=actor_user_id,
                activity_type="invoice_updated",
                summary=(
                    f"Invoice {invoice.invoice_number} updated."
                ),
                details={
                    "invoice_id": str(invoice.id),
                    "invoice_number": invoice.invoice_number,
                    "changed_fields": changed_fields,
                    "subtotal": str(invoice.subtotal),
                    "total_amount": str(
                        invoice.total_amount
                    ),
                    "currency": invoice.currency,
                },
            )

            self.db.commit()

            loaded = self._reload_invoice(
                organization_id=organization_id,
                invoice_id=invoice.id,
            )

            return self._build_response(loaded)

        except HTTPException:
            self.db.rollback()
            raise

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The invoice update could not be saved.",
            ) from exc

        except Exception:
            self.db.rollback()
            raise

    def add_manual_line_item(
        self,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        payload: InvoiceLineItemCreate,
        *,
        actor_user_id: uuid.UUID,
    ) -> InvoiceResponse:
        """
        Add a manual charge to a draft invoice.
        """

        invoice = self._get_invoice_or_404(
            organization_id=organization_id,
            invoice_id=invoice_id,
        )

        self._ensure_draft(invoice)

        position = self._resolve_position(
            invoice.id,
            payload.position,
        )
        line_total = self._calculate_line_total(
            payload.quantity,
            payload.unit_price,
        )

        try:
            line_item = self.invoices.add_line_item(
                InvoiceLineItem(
                    invoice_id=invoice.id,
                    work_order_expense_id=None,
                    source_type=(
                        InvoiceLineSource.MANUAL.value
                    ),
                    description=payload.description,
                    quantity=payload.quantity,
                    unit_price=payload.unit_price,
                    line_total=line_total,
                    position=position,
                    is_active=True,
                )
            )

            invoice = self._recalculate_invoice(
                invoice
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=invoice.work_order_id,
                actor_user_id=actor_user_id,
                activity_type="invoice_line_item_added",
                summary=(
                    f"Manual line added to invoice "
                    f"{invoice.invoice_number}."
                ),
                details={
                    "invoice_id": str(invoice.id),
                    "line_item_id": str(line_item.id),
                    "source_type": line_item.source_type,
                    "description": line_item.description,
                    "quantity": str(line_item.quantity),
                    "unit_price": str(line_item.unit_price),
                    "line_total": str(line_item.line_total),
                    "currency": invoice.currency,
                },
            )

            self.db.commit()

            loaded = self._reload_invoice(
                organization_id=organization_id,
                invoice_id=invoice.id,
            )

            return self._build_response(loaded)

        except HTTPException:
            self.db.rollback()
            raise

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The invoice line item conflicts with "
                    "an existing line."
                ),
            ) from exc

        except Exception:
            self.db.rollback()
            raise

    def add_expense_line_item(
        self,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        payload: InvoiceExpenseLineCreate,
        *,
        actor_user_id: uuid.UUID,
    ) -> InvoiceResponse:
        """
        Add one approved billable expense to a draft invoice.
        """

        invoice = self._get_invoice_or_404(
            organization_id=organization_id,
            invoice_id=invoice_id,
        )

        self._ensure_draft(invoice)

        expense = self.invoices.get_billable_expense(
            organization_id=organization_id,
            work_order_id=invoice.work_order_id,
            expense_id=payload.expense_id,
            currency=invoice.currency,
        )

        if expense is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=(
                    "The expense must be active, approved, "
                    "billable, belong to the invoice work order, "
                    "and use the invoice currency."
                ),
            )

        if self.invoices.expense_already_invoiced(
            organization_id=organization_id,
            expense_id=expense.id,
            exclude_invoice_id=invoice.id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This expense has already been invoiced.",
            )

        existing = self.invoices.get_line_item_by_expense(
            invoice_id=invoice.id,
            expense_id=expense.id,
        )

        if existing is not None and existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This expense is already on the invoice."
                ),
            )

        position = self._resolve_position(
            invoice.id,
            payload.position,
            exclude_line_item_id=(
                existing.id
                if existing is not None
                else None
            ),
        )

        try:
            if existing is None:
                line_item = self.invoices.add_line_item(
                    InvoiceLineItem(
                        invoice_id=invoice.id,
                        work_order_expense_id=expense.id,
                        source_type=(
                            InvoiceLineSource.EXPENSE.value
                        ),
                        description=expense.description,
                        quantity=expense.quantity,
                        unit_price=expense.unit_cost,
                        line_total=expense.total_amount,
                        position=position,
                        is_active=True,
                    )
                )
            else:
                existing.source_type = (
                    InvoiceLineSource.EXPENSE.value
                )
                existing.description = expense.description
                existing.quantity = expense.quantity
                existing.unit_price = expense.unit_cost
                existing.line_total = expense.total_amount
                existing.position = position
                existing.is_active = True

                line_item = self.invoices.update_line_item(
                    existing
                )

            invoice = self._recalculate_invoice(
                invoice
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=invoice.work_order_id,
                actor_user_id=actor_user_id,
                activity_type="invoice_line_item_added",
                summary=(
                    f"Expense line added to invoice "
                    f"{invoice.invoice_number}."
                ),
                details={
                    "invoice_id": str(invoice.id),
                    "line_item_id": str(line_item.id),
                    "expense_id": str(expense.id),
                    "source_type": line_item.source_type,
                    "description": line_item.description,
                    "line_total": str(line_item.line_total),
                    "currency": invoice.currency,
                },
            )

            self.db.commit()

            loaded = self._reload_invoice(
                organization_id=organization_id,
                invoice_id=invoice.id,
            )

            return self._build_response(loaded)

        except HTTPException:
            self.db.rollback()
            raise

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The expense line conflicts with an "
                    "existing invoice line."
                ),
            ) from exc

        except Exception:
            self.db.rollback()
            raise

    def update_line_item(
        self,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        line_item_id: uuid.UUID,
        payload: InvoiceLineItemUpdate,
        *,
        actor_user_id: uuid.UUID,
    ) -> InvoiceResponse:
        """
        Update one manual line on a draft invoice.
        """

        invoice = self._get_invoice_or_404(
            organization_id=organization_id,
            invoice_id=invoice_id,
        )

        self._ensure_draft(invoice)

        line_item = self._get_line_or_404(
            organization_id=organization_id,
            invoice_id=invoice_id,
            line_item_id=line_item_id,
        )

        if (
            line_item.source_type
            != InvoiceLineSource.MANUAL.value
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Expense-generated invoice lines cannot "
                    "be edited manually."
                ),
            )

        update_data = payload.model_dump(
            exclude_unset=True
        )

        for field_name, value in update_data.items():
            if value is None:
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail=(
                        f"{field_name.replace('_', ' ').title()} "
                        "cannot be null."
                    ),
                )

        if "position" in update_data:
            update_data["position"] = self._resolve_position(
                invoice.id,
                update_data["position"],
                exclude_line_item_id=line_item.id,
            )

        changed_fields = sorted(update_data.keys())

        for field_name, value in update_data.items():
            setattr(line_item, field_name, value)

        line_item.line_total = self._calculate_line_total(
            line_item.quantity,
            line_item.unit_price,
        )

        try:
            line_item = self.invoices.update_line_item(
                line_item
            )
            invoice = self._recalculate_invoice(
                invoice
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=invoice.work_order_id,
                actor_user_id=actor_user_id,
                activity_type="invoice_line_item_updated",
                summary=(
                    f"Invoice {invoice.invoice_number} "
                    "line item updated."
                ),
                details={
                    "invoice_id": str(invoice.id),
                    "line_item_id": str(line_item.id),
                    "changed_fields": changed_fields,
                    "description": line_item.description,
                    "quantity": str(line_item.quantity),
                    "unit_price": str(line_item.unit_price),
                    "line_total": str(line_item.line_total),
                    "currency": invoice.currency,
                },
            )

            self.db.commit()

            loaded = self._reload_invoice(
                organization_id=organization_id,
                invoice_id=invoice.id,
            )

            return self._build_response(loaded)

        except HTTPException:
            self.db.rollback()
            raise

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The invoice line update conflicts with "
                    "another line."
                ),
            ) from exc

        except Exception:
            self.db.rollback()
            raise

    def remove_line_item(
        self,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
    ) -> InvoiceResponse:
        """
        Soft-remove one line from a draft invoice.
        """

        invoice = self._get_invoice_or_404(
            organization_id=organization_id,
            invoice_id=invoice_id,
        )

        self._ensure_draft(invoice)

        line_item = self._get_line_or_404(
            organization_id=organization_id,
            invoice_id=invoice_id,
            line_item_id=line_item_id,
        )

        try:
            line_item.is_active = False

            self.invoices.update_line_item(
                line_item
            )
            invoice = self._recalculate_invoice(
                invoice
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=invoice.work_order_id,
                actor_user_id=actor_user_id,
                activity_type="invoice_line_item_removed",
                summary=(
                    f"Line removed from invoice "
                    f"{invoice.invoice_number}."
                ),
                details={
                    "invoice_id": str(invoice.id),
                    "line_item_id": str(line_item.id),
                    "expense_id": (
                        str(line_item.work_order_expense_id)
                        if line_item.work_order_expense_id
                        is not None
                        else None
                    ),
                    "source_type": line_item.source_type,
                    "description": line_item.description,
                    "line_total": str(line_item.line_total),
                    "currency": invoice.currency,
                },
            )

            self.db.commit()

            loaded = self._reload_invoice(
                organization_id=organization_id,
                invoice_id=invoice.id,
            )

            return self._build_response(loaded)

        except HTTPException:
            self.db.rollback()
            raise

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The invoice line could not be removed.",
            ) from exc

        except Exception:
            self.db.rollback()
            raise

    def issue_invoice(
        self,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        payload: InvoiceIssueRequest,
        *,
        actor_user_id: uuid.UUID,
    ) -> InvoiceResponse:
        """
        Issue a completed draft invoice to its customer.
        """

        invoice = self._get_invoice_or_404(
            organization_id=organization_id,
            invoice_id=invoice_id,
        )

        self._ensure_draft(invoice)

        if self._active_line_count(invoice.id) == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "An invoice must contain at least one "
                    "active line item before it can be issued."
                ),
            )

        try:
            invoice = self._recalculate_invoice(
                invoice
            )

            if invoice.total_amount <= Decimal("0.00"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "An invoice total must be greater than "
                        "zero before it can be issued."
                    ),
                )

            previous_status = invoice.status
            invoice.status = InvoiceStatus.ISSUED.value
            invoice.issued_by_user_id = actor_user_id
            invoice.issued_at = self._utc_now()
            invoice.balance_due = invoice.total_amount

            invoice = self.invoices.update_invoice(
                invoice
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=invoice.work_order_id,
                actor_user_id=actor_user_id,
                activity_type="invoice_issued",
                summary=(
                    f"Invoice {invoice.invoice_number} issued."
                ),
                from_status=previous_status,
                to_status=invoice.status,
                note=payload.note,
                details={
                    "invoice_id": str(invoice.id),
                    "invoice_number": invoice.invoice_number,
                    "currency": invoice.currency,
                    "total_amount": str(
                        invoice.total_amount
                    ),
                    "balance_due": str(invoice.balance_due),
                    "due_date": (
                        invoice.due_date.isoformat()
                        if invoice.due_date is not None
                        else None
                    ),
                },
            )

            # Auto notification: invoice issued.
            self.auto_notifications.notify_invoice_issued(
                organization_id=organization_id,
                invoice=invoice,
                actor_user_id=actor_user_id,
            )

            self.auto_audit.invoice_issued(

                organization_id=organization_id,

                invoice=invoice,

                actor_user_id=actor_user_id,

            )


            self.db.commit()

            loaded = self._reload_invoice(
                organization_id=organization_id,
                invoice_id=invoice.id,
            )

            return self._build_response(loaded)

        except HTTPException:
            self.db.rollback()
            raise

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The invoice could not be issued.",
            ) from exc

        except Exception:
            self.db.rollback()
            raise

    def record_payment(
        self,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        payload: InvoicePaymentCreate,
        *,
        actor_user_id: uuid.UUID,
    ) -> InvoiceResponse:
        """
        Record a payment against an issued invoice.
        """

        invoice = self._get_invoice_or_404(
            organization_id=organization_id,
            invoice_id=invoice_id,
        )

        if invoice.status not in {
            InvoiceStatus.ISSUED.value,
            InvoiceStatus.PARTIALLY_PAID.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Payments can only be recorded against "
                    "issued or partially paid invoices."
                ),
            )

        payment_amount = self._money(
            payload.amount
        )

        if payment_amount > invoice.balance_due:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Payment amount cannot exceed the "
                    "invoice balance."
                ),
            )

        previous_status = invoice.status

        try:
            payment = self.invoices.add_payment(
                InvoicePayment(
                    invoice_id=invoice.id,
                    recorded_by_user_id=actor_user_id,
                    amount=payment_amount,
                    currency=invoice.currency,
                    payment_date=payload.payment_date,
                    payment_method=(
                        payload.payment_method.value
                    ),
                    reference_number=(
                        payload.reference_number
                    ),
                    notes=payload.notes,
                    is_reversed=False,
                )
            )

            invoice = self._recalculate_invoice(
                invoice
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=invoice.work_order_id,
                actor_user_id=actor_user_id,
                activity_type="invoice_payment_recorded",
                summary=(
                    f"Payment recorded for invoice "
                    f"{invoice.invoice_number}."
                ),
                from_status=previous_status,
                to_status=invoice.status,
                details={
                    "invoice_id": str(invoice.id),
                    "payment_id": str(payment.id),
                    "amount": str(payment.amount),
                    "currency": payment.currency,
                    "payment_method": (
                        payment.payment_method
                    ),
                    "reference_number": (
                        payment.reference_number
                    ),
                    "amount_paid": str(
                        invoice.amount_paid
                    ),
                    "balance_due": str(
                        invoice.balance_due
                    ),
                },
            )

            # Auto notification: payment recorded.
            self.auto_notifications.notify_payment_recorded(
                organization_id=organization_id,
                invoice=invoice,
                payment=payment,
                actor_user_id=actor_user_id,
            )

            self.auto_audit.invoice_payment_recorded(

                organization_id=organization_id,

                invoice=invoice,

                payment=payment,

                actor_user_id=actor_user_id,

                previous_status=previous_status,

            )


            self.db.commit()

            loaded = self._reload_invoice(
                organization_id=organization_id,
                invoice_id=invoice.id,
            )

            return self._build_response(loaded)

        except HTTPException:
            self.db.rollback()
            raise

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The payment could not be recorded.",
            ) from exc

        except Exception:
            self.db.rollback()
            raise

    def reverse_payment(
        self,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        payment_id: uuid.UUID,
        payload: InvoicePaymentReverse,
        *,
        actor_user_id: uuid.UUID,
    ) -> InvoiceResponse:
        """
        Reverse an incorrect invoice payment.
        """

        invoice = self._get_invoice_or_404(
            organization_id=organization_id,
            invoice_id=invoice_id,
        )

        if invoice.status in {
            InvoiceStatus.DRAFT.value,
            InvoiceStatus.VOID.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Payments cannot be reversed on draft "
                    "or void invoices."
                ),
            )

        payment = self._get_payment_or_404(
            organization_id=organization_id,
            invoice_id=invoice_id,
            payment_id=payment_id,
        )

        if payment.is_reversed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This payment has already been reversed.",
            )

        previous_status = invoice.status

        try:
            payment.is_reversed = True
            payment.reversed_by_user_id = actor_user_id
            payment.reversed_at = self._utc_now()
            payment.reversal_reason = payload.reason

            self.invoices.update_payment(
                payment
            )
            invoice = self._recalculate_invoice(
                invoice
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=invoice.work_order_id,
                actor_user_id=actor_user_id,
                activity_type="invoice_payment_reversed",
                summary=(
                    f"Payment reversed for invoice "
                    f"{invoice.invoice_number}."
                ),
                from_status=previous_status,
                to_status=invoice.status,
                note=payload.reason,
                details={
                    "invoice_id": str(invoice.id),
                    "payment_id": str(payment.id),
                    "amount": str(payment.amount),
                    "currency": payment.currency,
                    "amount_paid": str(
                        invoice.amount_paid
                    ),
                    "balance_due": str(
                        invoice.balance_due
                    ),
                },
            )

            self.auto_audit.invoice_payment_reversed(

                organization_id=organization_id,

                invoice=invoice,

                payment=payment,

                actor_user_id=actor_user_id,

                previous_status=previous_status,

            )


            self.db.commit()

            loaded = self._reload_invoice(
                organization_id=organization_id,
                invoice_id=invoice.id,
            )

            return self._build_response(loaded)

        except HTTPException:
            self.db.rollback()
            raise

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The payment reversal could not be saved.",
            ) from exc

        except Exception:
            self.db.rollback()
            raise

    def void_invoice(
        self,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        payload: InvoiceVoidRequest,
        *,
        actor_user_id: uuid.UUID,
    ) -> InvoiceResponse:
        """
        Void an issued invoice that has no active payments.
        """

        invoice = self._get_invoice_or_404(
            organization_id=organization_id,
            invoice_id=invoice_id,
        )

        if invoice.status != InvoiceStatus.ISSUED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only issued invoices can be voided. "
                    "Reverse any payments first."
                ),
            )

        if (
            self.invoices.active_payment_total(invoice.id)
            > Decimal("0.00")
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "An invoice with active payments cannot "
                    "be voided."
                ),
            )

        previous_status = invoice.status

        try:
            invoice.status = InvoiceStatus.VOID.value
            invoice.voided_by_user_id = actor_user_id
            invoice.voided_at = self._utc_now()
            invoice.void_reason = payload.reason
            invoice.balance_due = Decimal("0.00")
            invoice.paid_at = None

            invoice = self.invoices.update_invoice(
                invoice
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=invoice.work_order_id,
                actor_user_id=actor_user_id,
                activity_type="invoice_voided",
                summary=(
                    f"Invoice {invoice.invoice_number} voided."
                ),
                from_status=previous_status,
                to_status=invoice.status,
                note=payload.reason,
                details={
                    "invoice_id": str(invoice.id),
                    "invoice_number": invoice.invoice_number,
                    "currency": invoice.currency,
                    "total_amount": str(
                        invoice.total_amount
                    ),
                },
            )

            self.db.commit()

            loaded = self._reload_invoice(
                organization_id=organization_id,
                invoice_id=invoice.id,
            )

            return self._build_response(loaded)

        except HTTPException:
            self.db.rollback()
            raise

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The invoice could not be voided.",
            ) from exc

        except Exception:
            self.db.rollback()
            raise

    def get_summary(
        self,
        organization_id: uuid.UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        include_inactive: bool = False,
    ) -> InvoiceSummaryResponse:
        """
        Return organization billing totals by currency.
        """

        self._ensure_date_range_valid(
            date_from=date_from,
            date_to=date_to,
        )

        rows = self.invoices.summary_by_currency(
            organization_id=organization_id,
            date_from=date_from,
            date_to=date_to,
            include_inactive=include_inactive,
        )

        summaries = [
            InvoiceCurrencySummary(
                currency=currency,
                invoice_count=int(invoice_count or 0),
                total_invoiced=self._money(
                    total_invoiced or Decimal("0.00")
                ),
                total_paid=self._money(
                    total_paid or Decimal("0.00")
                ),
                total_outstanding=self._money(
                    total_outstanding
                    or Decimal("0.00")
                ),
                draft_count=int(draft_count or 0),
                issued_count=int(issued_count or 0),
                partially_paid_count=int(
                    partially_paid_count or 0
                ),
                paid_count=int(paid_count or 0),
                void_count=int(void_count or 0),
            )
            for (
                currency,
                invoice_count,
                total_invoiced,
                total_paid,
                total_outstanding,
                draft_count,
                issued_count,
                partially_paid_count,
                paid_count,
                void_count,
            ) in rows
        ]

        return InvoiceSummaryResponse(
            currencies=summaries
        )
