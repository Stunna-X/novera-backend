"""Persistence and candidate queries for procurement workflow alerts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.procurement_alert import (
    ProcurementAlertDelivery,
    ProcurementAlertPreference,
)
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_requisition import PurchaseRequisition
from app.models.supplier_bill import SupplierBill
from app.models.supplier_payment import (
    SupplierPayment,
    SupplierPaymentAllocation,
)


@dataclass(frozen=True)
class ProcurementAlertCandidate:
    """Normalized record awaiting preference and dedupe checks."""

    alert_type: str
    entity_type: str
    entity_id: uuid.UUID
    reference_number: str
    due_date: date | None
    title: str
    message: str
    priority: str
    action_url: str
    details: dict[str, str]


class ProcurementAlertRepository:
    """Organization-scoped procurement alert persistence."""

    def __init__(self, db: Session):
        self.db = db

    def get_preference(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> ProcurementAlertPreference | None:
        query = self.db.query(ProcurementAlertPreference).filter(
            ProcurementAlertPreference.organization_id == organization_id,
            ProcurementAlertPreference.user_id == user_id,
        )
        if for_update:
            query = query.with_for_update(
                of=ProcurementAlertPreference
            )
        return query.first()

    def save_preference(
        self,
        preference: ProcurementAlertPreference,
    ) -> ProcurementAlertPreference:
        self.db.add(preference)
        self.db.flush()
        return preference

    def delivery_exists(
        self,
        organization_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        deduplication_key: str,
    ) -> bool:
        return (
            self.db.query(ProcurementAlertDelivery.id)
            .filter(
                ProcurementAlertDelivery.organization_id
                == organization_id,
                ProcurementAlertDelivery.recipient_user_id
                == recipient_user_id,
                ProcurementAlertDelivery.deduplication_key
                == deduplication_key,
            )
            .first()
            is not None
        )

    def save_delivery(
        self,
        delivery: ProcurementAlertDelivery,
    ) -> ProcurementAlertDelivery:
        self.db.add(delivery)
        self.db.flush()
        return delivery

    def list_deliveries(
        self,
        organization_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        *,
        alert_type: str | None,
        skip: int,
        limit: int,
    ) -> tuple[list[ProcurementAlertDelivery], int]:
        query = self.db.query(ProcurementAlertDelivery).filter(
            ProcurementAlertDelivery.organization_id
            == organization_id,
            ProcurementAlertDelivery.recipient_user_id
            == recipient_user_id,
        )
        if alert_type is not None:
            query = query.filter(
                ProcurementAlertDelivery.alert_type == alert_type
            )
        total = int(query.count() or 0)
        items = (
            query.order_by(
                ProcurementAlertDelivery.alert_date.desc(),
                ProcurementAlertDelivery.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, total

    def requisition_approval_candidates(
        self,
        organization_id: uuid.UUID,
    ) -> list[PurchaseRequisition]:
        return (
            self.db.query(PurchaseRequisition)
            .filter(
                PurchaseRequisition.organization_id == organization_id,
                PurchaseRequisition.is_active.is_(True),
                PurchaseRequisition.status == "submitted",
            )
            .order_by(
                PurchaseRequisition.created_at.asc(),
            )
            .all()
        )

    def purchase_order_delivery_candidates(
        self,
        organization_id: uuid.UUID,
        *,
        as_of_date: date,
        lead_days: int,
    ) -> list[PurchaseOrder]:
        cutoff = as_of_date + timedelta(days=lead_days)
        return (
            self.db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.organization_id == organization_id,
                PurchaseOrder.is_active.is_(True),
                PurchaseOrder.status.in_(
                    [
                        "issued",
                        "acknowledged",
                        "partially_received",
                    ]
                ),
                PurchaseOrder.expected_delivery_date.is_not(None),
                PurchaseOrder.expected_delivery_date <= cutoff,
            )
            .order_by(
                PurchaseOrder.expected_delivery_date.asc(),
            )
            .all()
        )

    def match_exception_candidates(
        self,
        organization_id: uuid.UUID,
    ) -> list[SupplierBill]:
        return (
            self.db.query(SupplierBill)
            .filter(
                SupplierBill.organization_id == organization_id,
                SupplierBill.is_active.is_(True),
                SupplierBill.status == "exception",
                SupplierBill.match_status == "exception",
            )
            .order_by(
                SupplierBill.updated_at.asc(),
            )
            .all()
        )

    def payable_candidates(
        self,
        organization_id: uuid.UUID,
        *,
        as_of_date: date,
        lead_days: int,
    ) -> list[tuple[SupplierBill, Decimal]]:
        paid = (
            self.db.query(
                SupplierPaymentAllocation.supplier_bill_id.label(
                    "supplier_bill_id"
                ),
                func.coalesce(
                    func.sum(
                        SupplierPaymentAllocation.amount_allocated
                    ),
                    Decimal("0.00"),
                ).label("amount_paid"),
            )
            .join(
                SupplierPayment,
                SupplierPayment.id
                == SupplierPaymentAllocation.supplier_payment_id,
            )
            .filter(
                SupplierPayment.organization_id == organization_id,
                SupplierPayment.status == "posted",
            )
            .group_by(
                SupplierPaymentAllocation.supplier_bill_id
            )
            .subquery()
        )
        amount_paid = func.coalesce(
            paid.c.amount_paid,
            Decimal("0.00"),
        )
        balance_due = SupplierBill.total_amount - amount_paid
        cutoff = as_of_date + timedelta(days=lead_days)
        rows = (
            self.db.query(
                SupplierBill,
                balance_due.label("balance_due"),
            )
            .outerjoin(
                paid,
                paid.c.supplier_bill_id == SupplierBill.id,
            )
            .filter(
                SupplierBill.organization_id == organization_id,
                SupplierBill.is_active.is_(True),
                SupplierBill.status == "approved",
                SupplierBill.due_date.is_not(None),
                SupplierBill.due_date <= cutoff,
                balance_due > Decimal("0.00"),
            )
            .order_by(
                SupplierBill.due_date.asc(),
            )
            .all()
        )
        return [
            (
                bill,
                Decimal(balance or 0),
            )
            for bill, balance in rows
        ]
