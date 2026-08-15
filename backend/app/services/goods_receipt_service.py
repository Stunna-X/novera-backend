"""
Goods receipt business logic.

Draft maintenance and posting are organization-scoped. Posting locks the
receipt, purchase order, order lines, and inventory balances so accepted
stock, purchase-order progress, movement-ledger rows, and audit events
commit or roll back as one transaction.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.goods_receipt import (
    GoodsReceipt,
    GoodsReceiptLineItem,
)
from app.models.inventory import (
    InventoryBalance,
    InventoryMovement,
)
from app.models.purchase_order import (
    PurchaseOrder,
    PurchaseOrderLineItem,
)
from app.repositories.goods_receipt import GoodsReceiptRepository
from app.repositories.inventory import InventoryRepository
from app.repositories.purchase_order import PurchaseOrderRepository
from app.schemas.audit_log import AuditLogCreate
from app.schemas.goods_receipt import (
    CancelGoodsReceiptSchema,
    CreateGoodsReceiptSchema,
    GoodsReceiptLineCreate,
    GoodsReceiptLineUpdate,
    GoodsReceiptListResponse,
    UpdateGoodsReceiptSchema,
)
from app.services.audit_log_service import AuditLogService
from app.services.purchase_order_service import PurchaseOrderService


QUANTITY_QUANTIZER = Decimal("0.001")
COST_QUANTIZER = Decimal("0.0001")
RECEIVABLE_PURCHASE_ORDER_STATUSES = {
    "issued",
    "acknowledged",
    "partially_received",
}


class GoodsReceiptService:
    """Handle organization-scoped goods receipts."""

    def __init__(self, db: Session):
        self.db = db
        self.goods_receipts = GoodsReceiptRepository(db)
        self.purchase_orders = PurchaseOrderRepository(db)
        self.inventory = InventoryRepository(db)
        self.audit_logs = AuditLogService(db)
        self.purchase_order_service = PurchaseOrderService(db)

    def _get_or_404(
        self,
        organization_id: uuid.UUID,
        goods_receipt_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> GoodsReceipt:
        receipt = self.goods_receipts.get_for_organization(
            organization_id,
            goods_receipt_id,
            include_inactive=include_inactive,
            for_update=for_update,
        )

        if receipt is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Goods receipt not found.",
            )

        return receipt

    def _get_line_or_404(
        self,
        organization_id: uuid.UUID,
        goods_receipt_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> GoodsReceiptLineItem:
        line = self.goods_receipts.get_line_item(
            organization_id,
            goods_receipt_id,
            line_item_id,
            for_update=for_update,
        )

        if line is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Goods receipt line item not found.",
            )

        return line

    @staticmethod
    def _ensure_draft(receipt: GoodsReceipt) -> None:
        if receipt.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only draft goods receipts can be changed.",
            )

    def _get_purchase_order_or_404(
        self,
        organization_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> PurchaseOrder:
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

    @staticmethod
    def _ensure_purchase_order_receivable(
        purchase_order: PurchaseOrder,
    ) -> None:
        if purchase_order.status not in RECEIVABLE_PURCHASE_ORDER_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Goods can only be received against an issued, "
                    "acknowledged, or partially received purchase order."
                ),
            )

    def _validate_location(
        self,
        organization_id: uuid.UUID,
        location_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> None:
        location = self.inventory.get_location_for_organization(
            organization_id,
            location_id,
            for_update=for_update,
        )

        if location is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Receiving inventory location not found.",
            )

    def _get_purchase_order_line_or_404(
        self,
        organization_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> PurchaseOrderLineItem:
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

    @staticmethod
    def _quantity(value: Decimal) -> Decimal:
        return Decimal(value).quantize(
            QUANTITY_QUANTIZER,
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _cost(value: Decimal) -> Decimal:
        return Decimal(value).quantize(
            COST_QUANTIZER,
            rounding=ROUND_HALF_UP,
        )

    @classmethod
    def _weighted_average_cost(
        cls,
        *,
        existing_quantity: Decimal,
        existing_unit_cost: Decimal,
        incoming_quantity: Decimal,
        incoming_unit_cost: Decimal,
    ) -> Decimal:
        final_quantity = (
            Decimal(existing_quantity) + Decimal(incoming_quantity)
        )

        if final_quantity <= Decimal("0"):
            return Decimal("0.0000")

        total_value = (
            Decimal(existing_quantity) * Decimal(existing_unit_cost)
            + Decimal(incoming_quantity) * Decimal(incoming_unit_cost)
        )

        return cls._cost(total_value / final_quantity)

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, uuid.UUID):
            return str(value)

        if isinstance(value, Decimal):
            return str(value)

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, dict):
            return {
                str(key): GoodsReceiptService._json_safe(nested)
                for key, nested in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            return [
                GoodsReceiptService._json_safe(nested)
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
        entity_type: str,
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
                entity_type=entity_type,
                entity_id=entity_id,
                summary=summary,
                status="success",
                details=self._json_safe(details or {}),
            ),
            commit=False,
        )

    @staticmethod
    def _generated_number() -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        return f"GR-{timestamp}-{uuid.uuid4().hex[:8].upper()}"

    def _ensure_number_available(
        self,
        organization_id: uuid.UUID,
        goods_receipt_number: str,
    ) -> None:
        if self.goods_receipts.number_exists(
            organization_id,
            goods_receipt_number,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another goods receipt in this organization "
                    "already uses this number."
                ),
            )

    @staticmethod
    def _validate_line_quantities(
        *,
        quantity_accepted: Decimal,
        quantity_rejected: Decimal,
        quantity_damaged: Decimal,
        rejection_reason: str | None,
        damage_notes: str | None,
    ) -> None:
        total = (
            quantity_accepted
            + quantity_rejected
            + quantity_damaged
        )

        if total <= Decimal("0"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "At least one delivered quantity must be "
                    "greater than zero."
                ),
            )

        if quantity_rejected > Decimal("0") and not rejection_reason:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "A rejection reason is required for rejected "
                    "quantity."
                ),
            )

        if quantity_damaged > Decimal("0") and not damage_notes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Damage notes are required for damaged quantity."
                ),
            )

    def _build_line(
        self,
        *,
        organization_id: uuid.UUID,
        receipt: GoodsReceipt,
        payload: GoodsReceiptLineCreate,
        position: int,
    ) -> GoodsReceiptLineItem:
        if self.goods_receipts.purchase_order_line_exists(
            receipt.id,
            payload.purchase_order_line_item_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This purchase-order line is already included "
                    "in the goods receipt."
                ),
            )

        purchase_order_line = self._get_purchase_order_line_or_404(
            organization_id,
            receipt.purchase_order_id,
            payload.purchase_order_line_item_id,
        )

        quantity_accepted = self._quantity(payload.quantity_accepted)
        quantity_rejected = self._quantity(payload.quantity_rejected)
        quantity_damaged = self._quantity(payload.quantity_damaged)

        self._validate_line_quantities(
            quantity_accepted=quantity_accepted,
            quantity_rejected=quantity_rejected,
            quantity_damaged=quantity_damaged,
            rejection_reason=payload.rejection_reason,
            damage_notes=payload.damage_notes,
        )

        outstanding = self._quantity(
            Decimal(purchase_order_line.quantity_ordered)
            - Decimal(purchase_order_line.quantity_received)
        )

        if quantity_accepted > outstanding:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Accepted quantity exceeds the purchase-order "
                    "line's outstanding quantity."
                ),
            )

        unit_cost = self._cost(
            payload.unit_cost
            if payload.unit_cost is not None
            else Decimal(purchase_order_line.unit_price)
        )

        return GoodsReceiptLineItem(
            goods_receipt_id=receipt.id,
            purchase_order_line_item_id=purchase_order_line.id,
            inventory_item_id=purchase_order_line.inventory_item_id,
            description=purchase_order_line.description,
            quantity_accepted=quantity_accepted,
            quantity_rejected=quantity_rejected,
            quantity_damaged=quantity_damaged,
            unit_of_measure=purchase_order_line.unit_of_measure,
            unit_cost=unit_cost,
            currency=receipt.purchase_order.currency,
            rejection_reason=payload.rejection_reason,
            damage_notes=payload.damage_notes,
            position=position,
            details=payload.details,
        )

    def _reload(
        self,
        organization_id: uuid.UUID,
        goods_receipt_id: uuid.UUID,
    ) -> GoodsReceipt:
        return self._get_or_404(
            organization_id,
            goods_receipt_id,
        )

    def _rollback_conflict(self, exc: IntegrityError) -> None:
        self.db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The goods receipt conflicts with an existing "
                "organization record."
            ),
        ) from exc

    def create_goods_receipt(
        self,
        organization_id: uuid.UUID,
        payload: CreateGoodsReceiptSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> GoodsReceipt:
        purchase_order = self._get_purchase_order_or_404(
            organization_id,
            payload.purchase_order_id,
        )
        self._ensure_purchase_order_receivable(purchase_order)
        self._validate_location(
            organization_id,
            payload.receiving_location_id,
        )

        goods_receipt_number = (
            payload.goods_receipt_number or self._generated_number()
        )
        self._ensure_number_available(
            organization_id,
            goods_receipt_number,
        )

        receipt = GoodsReceipt(
            organization_id=organization_id,
            goods_receipt_number=goods_receipt_number,
            purchase_order_id=purchase_order.id,
            purchase_order=purchase_order,
            supplier_id=purchase_order.supplier_id,
            supplier=purchase_order.supplier,
            receiving_location_id=payload.receiving_location_id,
            status="draft",
            received_at=payload.received_at,
            supplier_delivery_note=payload.supplier_delivery_note,
            carrier_name=payload.carrier_name,
            vehicle_reference=payload.vehicle_reference,
            notes=payload.notes,
            created_by_user_id=actor_user_id,
            details=payload.details,
        )

        try:
            created = self.goods_receipts.create(receipt)

            used_positions: set[int] = set()

            for line_payload in payload.line_items:
                position = (
                    line_payload.position
                    if line_payload.position is not None
                    else self.goods_receipts.next_position(created.id)
                )

                if position in used_positions:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="Receipt line positions must be unique.",
                    )

                used_positions.add(position)
                self.goods_receipts.add_line_item(
                    self._build_line(
                        organization_id=organization_id,
                        receipt=created,
                        payload=line_payload,
                        position=position,
                    )
                )

            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="goods_receipt_created",
                entity_type="goods_receipt",
                entity_id=created.id,
                summary="Draft goods receipt created.",
                details={
                    "purchase_order_id": purchase_order.id,
                    "purchase_order_number": (
                        purchase_order.purchase_order_number
                    ),
                    "line_count": len(payload.line_items),
                },
            )

            receipt_id = created.id
            self.db.commit()
            return self._reload(organization_id, receipt_id)

        except IntegrityError as exc:
            self._rollback_conflict(exc)

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def list_goods_receipts(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        status_filter: str | None = None,
        purchase_order_id: uuid.UUID | None = None,
        supplier_id: uuid.UUID | None = None,
        receiving_location_id: uuid.UUID | None = None,
        received_from: datetime | None = None,
        received_to: datetime | None = None,
        include_inactive: bool = False,
    ) -> GoodsReceiptListResponse:
        if (
            received_from is not None
            and received_to is not None
            and received_from > received_to
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="received_from cannot be later than received_to.",
            )

        items = self.goods_receipts.list_for_organization(
            organization_id,
            skip=skip,
            limit=limit,
            search=search,
            status_filter=status_filter,
            purchase_order_id=purchase_order_id,
            supplier_id=supplier_id,
            receiving_location_id=receiving_location_id,
            received_from=received_from,
            received_to=received_to,
            include_inactive=include_inactive,
        )
        total = self.goods_receipts.count_for_organization(
            organization_id,
            search=search,
            status_filter=status_filter,
            purchase_order_id=purchase_order_id,
            supplier_id=supplier_id,
            receiving_location_id=receiving_location_id,
            received_from=received_from,
            received_to=received_to,
            include_inactive=include_inactive,
        )

        return GoodsReceiptListResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_goods_receipt(
        self,
        organization_id: uuid.UUID,
        goods_receipt_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> GoodsReceipt:
        return self._get_or_404(
            organization_id,
            goods_receipt_id,
            include_inactive=include_inactive,
        )

    def update_goods_receipt(
        self,
        organization_id: uuid.UUID,
        goods_receipt_id: uuid.UUID,
        payload: UpdateGoodsReceiptSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> GoodsReceipt:
        receipt = self._get_or_404(
            organization_id,
            goods_receipt_id,
            for_update=True,
        )
        self._ensure_draft(receipt)

        update_data = payload.model_dump(exclude_unset=True)

        if "receiving_location_id" in update_data:
            self._validate_location(
                organization_id,
                update_data["receiving_location_id"],
            )

        for field_name, value in update_data.items():
            setattr(receipt, field_name, value)

        try:
            self.goods_receipts.update(receipt)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="goods_receipt_updated",
                entity_type="goods_receipt",
                entity_id=receipt.id,
                summary="Draft goods receipt updated.",
                details={"changed_fields": sorted(update_data)},
            )
            receipt_id = receipt.id
            self.db.commit()
            return self._reload(organization_id, receipt_id)

        except IntegrityError as exc:
            self._rollback_conflict(exc)

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def add_line_item(
        self,
        organization_id: uuid.UUID,
        goods_receipt_id: uuid.UUID,
        payload: GoodsReceiptLineCreate,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> GoodsReceipt:
        receipt = self._get_or_404(
            organization_id,
            goods_receipt_id,
            for_update=True,
        )
        self._ensure_draft(receipt)

        position = (
            payload.position
            if payload.position is not None
            else self.goods_receipts.next_position(receipt.id)
        )

        try:
            line = self.goods_receipts.add_line_item(
                self._build_line(
                    organization_id=organization_id,
                    receipt=receipt,
                    payload=payload,
                    position=position,
                )
            )
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="goods_receipt_line_added",
                entity_type="goods_receipt",
                entity_id=receipt.id,
                summary="Goods receipt line added.",
                details={
                    "line_item_id": line.id,
                    "purchase_order_line_item_id": (
                        line.purchase_order_line_item_id
                    ),
                },
            )
            receipt_id = receipt.id
            self.db.commit()
            return self._reload(organization_id, receipt_id)

        except IntegrityError as exc:
            self._rollback_conflict(exc)

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def update_line_item(
        self,
        organization_id: uuid.UUID,
        goods_receipt_id: uuid.UUID,
        line_item_id: uuid.UUID,
        payload: GoodsReceiptLineUpdate,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> GoodsReceipt:
        receipt = self._get_or_404(
            organization_id,
            goods_receipt_id,
            for_update=True,
        )
        self._ensure_draft(receipt)
        line = self._get_line_or_404(
            organization_id,
            goods_receipt_id,
            line_item_id,
            for_update=True,
        )
        purchase_order_line = self._get_purchase_order_line_or_404(
            organization_id,
            receipt.purchase_order_id,
            line.purchase_order_line_item_id,
        )

        update_data = payload.model_dump(exclude_unset=True)

        for field_name, value in update_data.items():
            setattr(line, field_name, value)

        line.quantity_accepted = self._quantity(line.quantity_accepted)
        line.quantity_rejected = self._quantity(line.quantity_rejected)
        line.quantity_damaged = self._quantity(line.quantity_damaged)
        line.unit_cost = self._cost(line.unit_cost)

        self._validate_line_quantities(
            quantity_accepted=line.quantity_accepted,
            quantity_rejected=line.quantity_rejected,
            quantity_damaged=line.quantity_damaged,
            rejection_reason=line.rejection_reason,
            damage_notes=line.damage_notes,
        )

        outstanding = self._quantity(
            Decimal(purchase_order_line.quantity_ordered)
            - Decimal(purchase_order_line.quantity_received)
        )

        if line.quantity_accepted > outstanding:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Accepted quantity exceeds the purchase-order "
                    "line's outstanding quantity."
                ),
            )

        try:
            self.goods_receipts.update_line_item(line)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="goods_receipt_line_updated",
                entity_type="goods_receipt",
                entity_id=receipt.id,
                summary="Goods receipt line updated.",
                details={
                    "line_item_id": line.id,
                    "changed_fields": sorted(update_data),
                },
            )
            receipt_id = receipt.id
            self.db.commit()
            return self._reload(organization_id, receipt_id)

        except IntegrityError as exc:
            self._rollback_conflict(exc)

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def delete_line_item(
        self,
        organization_id: uuid.UUID,
        goods_receipt_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> GoodsReceipt:
        receipt = self._get_or_404(
            organization_id,
            goods_receipt_id,
            for_update=True,
        )
        self._ensure_draft(receipt)
        line = self._get_line_or_404(
            organization_id,
            goods_receipt_id,
            line_item_id,
            for_update=True,
        )

        try:
            deleted_line_id = line.id
            self.goods_receipts.delete_line_item(line)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="goods_receipt_line_removed",
                entity_type="goods_receipt",
                entity_id=receipt.id,
                summary="Goods receipt line removed.",
                details={"line_item_id": deleted_line_id},
            )
            receipt_id = receipt.id
            self.db.commit()
            return self._reload(organization_id, receipt_id)

        except IntegrityError as exc:
            self._rollback_conflict(exc)

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def _get_balance_for_update(
        self,
        *,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> InventoryBalance:
        balance = self.inventory.get_balance_for_organization(
            organization_id,
            item_id,
            location_id,
            for_update=True,
        )

        if balance is not None:
            return balance

        return self.inventory.create_balance(
            InventoryBalance(
                organization_id=organization_id,
                item_id=item_id,
                location_id=location_id,
                quantity_on_hand=Decimal("0.000"),
                quantity_reserved=Decimal("0.000"),
                average_unit_cost=Decimal("0.0000"),
            )
        )

    def _post_inventory_line(
        self,
        *,
        organization_id: uuid.UUID,
        receipt: GoodsReceipt,
        receipt_line: GoodsReceiptLineItem,
        purchase_order: PurchaseOrder,
        purchase_order_line: PurchaseOrderLineItem,
        occurred_at: datetime,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> None:
        quantity = self._quantity(receipt_line.quantity_accepted)

        if quantity <= Decimal("0"):
            return

        if receipt_line.inventory_item_id is None:
            return

        if (
            purchase_order_line.inventory_item_id
            != receipt_line.inventory_item_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The goods-receipt inventory item no longer "
                    "matches its purchase-order line."
                ),
            )

        item = self.inventory.get_item_for_organization(
            organization_id,
            receipt_line.inventory_item_id,
            for_update=True,
        )

        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inventory item not found.",
            )

        currency = purchase_order.currency.strip().upper()
        item_currency = item.currency.strip().upper()

        if currency != item_currency:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Purchase-order currency must match the inventory "
                    "item currency before accepted stock can be posted."
                ),
            )

        balance = self._get_balance_for_update(
            organization_id=organization_id,
            item_id=item.id,
            location_id=receipt.receiving_location_id,
        )

        quantity_before = self._quantity(balance.quantity_on_hand)
        quantity_after = self._quantity(quantity_before + quantity)
        unit_cost = self._cost(receipt_line.unit_cost)

        balance.quantity_on_hand = quantity_after
        balance.average_unit_cost = self._weighted_average_cost(
            existing_quantity=quantity_before,
            existing_unit_cost=Decimal(balance.average_unit_cost),
            incoming_quantity=quantity,
            incoming_unit_cost=unit_cost,
        )
        balance.last_movement_at = occurred_at
        self.inventory.update_balance(balance)

        movement = self.inventory.create_movement(
            InventoryMovement(
                organization_id=organization_id,
                item_id=item.id,
                location_id=receipt.receiving_location_id,
                movement_type="receipt",
                quantity=quantity,
                quantity_delta=quantity,
                quantity_before=quantity_before,
                quantity_after=quantity_after,
                unit_cost=unit_cost,
                currency=currency,
                reference_type="goods_receipt",
                reference_id=str(receipt.id),
                occurred_at=occurred_at,
                notes=(
                    f"Posted from goods receipt "
                    f"{receipt.goods_receipt_number}."
                ),
                created_by_user_id=actor_user_id,
                details={
                    "goods_receipt_id": str(receipt.id),
                    "goods_receipt_line_item_id": str(receipt_line.id),
                    "purchase_order_id": str(purchase_order.id),
                    "purchase_order_line_item_id": str(
                        purchase_order_line.id
                    ),
                    "supplier_id": str(receipt.supplier_id),
                    "operation": "goods_receipt_post",
                },
            )
        )
        receipt_line.inventory_movement_id = movement.id
        self.goods_receipts.update_line_item(receipt_line)

        self._record_audit(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            action="inventory_stock_received",
            entity_type="inventory_movement",
            entity_id=movement.id,
            summary="Inventory stock received from a goods receipt.",
            details={
                "goods_receipt_id": receipt.id,
                "purchase_order_id": purchase_order.id,
                "item_id": item.id,
                "location_id": receipt.receiving_location_id,
                "quantity": quantity,
            },
        )

    def post_goods_receipt(
        self,
        organization_id: uuid.UUID,
        goods_receipt_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> GoodsReceipt:
        receipt = self._get_or_404(
            organization_id,
            goods_receipt_id,
            for_update=True,
        )
        self._ensure_draft(receipt)
        self._validate_location(
            organization_id,
            receipt.receiving_location_id,
            for_update=True,
        )

        purchase_order = self._get_purchase_order_or_404(
            organization_id,
            receipt.purchase_order_id,
            for_update=True,
        )
        self._ensure_purchase_order_receivable(purchase_order)

        if purchase_order.supplier_id != receipt.supplier_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The goods receipt supplier no longer matches "
                    "the purchase order."
                ),
            )

        receipt_lines = self.goods_receipts.list_line_items_for_update(
            receipt.id
        )

        if not receipt_lines:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A goods receipt must contain at least one line "
                    "before it can be posted."
                ),
            )

        occurred_at = receipt.received_at or datetime.now(UTC)
        previous_purchase_order_status = purchase_order.status

        try:
            for receipt_line in receipt_lines:
                purchase_order_line = (
                    self._get_purchase_order_line_or_404(
                        organization_id,
                        purchase_order.id,
                        receipt_line.purchase_order_line_item_id,
                        for_update=True,
                    )
                )

                quantity_accepted = self._quantity(
                    receipt_line.quantity_accepted
                )
                quantity_rejected = self._quantity(
                    receipt_line.quantity_rejected
                )
                quantity_damaged = self._quantity(
                    receipt_line.quantity_damaged
                )

                self._validate_line_quantities(
                    quantity_accepted=quantity_accepted,
                    quantity_rejected=quantity_rejected,
                    quantity_damaged=quantity_damaged,
                    rejection_reason=receipt_line.rejection_reason,
                    damage_notes=receipt_line.damage_notes,
                )

                outstanding = self._quantity(
                    Decimal(purchase_order_line.quantity_ordered)
                    - Decimal(purchase_order_line.quantity_received)
                )

                if quantity_accepted > outstanding:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Accepted quantity exceeds the current "
                            "outstanding purchase-order quantity."
                        ),
                    )

                if quantity_accepted > Decimal("0"):
                    purchase_order_line.quantity_received = (
                        self._quantity(
                            Decimal(
                                purchase_order_line.quantity_received
                            )
                            + quantity_accepted
                        )
                    )
                    self.purchase_orders.update_line_item(
                        purchase_order_line
                    )

                self._post_inventory_line(
                    organization_id=organization_id,
                    receipt=receipt,
                    receipt_line=receipt_line,
                    purchase_order=purchase_order,
                    purchase_order_line=purchase_order_line,
                    occurred_at=occurred_at,
                    actor_user_id=actor_user_id,
                    actor_membership_id=actor_membership_id,
                )

            self.purchase_order_service.synchronize_receipt_status(
                purchase_order
            )
            self.purchase_orders.update(purchase_order)

            receipt.status = "posted"
            receipt.received_at = occurred_at
            receipt.posted_at = datetime.now(UTC)
            receipt.posted_by_user_id = actor_user_id
            self.goods_receipts.update(receipt)

            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="goods_receipt_posted",
                entity_type="goods_receipt",
                entity_id=receipt.id,
                summary="Goods receipt posted.",
                details={
                    "purchase_order_id": purchase_order.id,
                    "purchase_order_number": (
                        purchase_order.purchase_order_number
                    ),
                    "purchase_order_status_before": (
                        previous_purchase_order_status
                    ),
                    "purchase_order_status_after": (
                        purchase_order.status
                    ),
                    "total_accepted_quantity": sum(
                        (
                            Decimal(line.quantity_accepted)
                            for line in receipt_lines
                        ),
                        start=Decimal("0.000"),
                    ),
                    "total_rejected_quantity": sum(
                        (
                            Decimal(line.quantity_rejected)
                            for line in receipt_lines
                        ),
                        start=Decimal("0.000"),
                    ),
                    "total_damaged_quantity": sum(
                        (
                            Decimal(line.quantity_damaged)
                            for line in receipt_lines
                        ),
                        start=Decimal("0.000"),
                    ),
                    "line_count": len(receipt_lines),
                },
            )

            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="purchase_order_receipt_progress_updated",
                entity_type="purchase_order",
                entity_id=purchase_order.id,
                summary=(
                    "Purchase-order receipt progress updated from a "
                    "posted goods receipt."
                ),
                details={
                    "goods_receipt_id": receipt.id,
                    "from_status": previous_purchase_order_status,
                    "to_status": purchase_order.status,
                },
            )

            receipt_id = receipt.id
            self.db.commit()
            return self._reload(organization_id, receipt_id)

        except IntegrityError as exc:
            self._rollback_conflict(exc)

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def cancel_goods_receipt(
        self,
        organization_id: uuid.UUID,
        goods_receipt_id: uuid.UUID,
        payload: CancelGoodsReceiptSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> GoodsReceipt:
        receipt = self._get_or_404(
            organization_id,
            goods_receipt_id,
            for_update=True,
        )
        self._ensure_draft(receipt)

        receipt.status = "cancelled"
        receipt.cancelled_at = datetime.now(UTC)
        receipt.cancelled_by_user_id = actor_user_id
        receipt.cancellation_reason = payload.reason

        try:
            self.goods_receipts.update(receipt)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="goods_receipt_cancelled",
                entity_type="goods_receipt",
                entity_id=receipt.id,
                summary="Draft goods receipt cancelled.",
                details={"reason": payload.reason},
            )
            receipt_id = receipt.id
            self.db.commit()
            return self._reload(organization_id, receipt_id)

        except IntegrityError as exc:
            self._rollback_conflict(exc)

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise
