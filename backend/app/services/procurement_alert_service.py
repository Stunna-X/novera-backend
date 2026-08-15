"""Application service for procurement workflow alerts."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.procurement_alert import (
    ProcurementAlertDelivery,
    ProcurementAlertPreference,
)
from app.repositories.procurement_alert import (
    ProcurementAlertCandidate,
    ProcurementAlertRepository,
)
from app.schemas.procurement_alert import (
    ProcurementAlertDeliveryListResponse,
    ProcurementAlertDeliveryResponse,
    ProcurementAlertDispatchResponse,
    ProcurementAlertPreferenceResponse,
    ProcurementAlertPreferenceUpdate,
)


class ProcurementAlertService:
    """Evaluate, deduplicate, and persist procurement alerts."""

    DEFAULT_DELIVERY_LEAD_DAYS = 3
    DEFAULT_PAYMENT_LEAD_DAYS = 3

    def __init__(self, db: Session):
        self.db = db
        self.repository = ProcurementAlertRepository(db)

    @staticmethod
    def deduplication_key(
        *,
        alert_type: str,
        entity_id: uuid.UUID,
        alert_date: date,
    ) -> str:
        raw = f"{alert_type}:{entity_id}:{alert_date.isoformat()}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"procurement:{digest}"

    @staticmethod
    def action_url(
        organization_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
    ) -> str:
        resource = {
            "purchase_requisition": "purchase-requisitions",
            "purchase_order": "purchase-orders",
            "supplier_bill": "supplier-bills",
        }[entity_type]
        return (
            f"/organizations/{organization_id}/"
            f"{resource}/{entity_id}"
        )

    @staticmethod
    def permission_allows(
        alert_type: str,
        permission_names: set[str],
    ) -> bool:
        required = {
            "requisition_approval_required": (
                "purchase_requisitions.approve"
            ),
            "purchase_order_delivery_due": "purchase_orders.read",
            "purchase_order_delivery_overdue": (
                "purchase_orders.read"
            ),
            "supplier_bill_overdue": "supplier_bills.read",
            "supplier_bill_match_exception": "supplier_bills.read",
            "supplier_payment_action_required": (
                "supplier_payments.create"
            ),
        }
        return required[alert_type] in permission_names

    def get_preferences(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ProcurementAlertPreferenceResponse:
        preference = self.repository.get_preference(
            organization_id,
            user_id,
        )
        if preference is None:
            return ProcurementAlertPreferenceResponse(
                organization_id=organization_id,
                user_id=user_id,
                requisition_approval_enabled=True,
                purchase_order_delivery_enabled=True,
                supplier_bill_overdue_enabled=True,
                match_exception_enabled=True,
                payment_action_enabled=True,
                delivery_lead_days=self.DEFAULT_DELIVERY_LEAD_DAYS,
                payment_lead_days=self.DEFAULT_PAYMENT_LEAD_DAYS,
                is_active=True,
                persisted=False,
            )
        return self._preference_response(
            preference,
            persisted=True,
        )

    def update_preferences(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: ProcurementAlertPreferenceUpdate,
    ) -> ProcurementAlertPreferenceResponse:
        try:
            preference = self.repository.get_preference(
                organization_id,
                user_id,
                for_update=True,
            )
            if preference is None:
                preference = ProcurementAlertPreference(
                    organization_id=organization_id,
                    user_id=user_id,
                )
            for field_name in payload.model_fields_set:
                setattr(
                    preference,
                    field_name,
                    getattr(payload, field_name),
                )
            self.repository.save_preference(preference)
            self.db.commit()
            self.db.refresh(preference)
            return self._preference_response(
                preference,
                persisted=True,
            )
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Procurement alert preferences could not be saved.",
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def dispatch(
        self,
        organization_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        permission_names: set[str],
        *,
        as_of_date: date,
    ) -> ProcurementAlertDispatchResponse:
        preference = self.get_preferences(
            organization_id,
            recipient_user_id,
        )
        if not preference.is_active:
            return ProcurementAlertDispatchResponse(
                as_of_date=as_of_date,
                candidate_count=0,
                delivered_count=0,
                duplicate_count=0,
                disabled_count=0,
            )
        candidates = self._candidates(
            organization_id=organization_id,
            permission_names=permission_names,
            as_of_date=as_of_date,
            preference=preference,
        )
        delivered_count = 0
        duplicate_count = 0
        disabled_count = 0
        try:
            for candidate in candidates:
                if not self._enabled(
                    candidate.alert_type,
                    preference,
                ):
                    disabled_count += 1
                    continue
                key = self.deduplication_key(
                    alert_type=candidate.alert_type,
                    entity_id=candidate.entity_id,
                    alert_date=as_of_date,
                )
                if self.repository.delivery_exists(
                    organization_id,
                    recipient_user_id,
                    key,
                ):
                    duplicate_count += 1
                    continue
                notification = Notification(
                    organization_id=organization_id,
                    recipient_user_id=recipient_user_id,
                    actor_user_id=None,
                    notification_type=candidate.alert_type,
                    title=candidate.title,
                    message=candidate.message,
                    priority=candidate.priority,
                    entity_type=candidate.entity_type,
                    entity_id=candidate.entity_id,
                    action_url=candidate.action_url,
                    payload={
                        **candidate.details,
                        "alert_date": as_of_date.isoformat(),
                        "deduplication_key": key,
                    },
                )
                self.db.add(notification)
                self.db.flush()
                delivery = ProcurementAlertDelivery(
                    organization_id=organization_id,
                    recipient_user_id=recipient_user_id,
                    notification_id=notification.id,
                    alert_type=candidate.alert_type,
                    entity_type=candidate.entity_type,
                    entity_id=candidate.entity_id,
                    alert_date=as_of_date,
                    deduplication_key=key,
                    status="delivered",
                    delivered_at=datetime.now(UTC),
                    details=candidate.details,
                )
                self.repository.save_delivery(delivery)
                delivered_count += 1
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A concurrent procurement alert dispatch "
                    "created the same delivery."
                ),
            ) from exc
        except Exception:
            self.db.rollback()
            raise
        return ProcurementAlertDispatchResponse(
            as_of_date=as_of_date,
            candidate_count=len(candidates),
            delivered_count=delivered_count,
            duplicate_count=duplicate_count,
            disabled_count=disabled_count,
        )

    def list_deliveries(
        self,
        organization_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        *,
        alert_type: str | None,
        skip: int,
        limit: int,
    ) -> ProcurementAlertDeliveryListResponse:
        items, total = self.repository.list_deliveries(
            organization_id,
            recipient_user_id,
            alert_type=alert_type,
            skip=skip,
            limit=limit,
        )
        return ProcurementAlertDeliveryListResponse(
            items=[
                ProcurementAlertDeliveryResponse.model_validate(item)
                for item in items
            ],
            total=total,
            skip=skip,
            limit=limit,
        )

    def _candidates(
        self,
        *,
        organization_id: uuid.UUID,
        permission_names: set[str],
        as_of_date: date,
        preference: ProcurementAlertPreferenceResponse,
    ) -> list[ProcurementAlertCandidate]:
        candidates: list[ProcurementAlertCandidate] = []
        if self.permission_allows(
            "requisition_approval_required",
            permission_names,
        ):
            for requisition in (
                self.repository.requisition_approval_candidates(
                    organization_id
                )
            ):
                candidates.append(
                    ProcurementAlertCandidate(
                        alert_type="requisition_approval_required",
                        entity_type="purchase_requisition",
                        entity_id=requisition.id,
                        reference_number=requisition.requisition_number,
                        due_date=requisition.requested_delivery_date,
                        title="Purchase requisition needs approval",
                        message=(
                            f"Requisition {requisition.requisition_number} "
                            f"is waiting for approval."
                        ),
                        priority=(
                            "urgent"
                            if requisition.priority == "urgent"
                            else "high"
                        ),
                        action_url=self.action_url(
                            organization_id,
                            "purchase_requisition",
                            requisition.id,
                        ),
                        details={
                            "requisition_number": (
                                requisition.requisition_number
                            ),
                            "priority": requisition.priority,
                        },
                    )
                )
        if self.permission_allows(
            "purchase_order_delivery_due",
            permission_names,
        ):
            for purchase_order in (
                self.repository.purchase_order_delivery_candidates(
                    organization_id,
                    as_of_date=as_of_date,
                    lead_days=preference.delivery_lead_days,
                )
            ):
                overdue = (
                    purchase_order.expected_delivery_date
                    < as_of_date
                )
                alert_type = (
                    "purchase_order_delivery_overdue"
                    if overdue
                    else "purchase_order_delivery_due"
                )
                candidates.append(
                    ProcurementAlertCandidate(
                        alert_type=alert_type,
                        entity_type="purchase_order",
                        entity_id=purchase_order.id,
                        reference_number=(
                            purchase_order.purchase_order_number
                        ),
                        due_date=(
                            purchase_order.expected_delivery_date
                        ),
                        title=(
                            "Purchase order delivery is overdue"
                            if overdue
                            else "Purchase order delivery is due soon"
                        ),
                        message=(
                            f"Purchase order "
                            f"{purchase_order.purchase_order_number} "
                            f"has an expected delivery date of "
                            f"{purchase_order.expected_delivery_date}."
                        ),
                        priority="urgent" if overdue else "high",
                        action_url=self.action_url(
                            organization_id,
                            "purchase_order",
                            purchase_order.id,
                        ),
                        details={
                            "purchase_order_number": (
                                purchase_order.purchase_order_number
                            ),
                            "expected_delivery_date": (
                                purchase_order
                                .expected_delivery_date
                                .isoformat()
                            ),
                        },
                    )
                )
        if self.permission_allows(
            "supplier_bill_match_exception",
            permission_names,
        ):
            for bill in self.repository.match_exception_candidates(
                organization_id
            ):
                candidates.append(
                    ProcurementAlertCandidate(
                        alert_type="supplier_bill_match_exception",
                        entity_type="supplier_bill",
                        entity_id=bill.id,
                        reference_number=bill.supplier_bill_number,
                        due_date=bill.due_date,
                        title="Supplier bill has a match exception",
                        message=(
                            f"Supplier bill {bill.supplier_bill_number} "
                            f"requires exception review."
                        ),
                        priority="high",
                        action_url=self.action_url(
                            organization_id,
                            "supplier_bill",
                            bill.id,
                        ),
                        details={
                            "supplier_bill_number": (
                                bill.supplier_bill_number
                            ),
                            "match_status": bill.match_status,
                        },
                    )
                )
        payable_rows = self.repository.payable_candidates(
            organization_id,
            as_of_date=as_of_date,
            lead_days=preference.payment_lead_days,
        )
        for bill, balance_due in payable_rows:
            if (
                bill.due_date < as_of_date
                and self.permission_allows(
                    "supplier_bill_overdue",
                    permission_names,
                )
            ):
                candidates.append(
                    self._payable_candidate(
                        organization_id=organization_id,
                        bill=bill,
                        balance_due=balance_due,
                        alert_type="supplier_bill_overdue",
                    )
                )
            elif self.permission_allows(
                "supplier_payment_action_required",
                permission_names,
            ):
                candidates.append(
                    self._payable_candidate(
                        organization_id=organization_id,
                        bill=bill,
                        balance_due=balance_due,
                        alert_type=(
                            "supplier_payment_action_required"
                        ),
                    )
                )
        return candidates

    def _payable_candidate(
        self,
        *,
        organization_id: uuid.UUID,
        bill,
        balance_due: Decimal,
        alert_type: str,
    ) -> ProcurementAlertCandidate:
        overdue = alert_type == "supplier_bill_overdue"
        return ProcurementAlertCandidate(
            alert_type=alert_type,
            entity_type="supplier_bill",
            entity_id=bill.id,
            reference_number=bill.supplier_bill_number,
            due_date=bill.due_date,
            title=(
                "Supplier bill is overdue"
                if overdue
                else "Supplier bill payment action is required"
            ),
            message=(
                f"Supplier bill {bill.supplier_bill_number} "
                f"has an outstanding balance of "
                f"{bill.currency} {balance_due:.2f} "
                f"and a due date of {bill.due_date}."
            ),
            priority="urgent" if overdue else "high",
            action_url=self.action_url(
                organization_id,
                "supplier_bill",
                bill.id,
            ),
            details={
                "supplier_bill_number": bill.supplier_bill_number,
                "currency": bill.currency,
                "balance_due": str(balance_due),
                "due_date": bill.due_date.isoformat(),
            },
        )

    @staticmethod
    def _enabled(
        alert_type: str,
        preference: ProcurementAlertPreferenceResponse,
    ) -> bool:
        mapping = {
            "requisition_approval_required": (
                preference.requisition_approval_enabled
            ),
            "purchase_order_delivery_due": (
                preference.purchase_order_delivery_enabled
            ),
            "purchase_order_delivery_overdue": (
                preference.purchase_order_delivery_enabled
            ),
            "supplier_bill_overdue": (
                preference.supplier_bill_overdue_enabled
            ),
            "supplier_bill_match_exception": (
                preference.match_exception_enabled
            ),
            "supplier_payment_action_required": (
                preference.payment_action_enabled
            ),
        }
        return mapping[alert_type]

    @staticmethod
    def _preference_response(
        preference: ProcurementAlertPreference,
        *,
        persisted: bool,
    ) -> ProcurementAlertPreferenceResponse:
        return ProcurementAlertPreferenceResponse(
            organization_id=preference.organization_id,
            user_id=preference.user_id,
            requisition_approval_enabled=(
                preference.requisition_approval_enabled
            ),
            purchase_order_delivery_enabled=(
                preference.purchase_order_delivery_enabled
            ),
            supplier_bill_overdue_enabled=(
                preference.supplier_bill_overdue_enabled
            ),
            match_exception_enabled=(
                preference.match_exception_enabled
            ),
            payment_action_enabled=(
                preference.payment_action_enabled
            ),
            delivery_lead_days=preference.delivery_lead_days,
            payment_lead_days=preference.payment_lead_days,
            is_active=preference.is_active,
            persisted=persisted,
        )
