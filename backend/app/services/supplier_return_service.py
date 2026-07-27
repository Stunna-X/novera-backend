"""Business logic for supplier returns, debit notes, and credit settlement."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.inventory import InventoryBalance, InventoryMovement
from app.models.supplier import Supplier
from app.models.supplier_payment import (
    SupplierPayment,
    SupplierPaymentAllocation,
)
from app.models.supplier_return import (
    SupplierCreditSettlement,
    SupplierDebitNote,
    SupplierDebitNoteLineItem,
    SupplierReturn,
    SupplierReturnLineItem,
)
from app.repositories.inventory import InventoryRepository
from app.repositories.supplier_payment import SupplierPaymentRepository
from app.repositories.supplier_return import SupplierReturnRepository
from app.schemas.audit_log import AuditLogCreate
from app.schemas.supplier_return import (
    AcknowledgeSupplierDebitNoteSchema,
    CancelSupplierReturnSchema,
    CompleteSupplierReturnSchema,
    CreateSupplierDebitNoteSchema,
    CreateSupplierReturnSchema,
    ReverseSupplierCreditSettlementSchema,
    SettleSupplierDebitNoteSchema,
    SupplierCreditSettlementResponse,
    SupplierDebitNoteLineCreate,
    SupplierDebitNoteLineUpdate,
    SupplierDebitNoteListResponse,
    SupplierDebitNoteResponse,
    SupplierReturnLineCreate,
    SupplierReturnLineUpdate,
    SupplierReturnListResponse,
    UpdateSupplierDebitNoteSchema,
    UpdateSupplierReturnSchema,
    VoidSupplierDebitNoteSchema,
)
from app.services.audit_log_service import AuditLogService


QUANTITY = Decimal("0.001")
COST = Decimal("0.0001")
MONEY = Decimal("0.01")
RATE = Decimal("0.0001")


class SupplierReturnService:
    """Own transaction boundaries for the return-and-credit workflow."""

    def __init__(self, db: Session):
        self.db = db
        self.records = SupplierReturnRepository(db)
        self.inventory = InventoryRepository(db)
        self.payments = SupplierPaymentRepository(db)
        self.audit_logs = AuditLogService(db)

    @staticmethod
    def _quantity(value: Decimal | int | str) -> Decimal:
        return Decimal(value).quantize(
            QUANTITY,
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _cost(value: Decimal | int | str) -> Decimal:
        return Decimal(value).quantize(COST, rounding=ROUND_HALF_UP)

    @staticmethod
    def _money(value: Decimal | int | str) -> Decimal:
        return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)

    @staticmethod
    def _rate(value: Decimal | int | str) -> Decimal:
        return Decimal(value).quantize(RATE, rounding=ROUND_HALF_UP)

    @staticmethod
    def _generated_return_number() -> str:
        return (
            f"SR-{datetime.now(UTC):%Y%m%d}-"
            f"{uuid.uuid4().hex[:8].upper()}"
        )

    @staticmethod
    def _generated_debit_note_number() -> str:
        return (
            f"DN-{datetime.now(UTC):%Y%m%d}-"
            f"{uuid.uuid4().hex[:8].upper()}"
        )

    @staticmethod
    def _generated_credit_payment_number() -> str:
        return (
            f"CR-{datetime.now(UTC):%Y%m%d}-"
            f"{uuid.uuid4().hex[:8].upper()}"
        )

    def _record_audit(
        self,
        *,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
        summary: str,
        details: dict[str, Any],
    ) -> None:
        self.audit_logs.record_event(
            organization_id=organization_id,
            payload=AuditLogCreate(
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                summary=summary,
                status="success",
                request_method="SYSTEM",
                request_path="/system/procurement-return-credit",
                details=details,
            ),
            commit=False,
        )

    def _get_return_or_404(
        self,
        organization_id: uuid.UUID,
        supplier_return_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierReturn:
        item = self.records.get_return(
            organization_id,
            supplier_return_id,
            for_update=for_update,
        )
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier return not found.",
            )
        return item

    def _get_return_line_or_404(
        self,
        organization_id: uuid.UUID,
        supplier_return_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierReturnLineItem:
        item = self.records.get_return_line(
            organization_id,
            supplier_return_id,
            line_item_id,
            for_update=for_update,
        )
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier return line item not found.",
            )
        return item

    def _get_debit_note_or_404(
        self,
        organization_id: uuid.UUID,
        debit_note_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierDebitNote:
        item = self.records.get_debit_note(
            organization_id,
            debit_note_id,
            for_update=for_update,
        )
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier debit note not found.",
            )
        return item

    def _get_debit_note_line_or_404(
        self,
        organization_id: uuid.UUID,
        debit_note_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierDebitNoteLineItem:
        item = self.records.get_debit_note_line(
            organization_id,
            debit_note_id,
            line_item_id,
            for_update=for_update,
        )
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier debit-note line item not found.",
            )
        return item

    @staticmethod
    def _ensure_return_draft(item: SupplierReturn) -> None:
        if item.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only draft supplier returns can be changed.",
            )

    @staticmethod
    def _ensure_debit_note_draft(item: SupplierDebitNote) -> None:
        if item.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only draft supplier debit notes can be changed.",
            )

    @staticmethod
    def _receipt_source_quantity(receipt_line, source: str) -> Decimal:
        field_name = {
            "accepted": "quantity_accepted",
            "rejected": "quantity_rejected",
            "damaged": "quantity_damaged",
        }[source]
        return Decimal(getattr(receipt_line, field_name))

    def _build_return_line(
        self,
        *,
        organization_id: uuid.UUID,
        supplier_return: SupplierReturn,
        payload: SupplierReturnLineCreate,
        position: int,
    ) -> SupplierReturnLineItem:
        receipt_line = self.records.get_goods_receipt_line(
            organization_id,
            supplier_return.goods_receipt_id,
            payload.goods_receipt_line_item_id,
        )
        if receipt_line is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Goods receipt line item not found.",
            )
        source = payload.quantity_source.value
        source_total = self._quantity(
            self._receipt_source_quantity(receipt_line, source)
        )
        already_returned = self._quantity(
            self.records.returned_quantity(
                organization_id,
                receipt_line.id,
                source,
            )
        )
        requested = self._quantity(payload.quantity_returned)
        if requested > self._quantity(source_total - already_returned):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Returned quantity exceeds the remaining "
                    f"{source} receipt quantity."
                ),
            )
        if source == "accepted" and receipt_line.inventory_item_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Accepted receipt quantity has no inventory item "
                    "and cannot be returned from stock."
                ),
            )
        return SupplierReturnLineItem(
            supplier_return_id=supplier_return.id,
            goods_receipt_line_item_id=receipt_line.id,
            inventory_item_id=receipt_line.inventory_item_id,
            quantity_source=source,
            description=receipt_line.description,
            quantity_returned=requested,
            unit_of_measure=receipt_line.unit_of_measure,
            unit_cost=self._cost(receipt_line.unit_cost),
            currency=receipt_line.currency.upper(),
            reason=payload.reason,
            position=position,
            details=dict(payload.details),
        )

    def create_supplier_return(
        self,
        organization_id: uuid.UUID,
        payload: CreateSupplierReturnSchema,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> SupplierReturn:
        receipt = self.records.get_goods_receipt(
            organization_id,
            payload.goods_receipt_id,
        )
        if receipt is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Goods receipt not found.",
            )
        if receipt.status != "posted":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only posted goods receipts can be returned.",
            )
        if receipt.receiving_location_id != payload.source_location_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Supplier returns must use the goods receipt's "
                    "receiving location."
                ),
            )
        return_number = (
            payload.return_number or self._generated_return_number()
        ).strip().upper()
        if self.records.return_number_exists(
            organization_id,
            return_number,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier return number already exists.",
            )
        item = SupplierReturn(
            organization_id=organization_id,
            return_number=return_number,
            supplier_id=receipt.supplier_id,
            purchase_order_id=receipt.purchase_order_id,
            goods_receipt_id=receipt.id,
            source_location_id=payload.source_location_id,
            return_date=payload.return_date,
            reason_code=payload.reason_code.value,
            status="draft",
            supplier_reference=(
                payload.supplier_reference.strip().upper()
                if payload.supplier_reference
                else None
            ),
            carrier_name=(
                payload.carrier_name.strip()
                if payload.carrier_name
                else None
            ),
            tracking_number=(
                payload.tracking_number.strip().upper()
                if payload.tracking_number
                else None
            ),
            notes=payload.notes.strip() if payload.notes else None,
            created_by_user_id=actor_user_id,
            details=dict(payload.details),
        )
        try:
            self.records.create_return(item)
            used_positions: set[int] = set()
            for payload_line in payload.line_items:
                position = (
                    payload_line.position
                    if payload_line.position is not None
                    else self.records.next_return_line_position(item.id)
                )
                if position in used_positions:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="Supplier return line positions must be unique.",
                    )
                used_positions.add(position)
                self.records.add_return_line(
                    self._build_return_line(
                        organization_id=organization_id,
                        supplier_return=item,
                        payload=payload_line,
                        position=position,
                    )
                )
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_return_created",
                entity_type="supplier_return",
                entity_id=item.id,
                summary="Draft supplier return created.",
                details={
                    "return_number": return_number,
                    "goods_receipt_id": receipt.id,
                    "supplier_id": receipt.supplier_id,
                    "line_count": len(payload.line_items),
                },
            )
            self.db.commit()
            return self._get_return_or_404(organization_id, item.id)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier return conflicts with an existing record.",
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def list_supplier_returns(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        supplier_id: uuid.UUID | None,
        status_filter: str | None,
        search: str | None,
    ) -> SupplierReturnListResponse:
        return SupplierReturnListResponse(
            items=self.records.list_returns(
                organization_id,
                skip=skip,
                limit=limit,
                supplier_id=supplier_id,
                status_filter=status_filter,
                search=search,
            ),
            total=self.records.count_returns(
                organization_id,
                supplier_id=supplier_id,
                status_filter=status_filter,
                search=search,
            ),
            skip=skip,
            limit=limit,
        )

    def get_supplier_return(
        self,
        organization_id: uuid.UUID,
        supplier_return_id: uuid.UUID,
    ) -> SupplierReturn:
        return self._get_return_or_404(
            organization_id,
            supplier_return_id,
        )

    def update_supplier_return(
        self,
        organization_id: uuid.UUID,
        supplier_return_id: uuid.UUID,
        payload: UpdateSupplierReturnSchema,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> SupplierReturn:
        item = self._get_return_or_404(
            organization_id,
            supplier_return_id,
            for_update=True,
        )
        self._ensure_return_draft(item)
        for field_name in payload.model_fields_set:
            value = getattr(payload, field_name)
            if hasattr(value, "value"):
                value = value.value
            if isinstance(value, str):
                value = value.strip() or None
            setattr(item, field_name, value)
        try:
            self.records.update_return(item)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_return_updated",
                entity_type="supplier_return",
                entity_id=item.id,
                summary="Draft supplier return updated.",
                details={"changed_fields": sorted(payload.model_fields_set)},
            )
            self.db.commit()
            return self._get_return_or_404(organization_id, item.id)
        except Exception:
            self.db.rollback()
            raise

    def add_return_line(
        self,
        organization_id: uuid.UUID,
        supplier_return_id: uuid.UUID,
        payload: SupplierReturnLineCreate,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> SupplierReturn:
        item = self._get_return_or_404(
            organization_id,
            supplier_return_id,
            for_update=True,
        )
        self._ensure_return_draft(item)
        position = (
            payload.position
            if payload.position is not None
            else self.records.next_return_line_position(item.id)
        )
        try:
            line = self._build_return_line(
                organization_id=organization_id,
                supplier_return=item,
                payload=payload,
                position=position,
            )
            self.records.add_return_line(line)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_return_line_added",
                entity_type="supplier_return",
                entity_id=item.id,
                summary="Supplier return line added.",
                details={"line_item_id": line.id},
            )
            self.db.commit()
            return self._get_return_or_404(organization_id, item.id)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This receipt source or line position is already "
                    "used on the supplier return."
                ),
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def update_return_line(
        self,
        organization_id: uuid.UUID,
        supplier_return_id: uuid.UUID,
        line_item_id: uuid.UUID,
        payload: SupplierReturnLineUpdate,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> SupplierReturn:
        item = self._get_return_or_404(
            organization_id,
            supplier_return_id,
            for_update=True,
        )
        self._ensure_return_draft(item)
        line = self._get_return_line_or_404(
            organization_id,
            supplier_return_id,
            line_item_id,
            for_update=True,
        )
        if "quantity_returned" in payload.model_fields_set:
            receipt_line = self.records.get_goods_receipt_line(
                organization_id,
                item.goods_receipt_id,
                line.goods_receipt_line_item_id,
            )
            source_total = self._quantity(
                self._receipt_source_quantity(
                    receipt_line,
                    line.quantity_source,
                )
            )
            previous = self._quantity(
                self.records.returned_quantity(
                    organization_id,
                    line.goods_receipt_line_item_id,
                    line.quantity_source,
                    exclude_line_item_id=line.id,
                )
            )
            requested = self._quantity(payload.quantity_returned)
            if requested > self._quantity(source_total - previous):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Updated return quantity exceeds source quantity.",
                )
            line.quantity_returned = requested
        for field_name in payload.model_fields_set - {
            "quantity_returned"
        }:
            value = getattr(payload, field_name)
            if isinstance(value, str):
                value = value.strip()
            setattr(line, field_name, value)
        try:
            self.records.update_return_line(line)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_return_line_updated",
                entity_type="supplier_return",
                entity_id=item.id,
                summary="Supplier return line updated.",
                details={
                    "line_item_id": line.id,
                    "changed_fields": sorted(payload.model_fields_set),
                },
            )
            self.db.commit()
            return self._get_return_or_404(organization_id, item.id)
        except Exception:
            self.db.rollback()
            raise

    def delete_return_line(
        self,
        organization_id: uuid.UUID,
        supplier_return_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> SupplierReturn:
        item = self._get_return_or_404(
            organization_id,
            supplier_return_id,
            for_update=True,
        )
        self._ensure_return_draft(item)
        line = self._get_return_line_or_404(
            organization_id,
            supplier_return_id,
            line_item_id,
            for_update=True,
        )
        try:
            self.records.delete_return_line(line)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_return_line_removed",
                entity_type="supplier_return",
                entity_id=item.id,
                summary="Supplier return line removed.",
                details={"line_item_id": line.id},
            )
            self.db.commit()
            return self._get_return_or_404(organization_id, item.id)
        except Exception:
            self.db.rollback()
            raise

    def dispatch_supplier_return(
        self,
        organization_id: uuid.UUID,
        supplier_return_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> SupplierReturn:
        item = self._get_return_or_404(
            organization_id,
            supplier_return_id,
            for_update=True,
        )
        self._ensure_return_draft(item)
        lines = sorted(
            item.line_items,
            key=lambda line: (
                str(line.inventory_item_id or ""),
                line.position,
            ),
        )
        if not lines:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier return must contain at least one line.",
            )
        occurred_at = datetime.now(UTC)
        try:
            for line in lines:
                source_total = self._quantity(
                    self._receipt_source_quantity(
                        line.goods_receipt_line_item,
                        line.quantity_source,
                    )
                )
                previous = self._quantity(
                    self.records.returned_quantity(
                        organization_id,
                        line.goods_receipt_line_item_id,
                        line.quantity_source,
                        exclude_line_item_id=line.id,
                    )
                )
                quantity = self._quantity(line.quantity_returned)
                if quantity > self._quantity(source_total - previous):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "A supplier return line exceeds the remaining "
                            "receipt quantity."
                        ),
                    )
                if line.quantity_source != "accepted":
                    continue
                balance = (
                    self.db.query(InventoryBalance)
                    .populate_existing()
                    .filter(
                        InventoryBalance.organization_id
                        == organization_id,
                        InventoryBalance.item_id
                        == line.inventory_item_id,
                        InventoryBalance.location_id
                        == item.source_location_id,
                    )
                    .with_for_update(of=InventoryBalance)
                    .first()
                )
                if balance is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "No inventory balance exists for an accepted "
                            "supplier return line."
                        ),
                    )
                on_hand = self._quantity(balance.quantity_on_hand)
                reserved = self._quantity(balance.quantity_reserved)
                if quantity > self._quantity(on_hand - reserved):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Available inventory is insufficient for "
                            "the supplier return."
                        ),
                    )
                quantity_after = self._quantity(on_hand - quantity)
                balance.quantity_on_hand = quantity_after
                balance.last_movement_at = occurred_at
                self.inventory.update_balance(balance)
                movement = InventoryMovement(
                    organization_id=organization_id,
                    item_id=line.inventory_item_id,
                    location_id=item.source_location_id,
                    movement_type="adjustment_out",
                    quantity=quantity,
                    quantity_delta=-quantity,
                    quantity_before=on_hand,
                    quantity_after=quantity_after,
                    unit_cost=self._cost(balance.average_unit_cost),
                    currency=line.currency,
                    reference_type="supplier_return",
                    reference_id=str(item.id),
                    occurred_at=occurred_at,
                    notes=f"Supplier return {item.return_number}",
                    created_by_user_id=actor_user_id,
                    details={
                        "supplier_return_id": str(item.id),
                        "supplier_return_line_item_id": str(line.id),
                        "goods_receipt_line_item_id": str(
                            line.goods_receipt_line_item_id
                        ),
                        "quantity_source": line.quantity_source,
                    },
                )
                self.inventory.create_movement(movement)
                line.inventory_movement_id = movement.id
                self.records.update_return_line(line)
            item.status = "dispatched"
            item.dispatched_at = occurred_at
            item.dispatched_by_user_id = actor_user_id
            self.records.update_return(item)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_return_dispatched",
                entity_type="supplier_return",
                entity_id=item.id,
                summary="Supplier return dispatched.",
                details={
                    "return_number": item.return_number,
                    "supplier_id": item.supplier_id,
                    "line_count": len(lines),
                    "inventory_movement_count": sum(
                        1
                        for line in lines
                        if line.quantity_source == "accepted"
                    ),
                },
            )
            self.db.commit()
            return self._get_return_or_404(organization_id, item.id)
        except Exception:
            self.db.rollback()
            raise

    def complete_supplier_return(
        self,
        organization_id: uuid.UUID,
        supplier_return_id: uuid.UUID,
        payload: CompleteSupplierReturnSchema,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> SupplierReturn:
        item = self._get_return_or_404(
            organization_id,
            supplier_return_id,
            for_update=True,
        )
        if item.status != "dispatched":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only dispatched supplier returns can be completed.",
            )
        item.status = "completed"
        item.completed_at = datetime.now(UTC)
        item.completed_by_user_id = actor_user_id
        if payload.supplier_reference:
            item.supplier_reference = (
                payload.supplier_reference.strip().upper()
            )
        try:
            self.records.update_return(item)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_return_completed",
                entity_type="supplier_return",
                entity_id=item.id,
                summary="Supplier return completed.",
                details={
                    "return_number": item.return_number,
                    "supplier_reference": item.supplier_reference,
                },
            )
            self.db.commit()
            return self._get_return_or_404(organization_id, item.id)
        except Exception:
            self.db.rollback()
            raise

    def cancel_supplier_return(
        self,
        organization_id: uuid.UUID,
        supplier_return_id: uuid.UUID,
        payload: CancelSupplierReturnSchema,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> SupplierReturn:
        item = self._get_return_or_404(
            organization_id,
            supplier_return_id,
            for_update=True,
        )
        self._ensure_return_draft(item)
        item.status = "cancelled"
        item.cancelled_at = datetime.now(UTC)
        item.cancelled_by_user_id = actor_user_id
        item.cancellation_reason = payload.reason
        try:
            self.records.update_return(item)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_return_cancelled",
                entity_type="supplier_return",
                entity_id=item.id,
                summary="Draft supplier return cancelled.",
                details={"reason": payload.reason},
            )
            self.db.commit()
            return self._get_return_or_404(organization_id, item.id)
        except Exception:
            self.db.rollback()
            raise


    def _validate_supplier(
        self,
        organization_id: uuid.UUID,
        supplier_id: uuid.UUID,
    ) -> Supplier:
        item = (
            self.db.query(Supplier)
            .filter(
                Supplier.id == supplier_id,
                Supplier.organization_id == organization_id,
                Supplier.is_active.is_(True),
            )
            .first()
        )
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found.",
            )
        return item

    def _calculate_debit_line(
        self,
        payload: SupplierDebitNoteLineCreate,
        *,
        position: int,
        debit_note_id: uuid.UUID,
    ) -> SupplierDebitNoteLineItem:
        quantity = self._quantity(payload.quantity)
        unit_price = self._cost(payload.unit_price)
        tax_rate = self._rate(payload.tax_rate)
        subtotal = self._money(quantity * unit_price)
        tax_amount = self._money(
            subtotal * tax_rate / Decimal("100")
        )
        return SupplierDebitNoteLineItem(
            supplier_debit_note_id=debit_note_id,
            supplier_return_line_item_id=(
                payload.supplier_return_line_item_id
            ),
            supplier_bill_line_item_id=(
                payload.supplier_bill_line_item_id
            ),
            description=payload.description.strip(),
            quantity=quantity,
            unit_of_measure=payload.unit_of_measure.strip().lower(),
            unit_price=unit_price,
            tax_rate=tax_rate,
            line_subtotal=subtotal,
            tax_amount=tax_amount,
            line_total=self._money(subtotal + tax_amount),
            position=position,
            details=dict(payload.details),
        )

    def _recalculate_debit_note(
        self,
        debit_note: SupplierDebitNote,
    ) -> None:
        self.db.flush()
        self.db.refresh(debit_note, attribute_names=["line_items"])
        debit_note.subtotal = self._money(
            sum(
                (
                    Decimal(line.line_subtotal)
                    for line in debit_note.line_items
                ),
                Decimal("0.00"),
            )
        )
        debit_note.tax_total = self._money(
            sum(
                (
                    Decimal(line.tax_amount)
                    for line in debit_note.line_items
                ),
                Decimal("0.00"),
            )
        )
        debit_note.total_amount = self._money(
            debit_note.subtotal + debit_note.tax_total
        )
        self.records.update_debit_note(debit_note)

    def _validate_debit_line_references(
        self,
        organization_id: uuid.UUID,
        debit_note: SupplierDebitNote,
        payload: SupplierDebitNoteLineCreate,
    ) -> None:
        if payload.supplier_return_line_item_id is not None:
            if debit_note.supplier_return_id is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "A return-line reference requires the debit note "
                        "to reference a supplier return."
                    ),
                )
            return_line = self.records.get_return_line(
                organization_id,
                debit_note.supplier_return_id,
                payload.supplier_return_line_item_id,
            )
            if return_line is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Supplier return line item not found.",
                )
        if payload.supplier_bill_line_item_id is not None:
            bill_line = self.records.get_supplier_bill_line(
                organization_id,
                payload.supplier_bill_line_item_id,
            )
            if bill_line is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Supplier bill line item not found.",
                )
            if bill_line.supplier_bill.supplier_id != debit_note.supplier_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Supplier bill line does not belong to the debit "
                        "note supplier."
                    ),
                )

    def create_debit_note(
        self,
        organization_id: uuid.UUID,
        payload: CreateSupplierDebitNoteSchema,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> SupplierDebitNoteResponse:
        self._validate_supplier(organization_id, payload.supplier_id)
        supplier_return = None
        if payload.supplier_return_id is not None:
            supplier_return = self._get_return_or_404(
                organization_id,
                payload.supplier_return_id,
            )
            if supplier_return.supplier_id != payload.supplier_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Supplier return and debit note must belong "
                        "to the same supplier."
                    ),
                )
            if supplier_return.status not in {
                "dispatched",
                "completed",
            }:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Only dispatched or completed supplier returns "
                        "can support a debit note."
                    ),
                )
        note_number = (
            payload.debit_note_number
            or self._generated_debit_note_number()
        ).strip().upper()
        if self.records.debit_note_number_exists(
            organization_id,
            note_number,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier debit-note number already exists.",
            )
        purchase_order_id = payload.purchase_order_id
        if supplier_return is not None:
            if (
                purchase_order_id is not None
                and purchase_order_id
                != supplier_return.purchase_order_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Debit-note purchase order must match the "
                        "supplier return."
                    ),
                )
            purchase_order_id = supplier_return.purchase_order_id
        debit_note = SupplierDebitNote(
            organization_id=organization_id,
            debit_note_number=note_number,
            supplier_id=payload.supplier_id,
            supplier_return_id=payload.supplier_return_id,
            purchase_order_id=purchase_order_id,
            note_date=payload.note_date,
            status="draft",
            currency=payload.currency.upper(),
            reason=payload.reason,
            notes=payload.notes.strip() if payload.notes else None,
            created_by_user_id=actor_user_id,
            details=dict(payload.details),
        )
        try:
            self.records.create_debit_note(debit_note)
            used_positions: set[int] = set()
            for payload_line in payload.line_items:
                self._validate_debit_line_references(
                    organization_id,
                    debit_note,
                    payload_line,
                )
                position = (
                    payload_line.position
                    if payload_line.position is not None
                    else self.records.next_debit_note_line_position(
                        debit_note.id
                    )
                )
                if position in used_positions:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="Debit-note line positions must be unique.",
                    )
                used_positions.add(position)
                self.records.add_debit_note_line(
                    self._calculate_debit_line(
                        payload_line,
                        position=position,
                        debit_note_id=debit_note.id,
                    )
                )
            self._recalculate_debit_note(debit_note)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_debit_note_created",
                entity_type="supplier_debit_note",
                entity_id=debit_note.id,
                summary="Draft supplier debit note created.",
                details={
                    "debit_note_number": note_number,
                    "supplier_id": debit_note.supplier_id,
                    "supplier_return_id": debit_note.supplier_return_id,
                    "line_count": len(payload.line_items),
                },
            )
            self.db.commit()
            return self._debit_note_response(
                self._get_debit_note_or_404(
                    organization_id,
                    debit_note.id,
                )
            )
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier debit note conflicts with an existing record.",
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def list_debit_notes(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        supplier_id: uuid.UUID | None,
        status_filter: str | None,
        search: str | None,
    ) -> SupplierDebitNoteListResponse:
        notes = self.records.list_debit_notes(
            organization_id,
            skip=skip,
            limit=limit,
            supplier_id=supplier_id,
            status_filter=status_filter,
            search=search,
        )
        return SupplierDebitNoteListResponse(
            items=[
                self._debit_note_response(note)
                for note in notes
            ],
            total=self.records.count_debit_notes(
                organization_id,
                supplier_id=supplier_id,
                status_filter=status_filter,
                search=search,
            ),
            skip=skip,
            limit=limit,
        )

    def get_debit_note(
        self,
        organization_id: uuid.UUID,
        debit_note_id: uuid.UUID,
    ) -> SupplierDebitNoteResponse:
        return self._debit_note_response(
            self._get_debit_note_or_404(
                organization_id,
                debit_note_id,
            )
        )

    def update_debit_note(
        self,
        organization_id: uuid.UUID,
        debit_note_id: uuid.UUID,
        payload: UpdateSupplierDebitNoteSchema,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> SupplierDebitNoteResponse:
        debit_note = self._get_debit_note_or_404(
            organization_id,
            debit_note_id,
            for_update=True,
        )
        self._ensure_debit_note_draft(debit_note)
        for field_name in payload.model_fields_set:
            value = getattr(payload, field_name)
            if isinstance(value, str):
                value = value.strip() or None
            setattr(debit_note, field_name, value)
        try:
            self.records.update_debit_note(debit_note)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_debit_note_updated",
                entity_type="supplier_debit_note",
                entity_id=debit_note.id,
                summary="Draft supplier debit note updated.",
                details={"changed_fields": sorted(payload.model_fields_set)},
            )
            self.db.commit()
            return self.get_debit_note(
                organization_id,
                debit_note.id,
            )
        except Exception:
            self.db.rollback()
            raise

    def add_debit_note_line(
        self,
        organization_id: uuid.UUID,
        debit_note_id: uuid.UUID,
        payload: SupplierDebitNoteLineCreate,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> SupplierDebitNoteResponse:
        debit_note = self._get_debit_note_or_404(
            organization_id,
            debit_note_id,
            for_update=True,
        )
        self._ensure_debit_note_draft(debit_note)
        self._validate_debit_line_references(
            organization_id,
            debit_note,
            payload,
        )
        position = (
            payload.position
            if payload.position is not None
            else self.records.next_debit_note_line_position(
                debit_note.id
            )
        )
        try:
            line = self._calculate_debit_line(
                payload,
                position=position,
                debit_note_id=debit_note.id,
            )
            self.records.add_debit_note_line(line)
            self._recalculate_debit_note(debit_note)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_debit_note_line_added",
                entity_type="supplier_debit_note",
                entity_id=debit_note.id,
                summary="Supplier debit-note line added.",
                details={"line_item_id": line.id},
            )
            self.db.commit()
            return self.get_debit_note(
                organization_id,
                debit_note.id,
            )
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Debit-note line position already exists.",
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def update_debit_note_line(
        self,
        organization_id: uuid.UUID,
        debit_note_id: uuid.UUID,
        line_item_id: uuid.UUID,
        payload: SupplierDebitNoteLineUpdate,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> SupplierDebitNoteResponse:
        debit_note = self._get_debit_note_or_404(
            organization_id,
            debit_note_id,
            for_update=True,
        )
        self._ensure_debit_note_draft(debit_note)
        line = self._get_debit_note_line_or_404(
            organization_id,
            debit_note_id,
            line_item_id,
            for_update=True,
        )
        for field_name in payload.model_fields_set:
            value = getattr(payload, field_name)
            if isinstance(value, str):
                value = value.strip()
            setattr(line, field_name, value)
        quantity = self._quantity(line.quantity)
        unit_price = self._cost(line.unit_price)
        tax_rate = self._rate(line.tax_rate)
        line.quantity = quantity
        line.unit_price = unit_price
        line.tax_rate = tax_rate
        line.line_subtotal = self._money(quantity * unit_price)
        line.tax_amount = self._money(
            line.line_subtotal * tax_rate / Decimal("100")
        )
        line.line_total = self._money(
            line.line_subtotal + line.tax_amount
        )
        try:
            self.records.update_debit_note_line(line)
            self._recalculate_debit_note(debit_note)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_debit_note_line_updated",
                entity_type="supplier_debit_note",
                entity_id=debit_note.id,
                summary="Supplier debit-note line updated.",
                details={
                    "line_item_id": line.id,
                    "changed_fields": sorted(payload.model_fields_set),
                },
            )
            self.db.commit()
            return self.get_debit_note(
                organization_id,
                debit_note.id,
            )
        except Exception:
            self.db.rollback()
            raise

    def delete_debit_note_line(
        self,
        organization_id: uuid.UUID,
        debit_note_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> SupplierDebitNoteResponse:
        debit_note = self._get_debit_note_or_404(
            organization_id,
            debit_note_id,
            for_update=True,
        )
        self._ensure_debit_note_draft(debit_note)
        line = self._get_debit_note_line_or_404(
            organization_id,
            debit_note_id,
            line_item_id,
            for_update=True,
        )
        try:
            self.records.delete_debit_note_line(line)
            self._recalculate_debit_note(debit_note)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_debit_note_line_removed",
                entity_type="supplier_debit_note",
                entity_id=debit_note.id,
                summary="Supplier debit-note line removed.",
                details={"line_item_id": line.id},
            )
            self.db.commit()
            return self.get_debit_note(
                organization_id,
                debit_note.id,
            )
        except Exception:
            self.db.rollback()
            raise

    def issue_debit_note(
        self,
        organization_id: uuid.UUID,
        debit_note_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> SupplierDebitNoteResponse:
        debit_note = self._get_debit_note_or_404(
            organization_id,
            debit_note_id,
            for_update=True,
        )
        self._ensure_debit_note_draft(debit_note)
        if (
            not debit_note.line_items
            or Decimal(debit_note.total_amount) <= Decimal("0")
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Supplier debit note must contain positive-value "
                    "lines before issue."
                ),
            )
        debit_note.status = "issued"
        debit_note.issued_at = datetime.now(UTC)
        debit_note.issued_by_user_id = actor_user_id
        try:
            self.records.update_debit_note(debit_note)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_debit_note_issued",
                entity_type="supplier_debit_note",
                entity_id=debit_note.id,
                summary="Supplier debit note issued.",
                details={
                    "debit_note_number": debit_note.debit_note_number,
                    "currency": debit_note.currency,
                    "total_amount": debit_note.total_amount,
                },
            )
            self.db.commit()
            return self.get_debit_note(
                organization_id,
                debit_note.id,
            )
        except Exception:
            self.db.rollback()
            raise

    def acknowledge_debit_note(
        self,
        organization_id: uuid.UUID,
        debit_note_id: uuid.UUID,
        payload: AcknowledgeSupplierDebitNoteSchema,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> SupplierDebitNoteResponse:
        debit_note = self._get_debit_note_or_404(
            organization_id,
            debit_note_id,
            for_update=True,
        )
        if debit_note.status != "issued":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only issued supplier debit notes can be acknowledged.",
            )
        if self.records.supplier_credit_reference_exists(
            organization_id,
            debit_note.supplier_id,
            payload.supplier_credit_reference,
            exclude_debit_note_id=debit_note.id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier credit reference already exists.",
            )
        debit_note.status = "acknowledged"
        debit_note.acknowledged_at = datetime.now(UTC)
        debit_note.acknowledged_by_user_id = actor_user_id
        debit_note.supplier_credit_reference = (
            payload.supplier_credit_reference
        )
        try:
            self.records.update_debit_note(debit_note)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_debit_note_acknowledged",
                entity_type="supplier_debit_note",
                entity_id=debit_note.id,
                summary="Supplier debit note acknowledged as credit.",
                details={
                    "supplier_credit_reference": (
                        debit_note.supplier_credit_reference
                    ),
                    "total_amount": debit_note.total_amount,
                },
            )
            self.db.commit()
            return self.get_debit_note(
                organization_id,
                debit_note.id,
            )
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier credit reference already exists.",
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def void_debit_note(
        self,
        organization_id: uuid.UUID,
        debit_note_id: uuid.UUID,
        payload: VoidSupplierDebitNoteSchema,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> SupplierDebitNoteResponse:
        debit_note = self._get_debit_note_or_404(
            organization_id,
            debit_note_id,
            for_update=True,
        )
        if debit_note.status == "voided":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier debit note is already voided.",
            )
        if self.records.active_settlement_total(
            debit_note.id
        ) > Decimal("0.00"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Reverse all active credit settlements before "
                    "voiding the supplier debit note."
                ),
            )
        debit_note.status = "voided"
        debit_note.voided_at = datetime.now(UTC)
        debit_note.voided_by_user_id = actor_user_id
        debit_note.void_reason = payload.reason
        try:
            self.records.update_debit_note(debit_note)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_debit_note_voided",
                entity_type="supplier_debit_note",
                entity_id=debit_note.id,
                summary="Supplier debit note voided.",
                details={"reason": payload.reason},
            )
            self.db.commit()
            return self.get_debit_note(
                organization_id,
                debit_note.id,
            )
        except Exception:
            self.db.rollback()
            raise


    def settle_debit_note(
        self,
        organization_id: uuid.UUID,
        debit_note_id: uuid.UUID,
        payload: SettleSupplierDebitNoteSchema,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> SupplierDebitNoteResponse:
        debit_note = self._get_debit_note_or_404(
            organization_id,
            debit_note_id,
            for_update=True,
        )
        if debit_note.status != "acknowledged":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only acknowledged supplier debit notes can "
                    "settle payables."
                ),
            )

        allocation_map = {
            item.supplier_bill_id: item
            for item in payload.allocations
        }
        bill_ids = sorted(allocation_map, key=str)
        bills = self.payments.get_bills_for_update(
            organization_id,
            bill_ids,
        )
        if len(bills) != len(bill_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more supplier bills were not found.",
            )

        settlement_total = self._money(
            sum(
                (
                    Decimal(item.amount_allocated)
                    for item in payload.allocations
                ),
                Decimal("0.00"),
            )
        )
        amount_used = self._money(
            self.records.active_settlement_total(debit_note.id)
        )
        available_credit = self._money(
            Decimal(debit_note.total_amount) - amount_used
        )
        if settlement_total > available_credit:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Credit settlement exceeds available debit-note credit.",
            )

        bills_by_id = {bill.id: bill for bill in bills}
        for bill_id in bill_ids:
            bill = bills_by_id[bill_id]
            allocation = self._money(
                allocation_map[bill_id].amount_allocated
            )
            if bill.status != "approved":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Only approved supplier bills can receive "
                        "credit allocations."
                    ),
                )
            if bill.supplier_id != debit_note.supplier_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "All settled bills must belong to the debit-note "
                        "supplier."
                    ),
                )
            if bill.currency.upper() != debit_note.currency.upper():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Debit-note currency must match each supplier bill."
                    ),
                )
            allocated = self._money(
                self.payments.active_allocated_total(bill.id)
            )
            outstanding = self._money(
                Decimal(bill.total_amount) - allocated
            )
            if allocation > outstanding:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Credit allocation exceeds outstanding balance "
                        f"for bill {bill.supplier_bill_number}."
                    ),
                )

        payment = SupplierPayment(
            organization_id=organization_id,
            payment_number=self._generated_credit_payment_number(),
            supplier_id=debit_note.supplier_id,
            payment_date=payload.settlement_date,
            payment_method="other",
            currency=debit_note.currency,
            total_amount=settlement_total,
            reference_number=(
                f"{debit_note.debit_note_number}-"
                f"{uuid.uuid4().hex[:8].upper()}"
            ),
            status="posted",
            recorded_by_user_id=actor_user_id,
            notes=payload.notes,
            details={
                **dict(payload.details),
                "settlement_type": "supplier_credit",
                "supplier_debit_note_id": str(debit_note.id),
                "supplier_credit_reference": (
                    debit_note.supplier_credit_reference
                ),
            },
        )
        allocations = [
            SupplierPaymentAllocation(
                supplier_payment=payment,
                supplier_bill_id=bill_id,
                amount_allocated=self._money(
                    allocation_map[bill_id].amount_allocated
                ),
                position=position,
                notes=allocation_map[bill_id].notes,
                details={
                    **dict(allocation_map[bill_id].details),
                    "settlement_type": "supplier_credit",
                    "supplier_debit_note_id": str(debit_note.id),
                },
            )
            for position, bill_id in enumerate(bill_ids)
        ]
        settlement = SupplierCreditSettlement(
            organization_id=organization_id,
            supplier_debit_note_id=debit_note.id,
            supplier_payment=payment,
            amount_settled=settlement_total,
            position=self.records.next_settlement_position(
                debit_note.id
            ),
            created_by_user_id=actor_user_id,
            details={
                "supplier_credit_reference": (
                    debit_note.supplier_credit_reference
                ),
                "supplier_bill_ids": [
                    str(bill_id)
                    for bill_id in bill_ids
                ],
            },
        )
        try:
            self.payments.create_payment(payment)
            self.payments.add_allocations(allocations)
            self.records.create_settlement(settlement)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_credit_settled",
                entity_type="supplier_debit_note",
                entity_id=debit_note.id,
                summary="Supplier debit-note credit settled against payables.",
                details={
                    "payment_id": payment.id,
                    "payment_number": payment.payment_number,
                    "amount_settled": settlement_total,
                    "supplier_bill_ids": bill_ids,
                },
            )
            self.db.commit()
            return self.get_debit_note(
                organization_id,
                debit_note.id,
            )
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier credit settlement conflicts with existing data.",
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def reverse_credit_settlement(
        self,
        organization_id: uuid.UUID,
        debit_note_id: uuid.UUID,
        settlement_id: uuid.UUID,
        payload: ReverseSupplierCreditSettlementSchema,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> SupplierDebitNoteResponse:
        debit_note = self._get_debit_note_or_404(
            organization_id,
            debit_note_id,
            for_update=True,
        )
        settlement = self.records.get_settlement(
            organization_id,
            debit_note.id,
            settlement_id,
            for_update=True,
        )
        if settlement is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier credit settlement not found.",
            )
        payment = (
            self.db.query(SupplierPayment)
            .populate_existing()
            .filter(
                SupplierPayment.id == settlement.supplier_payment_id,
                SupplierPayment.organization_id == organization_id,
            )
            .with_for_update(of=SupplierPayment)
            .first()
        )
        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Linked supplier payment is unavailable.",
            )
        if payment.status == "reversed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier credit settlement is already reversed.",
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
                action="supplier_credit_settlement_reversed",
                entity_type="supplier_debit_note",
                entity_id=debit_note.id,
                summary="Supplier credit settlement reversed.",
                details={
                    "settlement_id": settlement.id,
                    "payment_id": payment.id,
                    "amount_settled": settlement.amount_settled,
                    "reason": payload.reason,
                },
            )
            self.db.commit()
            return self.get_debit_note(
                organization_id,
                debit_note.id,
            )
        except Exception:
            self.db.rollback()
            raise

    def list_credit_settlements(
        self,
        organization_id: uuid.UUID,
        debit_note_id: uuid.UUID,
    ) -> list[SupplierCreditSettlementResponse]:
        debit_note = self._get_debit_note_or_404(
            organization_id,
            debit_note_id,
        )
        return [
            self._settlement_response(settlement)
            for settlement in debit_note.settlements
        ]

    @staticmethod
    def _settlement_response(
        settlement: SupplierCreditSettlement,
    ) -> SupplierCreditSettlementResponse:
        payment = settlement.supplier_payment
        return SupplierCreditSettlementResponse(
            id=settlement.id,
            supplier_payment_id=payment.id,
            payment_number=payment.payment_number,
            amount_settled=settlement.amount_settled,
            settlement_date=payment.payment_date,
            status=payment.status,
            reversed_at=payment.reversed_at,
            reversal_reason=payment.reversal_reason,
            position=settlement.position,
            details=dict(settlement.details),
            created_at=settlement.created_at,
        )

    def _debit_note_response(
        self,
        debit_note: SupplierDebitNote,
    ) -> SupplierDebitNoteResponse:
        settlements = [
            self._settlement_response(settlement)
            for settlement in debit_note.settlements
        ]
        amount_settled = self._money(
            sum(
                (
                    Decimal(item.amount_settled)
                    for item in debit_note.settlements
                    if item.supplier_payment.status == "posted"
                ),
                Decimal("0.00"),
            )
        )
        available_credit = max(
            self._money(
                Decimal(debit_note.total_amount) - amount_settled
            ),
            Decimal("0.00"),
        )
        if amount_settled == Decimal("0.00"):
            settlement_status = "unsettled"
        elif available_credit == Decimal("0.00"):
            settlement_status = "fully_settled"
        else:
            settlement_status = "partially_settled"
        return SupplierDebitNoteResponse(
            id=debit_note.id,
            organization_id=debit_note.organization_id,
            debit_note_number=debit_note.debit_note_number,
            supplier_id=debit_note.supplier_id,
            supplier_return_id=debit_note.supplier_return_id,
            purchase_order_id=debit_note.purchase_order_id,
            note_date=debit_note.note_date,
            status=debit_note.status,
            currency=debit_note.currency,
            supplier_credit_reference=(
                debit_note.supplier_credit_reference
            ),
            reason=debit_note.reason,
            subtotal=debit_note.subtotal,
            tax_total=debit_note.tax_total,
            total_amount=debit_note.total_amount,
            amount_settled=amount_settled,
            available_credit=available_credit,
            settlement_status=settlement_status,
            notes=debit_note.notes,
            issued_at=debit_note.issued_at,
            acknowledged_at=debit_note.acknowledged_at,
            voided_at=debit_note.voided_at,
            void_reason=debit_note.void_reason,
            details=dict(debit_note.details),
            line_items=debit_note.line_items,
            settlements=settlements,
            created_at=debit_note.created_at,
            updated_at=debit_note.updated_at,
        )
