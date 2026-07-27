"""
Supplier bill and three-way matching business logic.

Draft maintenance, submission, matching, approval, and voiding are
organization-scoped. Match runs lock the supplier bill and purchase
order lines before persisting auditable comparison snapshots.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.supplier_bill import (
    SupplierBill,
    SupplierBillLineItem,
    SupplierBillMatchResult,
)
from app.repositories.purchase_order import PurchaseOrderRepository
from app.repositories.supplier import SupplierRepository
from app.repositories.supplier_bill import SupplierBillRepository
from app.schemas.audit_log import AuditLogCreate
from app.schemas.supplier_bill import (
    ApproveSupplierBillSchema,
    CreateSupplierBillSchema,
    MatchSupplierBillSchema,
    SubmitSupplierBillSchema,
    SupplierBillLineCreate,
    SupplierBillLineUpdate,
    SupplierBillListResponse,
    SupplierBillMatchSummaryResponse,
    UpdateSupplierBillSchema,
    VoidSupplierBillSchema,
)
from app.services.audit_log_service import AuditLogService


MONEY = Decimal("0.01")
QUANTITY = Decimal("0.001")
PRICE = Decimal("0.0001")
PERCENT = Decimal("0.0001")
BILLABLE_PURCHASE_ORDER_STATUSES = {
    "issued",
    "acknowledged",
    "partially_received",
    "received",
    "closed",
}


class SupplierBillService:
    """Handle organization-scoped supplier bills."""

    def __init__(self, db: Session):
        self.db = db
        self.supplier_bills = SupplierBillRepository(db)
        self.suppliers = SupplierRepository(db)
        self.purchase_orders = PurchaseOrderRepository(db)
        self.audit_logs = AuditLogService(db)

    @staticmethod
    def _money(value: Decimal | str | int) -> Decimal:
        return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)

    @staticmethod
    def _quantity(value: Decimal | str | int) -> Decimal:
        return Decimal(value).quantize(QUANTITY, rounding=ROUND_HALF_UP)

    @staticmethod
    def _price(value: Decimal | str | int) -> Decimal:
        return Decimal(value).quantize(PRICE, rounding=ROUND_HALF_UP)

    @staticmethod
    def _percent(value: Decimal | str | int) -> Decimal:
        return Decimal(value).quantize(PERCENT, rounding=ROUND_HALF_UP)

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, dict):
            return {
                str(key): SupplierBillService._json_safe(nested)
                for key, nested in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [
                SupplierBillService._json_safe(nested)
                for nested in value
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
                entity_type="supplier_bill",
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
        return f"SB-{stamp}-{uuid.uuid4().hex[:8].upper()}"

    def _get_or_404(
        self,
        organization_id: uuid.UUID,
        supplier_bill_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> SupplierBill:
        bill = self.supplier_bills.get_for_organization(
            organization_id,
            supplier_bill_id,
            include_inactive=include_inactive,
            for_update=for_update,
        )
        if bill is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier bill not found.",
            )
        return bill

    def _get_line_or_404(
        self,
        organization_id: uuid.UUID,
        supplier_bill_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierBillLineItem:
        line = self.supplier_bills.get_line_item(
            organization_id,
            supplier_bill_id,
            line_item_id,
            for_update=for_update,
        )
        if line is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier bill line item not found.",
            )
        return line

    @staticmethod
    def _ensure_draft(bill: SupplierBill) -> None:
        if bill.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only draft supplier bills can be changed.",
            )

    def _get_supplier_or_404(
        self,
        organization_id: uuid.UUID,
        supplier_id: uuid.UUID,
        *,
        for_update: bool = False,
    ):
        supplier = self.suppliers.get_for_organization(
            organization_id,
            supplier_id,
            for_update=for_update,
        )
        if supplier is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found.",
            )
        return supplier

    def _get_purchase_order_or_404(
        self,
        organization_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        *,
        for_update: bool = False,
    ):
        purchase_order = self.purchase_orders.get_for_organization(
            organization_id,
            purchase_order_id,
            for_update=for_update,
        )
        if purchase_order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase order not found.",
            )
        return purchase_order

    def _validate_bill_context(
        self,
        *,
        organization_id: uuid.UUID,
        supplier_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        currency: str,
        for_update: bool = False,
    ):
        supplier = self._get_supplier_or_404(
            organization_id,
            supplier_id,
            for_update=for_update,
        )
        purchase_order = self._get_purchase_order_or_404(
            organization_id,
            purchase_order_id,
            for_update=for_update,
        )
        if purchase_order.supplier_id != supplier.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Supplier bill supplier must match the purchase order.",
            )
        if purchase_order.status not in BILLABLE_PURCHASE_ORDER_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Purchase order must be issued before supplier billing.",
            )
        normalized_currency = currency.strip().upper()
        if purchase_order.currency.strip().upper() != normalized_currency:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Supplier bill currency must match the purchase order.",
            )
        return supplier, purchase_order

    def _ensure_unique_identifiers(
        self,
        *,
        organization_id: uuid.UUID,
        supplier_id: uuid.UUID,
        supplier_bill_number: str,
        supplier_invoice_number: str,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        if self.supplier_bills.number_exists(
            organization_id,
            supplier_bill_number,
            exclude_id=exclude_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier bill number already exists in this organization.",
            )
        if self.supplier_bills.supplier_invoice_exists(
            organization_id,
            supplier_id,
            supplier_invoice_number,
            exclude_id=exclude_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier invoice number already exists for this supplier.",
            )

    def _get_purchase_order_line_or_404(
        self,
        organization_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        for_update: bool = False,
    ):
        line = self.purchase_orders.get_line_item(
            organization_id,
            purchase_order_id,
            line_item_id,
            for_update=for_update,
        )
        if line is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase order line item not found.",
            )
        return line

    def _apply_line_values(
        self,
        line: SupplierBillLineItem,
        *,
        quantity_billed: Decimal,
        unit_price: Decimal,
        tax_rate: Decimal,
    ) -> None:
        quantity = self._quantity(quantity_billed)
        price = self._price(unit_price)
        rate = self._percent(tax_rate)
        subtotal = self._money(quantity * price)
        tax_amount = self._money(subtotal * rate / Decimal("100"))
        line.quantity_billed = quantity
        line.unit_price = price
        line.tax_rate = rate
        line.line_subtotal = subtotal
        line.tax_amount = tax_amount
        line.line_total = self._money(subtotal + tax_amount)

    def _recalculate_totals(self, bill: SupplierBill) -> None:
        lines = self.supplier_bills.list_line_items_for_update(bill.id)
        bill.subtotal = self._money(
            sum((Decimal(line.line_subtotal) for line in lines), Decimal("0"))
        )
        bill.tax_total = self._money(
            sum((Decimal(line.tax_amount) for line in lines), Decimal("0"))
        )
        bill.total_amount = self._money(
            sum((Decimal(line.line_total) for line in lines), Decimal("0"))
        )
        self.supplier_bills.update(bill)

    def _build_line(
        self,
        *,
        organization_id: uuid.UUID,
        bill: SupplierBill,
        payload: SupplierBillLineCreate,
        position: int,
    ) -> SupplierBillLineItem:
        purchase_order_line = self._get_purchase_order_line_or_404(
            organization_id,
            bill.purchase_order_id,
            payload.purchase_order_line_item_id,
        )
        line = SupplierBillLineItem(
            supplier_bill_id=bill.id,
            purchase_order_line_item_id=purchase_order_line.id,
            description=(payload.description or purchase_order_line.description),
            quantity_billed=payload.quantity_billed,
            unit_of_measure=(
                payload.unit_of_measure
                or purchase_order_line.unit_of_measure
            ),
            unit_price=(
                payload.unit_price
                if payload.unit_price is not None
                else purchase_order_line.unit_price
            ),
            tax_rate=payload.tax_rate,
            position=(payload.position if payload.position is not None else position),
            notes=payload.notes,
            details=dict(payload.details),
        )
        self._apply_line_values(
            line,
            quantity_billed=payload.quantity_billed,
            unit_price=line.unit_price,
            tax_rate=payload.tax_rate,
        )
        return line

    def create_supplier_bill(
        self,
        organization_id: uuid.UUID,
        payload: CreateSupplierBillSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> SupplierBill:
        self._validate_bill_context(
            organization_id=organization_id,
            supplier_id=payload.supplier_id,
            purchase_order_id=payload.purchase_order_id,
            currency=payload.currency,
        )
        bill_number = payload.supplier_bill_number or self._generated_number()
        self._ensure_unique_identifiers(
            organization_id=organization_id,
            supplier_id=payload.supplier_id,
            supplier_bill_number=bill_number,
            supplier_invoice_number=payload.supplier_invoice_number,
        )
        bill = SupplierBill(
            organization_id=organization_id,
            supplier_bill_number=bill_number,
            supplier_invoice_number=payload.supplier_invoice_number,
            supplier_id=payload.supplier_id,
            purchase_order_id=payload.purchase_order_id,
            invoice_date=payload.invoice_date,
            due_date=payload.due_date,
            currency=payload.currency,
            quantity_tolerance_percent=payload.quantity_tolerance_percent,
            price_tolerance_percent=payload.price_tolerance_percent,
            notes=payload.notes,
            details=dict(payload.details),
            created_by_user_id=actor_user_id,
        )
        try:
            self.supplier_bills.create(bill)
            for position, line_payload in enumerate(payload.line_items):
                self.supplier_bills.add_line_item(
                    self._build_line(
                        organization_id=organization_id,
                        bill=bill,
                        payload=line_payload,
                        position=position,
                    )
                )
            self._recalculate_totals(bill)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_bill_created",
                entity_id=bill.id,
                summary="Supplier bill created.",
                details={
                    "supplier_id": bill.supplier_id,
                    "purchase_order_id": bill.purchase_order_id,
                    "line_count": len(payload.line_items),
                    "total_amount": bill.total_amount,
                },
            )
            bill_id = bill.id
            self.db.commit()
            return self._get_or_404(organization_id, bill_id)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier bill could not be created due to a conflict.",
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def get_supplier_bill(
        self,
        organization_id: uuid.UUID,
        supplier_bill_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> SupplierBill:
        return self._get_or_404(
            organization_id,
            supplier_bill_id,
            include_inactive=include_inactive,
        )

    def list_supplier_bills(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        status_filter: str | None = None,
        match_status_filter: str | None = None,
        supplier_id: uuid.UUID | None = None,
        purchase_order_id: uuid.UUID | None = None,
        invoice_from: date | None = None,
        invoice_to: date | None = None,
        include_inactive: bool = False,
    ) -> SupplierBillListResponse:
        filters = dict(
            search=search,
            status_filter=status_filter,
            match_status_filter=match_status_filter,
            supplier_id=supplier_id,
            purchase_order_id=purchase_order_id,
            invoice_from=invoice_from,
            invoice_to=invoice_to,
            include_inactive=include_inactive,
        )
        return SupplierBillListResponse(
            items=self.supplier_bills.list_for_organization(
                organization_id,
                skip=skip,
                limit=limit,
                **filters,
            ),
            total=self.supplier_bills.count_for_organization(
                organization_id,
                **filters,
            ),
            skip=skip,
            limit=limit,
        )

    def update_supplier_bill(
        self,
        organization_id: uuid.UUID,
        supplier_bill_id: uuid.UUID,
        payload: UpdateSupplierBillSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> SupplierBill:
        bill = self._get_or_404(
            organization_id,
            supplier_bill_id,
            for_update=True,
        )
        self._ensure_draft(bill)
        changes = payload.model_dump(exclude_unset=True)
        invoice_date = changes.get("invoice_date", bill.invoice_date)
        due_date = changes.get("due_date", bill.due_date)
        if due_date is not None and due_date < invoice_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Due date cannot precede invoice date.",
            )
        supplier_invoice_number = changes.get(
            "supplier_invoice_number",
            bill.supplier_invoice_number,
        )
        self._ensure_unique_identifiers(
            organization_id=organization_id,
            supplier_id=bill.supplier_id,
            supplier_bill_number=bill.supplier_bill_number,
            supplier_invoice_number=supplier_invoice_number,
            exclude_id=bill.id,
        )
        try:
            for key, value in changes.items():
                setattr(bill, key, value)
            self.supplier_bills.update(bill)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_bill_updated",
                entity_id=bill.id,
                summary="Supplier bill updated.",
                details={"changed_fields": sorted(changes)},
            )
            self.db.commit()
            return self._get_or_404(organization_id, bill.id)
        except Exception:
            self.db.rollback()
            raise

    def add_line_item(
        self,
        organization_id: uuid.UUID,
        supplier_bill_id: uuid.UUID,
        payload: SupplierBillLineCreate,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> SupplierBill:
        bill = self._get_or_404(
            organization_id,
            supplier_bill_id,
            for_update=True,
        )
        self._ensure_draft(bill)
        position = len(self.supplier_bills.list_line_items_for_update(bill.id))
        try:
            line = self._build_line(
                organization_id=organization_id,
                bill=bill,
                payload=payload,
                position=position,
            )
            self.supplier_bills.add_line_item(line)
            self._recalculate_totals(bill)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_bill_line_added",
                entity_id=bill.id,
                summary="Supplier bill line added.",
                details={"line_item_id": line.id},
            )
            self.db.commit()
            return self._get_or_404(organization_id, bill.id)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier bill line conflicts with an existing line.",
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def update_line_item(
        self,
        organization_id: uuid.UUID,
        supplier_bill_id: uuid.UUID,
        line_item_id: uuid.UUID,
        payload: SupplierBillLineUpdate,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> SupplierBill:
        bill = self._get_or_404(
            organization_id,
            supplier_bill_id,
            for_update=True,
        )
        self._ensure_draft(bill)
        line = self._get_line_or_404(
            organization_id,
            supplier_bill_id,
            line_item_id,
            for_update=True,
        )
        changes = payload.model_dump(exclude_unset=True)
        try:
            for key in ("description", "unit_of_measure", "position", "notes", "details"):
                if key in changes:
                    setattr(line, key, changes[key])
            self._apply_line_values(
                line,
                quantity_billed=changes.get(
                    "quantity_billed", line.quantity_billed
                ),
                unit_price=changes.get("unit_price", line.unit_price),
                tax_rate=changes.get("tax_rate", line.tax_rate),
            )
            self.supplier_bills.update_line_item(line)
            self._recalculate_totals(bill)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_bill_line_updated",
                entity_id=bill.id,
                summary="Supplier bill line updated.",
                details={
                    "line_item_id": line.id,
                    "changed_fields": sorted(changes),
                },
            )
            self.db.commit()
            return self._get_or_404(organization_id, bill.id)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier bill line update conflicts with another line.",
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def delete_line_item(
        self,
        organization_id: uuid.UUID,
        supplier_bill_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> SupplierBill:
        bill = self._get_or_404(
            organization_id,
            supplier_bill_id,
            for_update=True,
        )
        self._ensure_draft(bill)
        line = self._get_line_or_404(
            organization_id,
            supplier_bill_id,
            line_item_id,
            for_update=True,
        )
        try:
            deleted_id = line.id
            self.supplier_bills.delete_line_item(line)
            self._recalculate_totals(bill)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_bill_line_removed",
                entity_id=bill.id,
                summary="Supplier bill line removed.",
                details={"line_item_id": deleted_id},
            )
            self.db.commit()
            return self._get_or_404(organization_id, bill.id)
        except Exception:
            self.db.rollback()
            raise

    def submit_supplier_bill(
        self,
        organization_id: uuid.UUID,
        supplier_bill_id: uuid.UUID,
        payload: SubmitSupplierBillSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> SupplierBill:
        bill = self._get_or_404(
            organization_id,
            supplier_bill_id,
            for_update=True,
        )
        self._ensure_draft(bill)
        lines = self.supplier_bills.list_line_items_for_update(bill.id)
        if not lines:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier bill requires at least one line before submission.",
            )
        self._validate_bill_context(
            organization_id=organization_id,
            supplier_id=bill.supplier_id,
            purchase_order_id=bill.purchase_order_id,
            currency=bill.currency,
            for_update=True,
        )
        self._recalculate_totals(bill)
        bill.status = "submitted"
        bill.match_status = "not_run"
        bill.submitted_at = datetime.now(UTC)
        bill.submitted_by_user_id = actor_user_id
        try:
            self.supplier_bills.update(bill)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_bill_submitted",
                entity_id=bill.id,
                summary="Supplier bill submitted for three-way matching.",
                details={
                    "line_count": len(lines),
                    "total_amount": bill.total_amount,
                    "note": payload.note,
                },
            )
            self.db.commit()
            return self._get_or_404(organization_id, bill.id)
        except Exception:
            self.db.rollback()
            raise

    @classmethod
    def _variance_percent(
        cls,
        *,
        difference: Decimal,
        baseline: Decimal,
    ) -> Decimal:
        baseline_value = abs(Decimal(baseline))
        if baseline_value == Decimal("0"):
            return Decimal("0.0000") if difference == 0 else Decimal("100.0000")
        calculated = cls._percent(
            abs(Decimal(difference))
            / baseline_value
            * Decimal("100")
        )
        return min(calculated, Decimal("99999.9999"))

    def run_three_way_match(
        self,
        organization_id: uuid.UUID,
        supplier_bill_id: uuid.UUID,
        payload: MatchSupplierBillSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> SupplierBill:
        bill = self._get_or_404(
            organization_id,
            supplier_bill_id,
            for_update=True,
        )
        if bill.status not in {"submitted", "matched", "exception"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only submitted supplier bills can be matched.",
            )
        purchase_order = self._get_purchase_order_or_404(
            organization_id,
            bill.purchase_order_id,
            for_update=True,
        )
        if purchase_order.supplier_id != bill.supplier_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier bill no longer matches its purchase order supplier.",
            )
        quantity_tolerance = self._percent(
            payload.quantity_tolerance_percent
            if payload.quantity_tolerance_percent is not None
            else bill.quantity_tolerance_percent
        )
        price_tolerance = self._percent(
            payload.price_tolerance_percent
            if payload.price_tolerance_percent is not None
            else bill.price_tolerance_percent
        )
        bill.quantity_tolerance_percent = quantity_tolerance
        bill.price_tolerance_percent = price_tolerance
        lines = self.supplier_bills.list_line_items_for_update(bill.id)
        if not lines:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier bill has no lines to match.",
            )
        now = datetime.now(UTC)
        exception_count = 0
        try:
            for line in lines:
                po_line = self._get_purchase_order_line_or_404(
                    organization_id,
                    bill.purchase_order_id,
                    line.purchase_order_line_item_id,
                    for_update=True,
                )
                ordered = self._quantity(po_line.quantity_ordered)
                received = self._quantity(
                    self.supplier_bills.posted_received_quantity(
                        organization_id=organization_id,
                        purchase_order_line_item_id=po_line.id,
                    )
                )
                billed = self._quantity(line.quantity_billed)
                po_price = self._price(po_line.unit_price)
                bill_price = self._price(line.unit_price)
                quantity_variance = self._quantity(billed - received)
                price_variance = self._price(bill_price - po_price)
                allowed_quantity = self._quantity(
                    ordered * quantity_tolerance / Decimal("100")
                )
                quantity_ok = billed <= received + allowed_quantity
                allowed_price = self._price(
                    abs(po_price) * price_tolerance / Decimal("100")
                )
                price_ok = abs(price_variance) <= allowed_price
                reasons: list[str] = []
                if received == Decimal("0.000") and billed > Decimal("0.000"):
                    reasons.append("No accepted quantity exists on a posted goods receipt.")
                if not quantity_ok:
                    reasons.append("Billed quantity exceeds accepted received quantity beyond tolerance.")
                if not price_ok:
                    reasons.append("Supplier unit price differs from purchase-order price beyond tolerance.")
                result_status = "matched" if quantity_ok and price_ok else "exception"
                if result_status == "exception":
                    exception_count += 1
                result = self.supplier_bills.get_match_result(line.id)
                if result is None:
                    result = SupplierBillMatchResult(
                        supplier_bill_id=bill.id,
                        supplier_bill_line_item_id=line.id,
                        purchase_order_line_item_id=po_line.id,
                        status=result_status,
                        quantity_ordered=ordered,
                        quantity_received=received,
                        quantity_billed=billed,
                        purchase_order_unit_price=po_price,
                        supplier_bill_unit_price=bill_price,
                        quantity_variance=quantity_variance,
                        unit_price_variance=price_variance,
                        quantity_variance_percent=self._variance_percent(
                            difference=quantity_variance,
                            baseline=received,
                        ),
                        unit_price_variance_percent=self._variance_percent(
                            difference=price_variance,
                            baseline=po_price,
                        ),
                        quantity_within_tolerance=quantity_ok,
                        price_within_tolerance=price_ok,
                        reasons=reasons,
                        evaluated_at=now,
                        evaluated_by_user_id=actor_user_id,
                    )
                else:
                    result.purchase_order_line_item_id = po_line.id
                    result.status = result_status
                    result.quantity_ordered = ordered
                    result.quantity_received = received
                    result.quantity_billed = billed
                    result.purchase_order_unit_price = po_price
                    result.supplier_bill_unit_price = bill_price
                    result.quantity_variance = quantity_variance
                    result.unit_price_variance = price_variance
                    result.quantity_variance_percent = self._variance_percent(
                        difference=quantity_variance,
                        baseline=received,
                    )
                    result.unit_price_variance_percent = self._variance_percent(
                        difference=price_variance,
                        baseline=po_price,
                    )
                    result.quantity_within_tolerance = quantity_ok
                    result.price_within_tolerance = price_ok
                    result.reasons = reasons
                    result.evaluated_at = now
                    result.evaluated_by_user_id = actor_user_id
                self.supplier_bills.save_match_result(result)
            bill.match_status = "matched" if exception_count == 0 else "exception"
            bill.status = bill.match_status
            bill.matched_at = now
            bill.matched_by_user_id = actor_user_id
            self.supplier_bills.update(bill)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_bill_three_way_match_completed",
                entity_id=bill.id,
                summary="Supplier bill three-way match completed.",
                details={
                    "match_status": bill.match_status,
                    "line_count": len(lines),
                    "exception_count": exception_count,
                    "quantity_tolerance_percent": quantity_tolerance,
                    "price_tolerance_percent": price_tolerance,
                },
            )
            self.db.commit()
            return self._get_or_404(organization_id, bill.id)
        except SQLAlchemyError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

    def approve_supplier_bill(
        self,
        organization_id: uuid.UUID,
        supplier_bill_id: uuid.UUID,
        payload: ApproveSupplierBillSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> SupplierBill:
        bill = self._get_or_404(
            organization_id,
            supplier_bill_id,
            for_update=True,
        )
        if bill.status not in {"matched", "exception"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier bill must be matched before approval.",
            )
        if bill.status == "exception" and not payload.override_reason:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="An override reason is required to approve match exceptions.",
            )
        previous_status = bill.status
        bill.status = "approved"
        bill.approved_at = datetime.now(UTC)
        bill.approved_by_user_id = actor_user_id
        bill.approval_override_reason = payload.override_reason
        try:
            self.supplier_bills.update(bill)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_bill_approved",
                entity_id=bill.id,
                summary="Supplier bill approved.",
                details={
                    "from_status": previous_status,
                    "match_status": bill.match_status,
                    "override_reason": payload.override_reason,
                    "total_amount": bill.total_amount,
                },
            )
            self.db.commit()
            return self._get_or_404(organization_id, bill.id)
        except Exception:
            self.db.rollback()
            raise

    def void_supplier_bill(
        self,
        organization_id: uuid.UUID,
        supplier_bill_id: uuid.UUID,
        payload: VoidSupplierBillSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> SupplierBill:
        bill = self._get_or_404(
            organization_id,
            supplier_bill_id,
            for_update=True,
        )
        if bill.status == "voided":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier bill is already voided.",
            )
        previous_status = bill.status
        bill.status = "voided"
        bill.voided_at = datetime.now(UTC)
        bill.voided_by_user_id = actor_user_id
        bill.void_reason = payload.reason
        try:
            self.supplier_bills.update(bill)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_bill_voided",
                entity_id=bill.id,
                summary="Supplier bill voided.",
                details={
                    "from_status": previous_status,
                    "reason": payload.reason,
                },
            )
            self.db.commit()
            return self._get_or_404(organization_id, bill.id)
        except Exception:
            self.db.rollback()
            raise

    def get_match_summary(
        self,
        organization_id: uuid.UUID,
        supplier_bill_id: uuid.UUID,
    ) -> SupplierBillMatchSummaryResponse:
        bill = self._get_or_404(organization_id, supplier_bill_id)
        results = list(bill.match_results)
        return SupplierBillMatchSummaryResponse(
            supplier_bill_id=bill.id,
            status=bill.status,
            match_status=bill.match_status,
            matched_lines=sum(1 for result in results if result.status == "matched"),
            exception_lines=sum(1 for result in results if result.status == "exception"),
            total_lines=len(bill.line_items),
            quantity_tolerance_percent=bill.quantity_tolerance_percent,
            price_tolerance_percent=bill.price_tolerance_percent,
            evaluated_at=bill.matched_at,
            results=results,
        )
