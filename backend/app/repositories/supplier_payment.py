"""Persistence helpers for supplier payments and payable balances."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.supplier import Supplier
from app.models.supplier_bill import SupplierBill
from app.models.supplier_payment import (
    SupplierPayment,
    SupplierPaymentAllocation,
)


class SupplierPaymentRepository:
    """Organization-scoped supplier-payment persistence."""

    def __init__(self, db: Session):
        self.db = db

    def get_supplier(
        self,
        organization_id: uuid.UUID,
        supplier_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> Supplier | None:
        query = self.db.query(Supplier).filter(
            Supplier.organization_id == organization_id,
            Supplier.id == supplier_id,
            Supplier.is_active.is_(True),
        )
        if for_update:
            query = query.with_for_update(of=Supplier)
        return query.first()

    def get_payment(
        self,
        organization_id: uuid.UUID,
        payment_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierPayment | None:
        query = (
            self.db.query(SupplierPayment)
            .options(
                joinedload(SupplierPayment.supplier),
                joinedload(SupplierPayment.recorded_by),
                joinedload(SupplierPayment.reversed_by),
                selectinload(SupplierPayment.allocations).joinedload(
                    SupplierPaymentAllocation.supplier_bill
                ),
            )
            .filter(
                SupplierPayment.organization_id == organization_id,
                SupplierPayment.id == payment_id,
            )
        )
        if for_update:
            query = query.with_for_update(of=SupplierPayment)
        return query.first()

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
    ) -> list[SupplierPayment]:
        query = (
            self.db.query(SupplierPayment)
            .options(
                joinedload(SupplierPayment.supplier),
                selectinload(SupplierPayment.allocations).joinedload(
                    SupplierPaymentAllocation.supplier_bill
                ),
            )
            .filter(SupplierPayment.organization_id == organization_id)
        )
        query = self._payment_filters(
            query,
            supplier_id=supplier_id,
            status_filter=status_filter,
            payment_from=payment_from,
            payment_to=payment_to,
            search=search,
        )
        return (
            query.order_by(
                SupplierPayment.payment_date.desc(),
                SupplierPayment.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_payments(
        self,
        organization_id: uuid.UUID,
        *,
        supplier_id: uuid.UUID | None = None,
        status_filter: str | None = None,
        payment_from: date | None = None,
        payment_to: date | None = None,
        search: str | None = None,
    ) -> int:
        query = self.db.query(func.count(SupplierPayment.id)).filter(
            SupplierPayment.organization_id == organization_id
        )
        query = self._payment_filters(
            query,
            supplier_id=supplier_id,
            status_filter=status_filter,
            payment_from=payment_from,
            payment_to=payment_to,
            search=search,
        )
        return int(query.scalar() or 0)

    @staticmethod
    def _payment_filters(
        query,
        *,
        supplier_id: uuid.UUID | None,
        status_filter: str | None,
        payment_from: date | None,
        payment_to: date | None,
        search: str | None,
    ):
        if supplier_id is not None:
            query = query.filter(
                SupplierPayment.supplier_id == supplier_id
            )
        if status_filter is not None:
            query = query.filter(
                SupplierPayment.status == status_filter
            )
        if payment_from is not None:
            query = query.filter(
                SupplierPayment.payment_date >= payment_from
            )
        if payment_to is not None:
            query = query.filter(
                SupplierPayment.payment_date <= payment_to
            )
        normalized = search.strip() if search else None
        if normalized:
            pattern = f"%{normalized}%"
            query = query.filter(
                or_(
                    SupplierPayment.payment_number.ilike(pattern),
                    SupplierPayment.reference_number.ilike(pattern),
                )
            )
        return query

    def payment_number_exists(
        self,
        organization_id: uuid.UUID,
        payment_number: str,
    ) -> bool:
        return (
            self.db.query(SupplierPayment.id)
            .filter(
                SupplierPayment.organization_id == organization_id,
                func.lower(SupplierPayment.payment_number)
                == payment_number.strip().lower(),
            )
            .first()
            is not None
        )

    def reference_exists(
        self,
        organization_id: uuid.UUID,
        supplier_id: uuid.UUID,
        reference_number: str,
    ) -> bool:
        return (
            self.db.query(SupplierPayment.id)
            .filter(
                SupplierPayment.organization_id == organization_id,
                SupplierPayment.supplier_id == supplier_id,
                func.lower(SupplierPayment.reference_number)
                == reference_number.strip().lower(),
            )
            .first()
            is not None
        )

    def get_bills_for_update(
        self,
        organization_id: uuid.UUID,
        bill_ids: list[uuid.UUID],
    ) -> list[SupplierBill]:
        return (
            self.db.query(SupplierBill)
            .options(joinedload(SupplierBill.supplier))
            .filter(
                SupplierBill.organization_id == organization_id,
                SupplierBill.id.in_(bill_ids),
                SupplierBill.is_active.is_(True),
            )
            .order_by(SupplierBill.id.asc())
            .with_for_update(of=SupplierBill)
            .all()
        )

    def active_allocated_total(
        self,
        supplier_bill_id: uuid.UUID,
    ) -> Decimal:
        value = (
            self.db.query(
                func.coalesce(
                    func.sum(
                        SupplierPaymentAllocation.amount_allocated
                    ),
                    Decimal("0.00"),
                )
            )
            .join(
                SupplierPayment,
                SupplierPayment.id
                == SupplierPaymentAllocation.supplier_payment_id,
            )
            .filter(
                SupplierPaymentAllocation.supplier_bill_id
                == supplier_bill_id,
                SupplierPayment.status == "posted",
            )
            .scalar()
        )
        return Decimal(value or 0)

    def create_payment(
        self,
        payment: SupplierPayment,
    ) -> SupplierPayment:
        self.db.add(payment)
        self.db.flush()
        return payment

    def add_allocations(
        self,
        allocations: list[SupplierPaymentAllocation],
    ) -> list[SupplierPaymentAllocation]:
        self.db.add_all(allocations)
        self.db.flush()
        return allocations

    def update_payment(
        self,
        payment: SupplierPayment,
    ) -> SupplierPayment:
        self.db.add(payment)
        self.db.flush()
        return payment

    def list_approved_bills(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        supplier_id: uuid.UUID | None = None,
    ) -> list[SupplierBill]:
        query = (
            self.db.query(SupplierBill)
            .options(joinedload(SupplierBill.supplier))
            .filter(
                SupplierBill.organization_id == organization_id,
                SupplierBill.status == "approved",
                SupplierBill.is_active.is_(True),
            )
        )
        if supplier_id is not None:
            query = query.filter(
                SupplierBill.supplier_id == supplier_id
            )
        return (
            query.order_by(
                SupplierBill.due_date.asc().nullslast(),
                SupplierBill.invoice_date.asc(),
                SupplierBill.created_at.asc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_approved_bills(
        self,
        organization_id: uuid.UUID,
        *,
        supplier_id: uuid.UUID | None = None,
    ) -> int:
        query = self.db.query(func.count(SupplierBill.id)).filter(
            SupplierBill.organization_id == organization_id,
            SupplierBill.status == "approved",
            SupplierBill.is_active.is_(True),
        )
        if supplier_id is not None:
            query = query.filter(
                SupplierBill.supplier_id == supplier_id
            )
        return int(query.scalar() or 0)
