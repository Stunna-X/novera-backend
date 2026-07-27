"""Business logic for supplier payments and AP settlement."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.supplier_bill import SupplierBill
from app.models.supplier_payment import (
    SupplierPayment,
    SupplierPaymentAllocation,
)
from app.repositories.supplier_payment import SupplierPaymentRepository
from app.schemas.audit_log import AuditLogCreate
from app.schemas.supplier_payment import (
    SupplierBillSettlementStatus,
    SupplierPayableBillResponse,
    SupplierPayableListResponse,
    SupplierPaymentCreate,
    SupplierPaymentListResponse,
    SupplierPaymentReverse,
)
from app.services.audit_log_service import AuditLogService


MONEY = Decimal("0.01")


class SupplierPaymentService:
    """Post, retrieve, reverse, and report supplier settlements."""

    def __init__(self, db: Session):
        self.db = db
        self.payments = SupplierPaymentRepository(db)
        self.audit_logs = AuditLogService(db)

    @staticmethod
    def _money(value: Decimal | str | int) -> Decimal:
        return Decimal(value).quantize(
            MONEY,
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, dict):
            return {
                str(key): SupplierPaymentService._json_safe(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [
                SupplierPaymentService._json_safe(item)
                for item in value
            ]
        return value

    def _record_audit(
        self,
        *,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
        action: str,
        entity_id: uuid.UUID,
        summary: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.audit_logs.record_event(
            organization_id=organization_id,
            payload=AuditLogCreate(
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action=action,
                entity_type="supplier_payment",
                entity_id=entity_id,
                summary=summary,
                status="success",
                details=self._json_safe(details or {}),
            ),
            commit=False,
        )

    @staticmethod
    def _generated_number() -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        return f"SP-{stamp}-{uuid.uuid4().hex[:8].upper()}"

    def _get_or_404(
        self,
        organization_id: uuid.UUID,
        supplier_payment_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierPayment:
        payment = self.payments.get_payment(
            organization_id,
            supplier_payment_id,
            for_update=for_update,
        )
        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier payment not found.",
            )
        return payment

    def record_payment(
        self,
        organization_id: uuid.UUID,
        payload: SupplierPaymentCreate,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> SupplierPayment:
        supplier = self.payments.get_supplier(
            organization_id,
            payload.supplier_id,
            for_update=True,
        )
        if supplier is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found.",
            )

        payment_number = (
            payload.payment_number or self._generated_number()
        ).strip().upper()

        if self.payments.payment_number_exists(
            organization_id,
            payment_number,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier payment number already exists.",
            )

        reference_number = (
            payload.reference_number.strip().upper()
            if payload.reference_number
            else None
        )
        if (
            reference_number is not None
            and self.payments.reference_exists(
                organization_id,
                payload.supplier_id,
                reference_number,
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This supplier payment reference has already "
                    "been recorded."
                ),
            )

        allocation_by_bill = {
            item.supplier_bill_id: item
            for item in payload.allocations
        }
        bill_ids = sorted(
            allocation_by_bill,
            key=str,
        )
        bills = self.payments.get_bills_for_update(
            organization_id,
            bill_ids,
        )
        if len(bills) != len(bill_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more supplier bills were not found.",
            )

        bills_by_id = {bill.id: bill for bill in bills}
        allocation_details: list[dict[str, Any]] = []

        for bill_id in bill_ids:
            bill = bills_by_id[bill_id]
            allocation = allocation_by_bill[bill_id]

            if bill.status != "approved":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Only approved supplier bills can receive "
                        "payment allocations."
                    ),
                )
            if bill.supplier_id != payload.supplier_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "All allocated bills must belong to the "
                        "selected supplier."
                    ),
                )
            if bill.currency.upper() != payload.currency.upper():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Payment currency must match every allocated "
                        "supplier bill."
                    ),
                )

            paid = self._money(
                self.payments.active_allocated_total(bill.id)
            )
            total = self._money(bill.total_amount)
            outstanding = max(
                self._money(total - paid),
                Decimal("0.00"),
            )
            amount = self._money(allocation.amount_allocated)

            if amount > outstanding:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Allocation exceeds outstanding balance for "
                        f"bill {bill.supplier_bill_number}."
                    ),
                )

            allocation_details.append(
                {
                    "supplier_bill_id": bill.id,
                    "supplier_bill_number": (
                        bill.supplier_bill_number
                    ),
                    "amount_allocated": amount,
                    "previous_amount_paid": paid,
                    "previous_balance_due": outstanding,
                    "new_balance_due": self._money(
                        outstanding - amount
                    ),
                }
            )

        payment = SupplierPayment(
            organization_id=organization_id,
            payment_number=payment_number,
            supplier_id=payload.supplier_id,
            payment_date=payload.payment_date,
            payment_method=payload.payment_method.value,
            currency=payload.currency.upper(),
            total_amount=self._money(payload.total_amount),
            reference_number=reference_number,
            status="posted",
            recorded_by_user_id=actor_user_id,
            notes=payload.notes,
            details=dict(payload.details),
        )

        allocations = [
            SupplierPaymentAllocation(
                supplier_payment=payment,
                supplier_bill_id=bill_id,
                amount_allocated=self._money(
                    allocation_by_bill[bill_id].amount_allocated
                ),
                position=position,
                notes=allocation_by_bill[bill_id].notes,
                details=dict(
                    allocation_by_bill[bill_id].details
                ),
            )
            for position, bill_id in enumerate(bill_ids)
        ]

        try:
            self.payments.create_payment(payment)
            self.payments.add_allocations(allocations)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_payment_posted",
                entity_id=payment.id,
                summary="Supplier payment posted and allocated.",
                details={
                    "payment_number": payment.payment_number,
                    "supplier_id": payment.supplier_id,
                    "payment_date": payment.payment_date,
                    "payment_method": payment.payment_method,
                    "currency": payment.currency,
                    "total_amount": payment.total_amount,
                    "reference_number": payment.reference_number,
                    "allocations": allocation_details,
                },
            )
            self.db.commit()
            return self._get_or_404(
                organization_id,
                payment.id,
            )
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Supplier payment number or reference already exists."
                ),
            ) from exc
        except SQLAlchemyError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

    def get_payment(
        self,
        organization_id: uuid.UUID,
        supplier_payment_id: uuid.UUID,
    ) -> SupplierPayment:
        return self._get_or_404(
            organization_id,
            supplier_payment_id,
        )

    def list_payments(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        supplier_id: uuid.UUID | None = None,
        status_filter: str | None = None,
        payment_from: date | None = None,
        payment_to: date | None = None,
        search: str | None = None,
    ) -> SupplierPaymentListResponse:
        return SupplierPaymentListResponse(
            items=self.payments.list_payments(
                organization_id,
                skip=skip,
                limit=limit,
                supplier_id=supplier_id,
                status_filter=status_filter,
                payment_from=payment_from,
                payment_to=payment_to,
                search=search,
            ),
            total=self.payments.count_payments(
                organization_id,
                supplier_id=supplier_id,
                status_filter=status_filter,
                payment_from=payment_from,
                payment_to=payment_to,
                search=search,
            ),
            skip=skip,
            limit=limit,
        )

    def reverse_payment(
        self,
        organization_id: uuid.UUID,
        supplier_payment_id: uuid.UUID,
        payload: SupplierPaymentReverse,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> SupplierPayment:
        payment = self._get_or_404(
            organization_id,
            supplier_payment_id,
            for_update=True,
        )
        if payment.status == "reversed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier payment is already reversed.",
            )

        bill_ids = sorted(
            {
                allocation.supplier_bill_id
                for allocation in payment.allocations
            },
            key=str,
        )
        bills = self.payments.get_bills_for_update(
            organization_id,
            bill_ids,
        )
        if len(bills) != len(bill_ids):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "An allocated supplier bill is no longer available."
                ),
            )

        payment.status = "reversed"
        payment.reversed_at = datetime.now(UTC)
        payment.reversed_by_user_id = actor_user_id
        payment.reversal_reason = payload.reason

        try:
            self.payments.update_payment(payment)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_payment_reversed",
                entity_id=payment.id,
                summary="Supplier payment reversed.",
                details={
                    "payment_number": payment.payment_number,
                    "supplier_id": payment.supplier_id,
                    "currency": payment.currency,
                    "total_amount": payment.total_amount,
                    "reason": payload.reason,
                    "supplier_bill_ids": bill_ids,
                },
            )
            self.db.commit()
            return self._get_or_404(
                organization_id,
                payment.id,
            )
        except SQLAlchemyError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

    def list_payables(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        supplier_id: uuid.UUID | None = None,
    ) -> SupplierPayableListResponse:
        today = date.today()
        bills = self.payments.list_approved_bills(
            organization_id,
            skip=skip,
            limit=limit,
            supplier_id=supplier_id,
        )
        items: list[SupplierPayableBillResponse] = []

        for bill in bills:
            total = self._money(bill.total_amount)
            amount_paid = self._money(
                self.payments.active_allocated_total(bill.id)
            )
            balance_due = max(
                self._money(total - amount_paid),
                Decimal("0.00"),
            )
            is_overdue = (
                balance_due > 0
                and bill.due_date is not None
                and bill.due_date < today
            )

            if balance_due <= 0:
                settlement_status = (
                    SupplierBillSettlementStatus.PAID
                )
            elif is_overdue:
                settlement_status = (
                    SupplierBillSettlementStatus.OVERDUE
                )
            elif amount_paid > 0:
                settlement_status = (
                    SupplierBillSettlementStatus.PARTIALLY_PAID
                )
            else:
                settlement_status = (
                    SupplierBillSettlementStatus.UNPAID
                )

            items.append(
                SupplierPayableBillResponse(
                    supplier_bill_id=bill.id,
                    supplier_bill_number=(
                        bill.supplier_bill_number
                    ),
                    supplier_invoice_number=(
                        bill.supplier_invoice_number
                    ),
                    supplier_id=bill.supplier_id,
                    supplier_name=bill.supplier.name,
                    invoice_date=bill.invoice_date,
                    due_date=bill.due_date,
                    currency=bill.currency,
                    total_amount=total,
                    amount_paid=amount_paid,
                    balance_due=balance_due,
                    settlement_status=settlement_status,
                    is_overdue=is_overdue,
                )
            )

        return SupplierPayableListResponse(
            items=items,
            total=self.payments.count_approved_bills(
                organization_id,
                supplier_id=supplier_id,
            ),
            skip=skip,
            limit=limit,
        )
