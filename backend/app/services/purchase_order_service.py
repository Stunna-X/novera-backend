"""
Purchase order business logic.

Creation, requisition conversion, commercial calculations, workflow
changes, and immutable audit events are committed atomically.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.inventory import InventoryItem, InventoryLocation
from app.models.purchase_order import (
    PurchaseOrder,
    PurchaseOrderLineItem,
)
from app.models.purchase_requisition import PurchaseRequisition
from app.models.supplier import Supplier
from app.repositories.purchase_order import PurchaseOrderRepository
from app.repositories.purchase_requisition import (
    PurchaseRequisitionRepository,
)
from app.schemas.audit_log import AuditLogCreate
from app.schemas.purchase_order import (
    AcknowledgePurchaseOrderSchema,
    CancelPurchaseOrderSchema,
    ConvertRequisitionToPurchaseOrderSchema,
    CreatePurchaseOrderSchema,
    PurchaseOrderLineCreate,
    PurchaseOrderLineUpdate,
    PurchaseOrderListResponse,
    UpdatePurchaseOrderSchema,
)
from app.services.audit_log_service import AuditLogService


CANCELLABLE_STATUSES = {
    "draft",
    "issued",
    "acknowledged",
}


class PurchaseOrderService:
    """Handle organization-scoped purchase orders."""

    def __init__(self, db: Session):
        self.db = db
        self.purchase_orders = PurchaseOrderRepository(db)
        self.requisitions = PurchaseRequisitionRepository(db)
        self.audit_logs = AuditLogService(db)

    def _get_or_404(
        self,
        organization_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> PurchaseOrder:
        purchase_order = self.purchase_orders.get_for_organization(
            organization_id,
            purchase_order_id,
            include_inactive=include_inactive,
            for_update=for_update,
        )

        if purchase_order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase order not found.",
            )

        return purchase_order

    def _get_line_or_404(
        self,
        organization_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> PurchaseOrderLineItem:
        line_item = self.purchase_orders.get_line_item(
            organization_id,
            purchase_order_id,
            line_item_id,
            for_update=for_update,
        )

        if line_item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase order line item not found.",
            )

        return line_item

    @staticmethod
    def _ensure_draft(purchase_order: PurchaseOrder) -> None:
        if purchase_order.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only draft purchase orders can be edited.",
            )

    def _get_supplier_or_404(
        self,
        organization_id: uuid.UUID,
        supplier_id: uuid.UUID,
    ) -> Supplier:
        supplier = (
            self.db.query(Supplier)
            .filter(
                Supplier.id == supplier_id,
                Supplier.organization_id == organization_id,
                Supplier.is_active.is_(True),
            )
            .first()
        )

        if supplier is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found.",
            )

        return supplier

    def _validate_location(
        self,
        organization_id: uuid.UUID,
        location_id: uuid.UUID | None,
    ) -> None:
        if location_id is None:
            return

        exists = (
            self.db.query(InventoryLocation.id)
            .filter(
                InventoryLocation.id == location_id,
                InventoryLocation.organization_id
                == organization_id,
                InventoryLocation.is_active.is_(True),
            )
            .first()
        )

        if exists is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inventory delivery location not found.",
            )

    def _validate_inventory_item(
        self,
        organization_id: uuid.UUID,
        inventory_item_id: uuid.UUID | None,
    ) -> None:
        if inventory_item_id is None:
            return

        exists = (
            self.db.query(InventoryItem.id)
            .filter(
                InventoryItem.id == inventory_item_id,
                InventoryItem.organization_id == organization_id,
                InventoryItem.is_active.is_(True),
            )
            .first()
        )

        if exists is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inventory item not found.",
            )

    @staticmethod
    def _supplier_snapshot(supplier: Supplier) -> dict[str, Any]:
        return {
            "supplier_name": supplier.name,
            "supplier_email": supplier.email,
            "supplier_phone": supplier.phone,
            "supplier_tax_id": supplier.tax_id,
        }

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    @classmethod
    def _calculate_line(cls, line: PurchaseOrderLineItem) -> None:
        subtotal = cls._money(
            line.quantity_ordered * line.unit_price
        )

        if line.discount_amount > subtotal:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Line discount cannot exceed the line subtotal."
                ),
            )

        taxable_amount = subtotal - line.discount_amount
        tax_amount = cls._money(
            taxable_amount
            * line.tax_rate
            / Decimal("100")
        )

        line.line_subtotal = subtotal
        line.tax_amount = tax_amount
        line.line_total = cls._money(
            taxable_amount + tax_amount
        )

    @classmethod
    def _recalculate_totals(
        cls,
        purchase_order: PurchaseOrder,
    ) -> None:
        purchase_order.subtotal = cls._money(
            sum(
                (
                    line.line_subtotal
                    for line in purchase_order.line_items
                ),
                start=Decimal("0.00"),
            )
        )
        purchase_order.discount_total = cls._money(
            sum(
                (
                    line.discount_amount
                    for line in purchase_order.line_items
                ),
                start=Decimal("0.00"),
            )
        )
        purchase_order.tax_total = cls._money(
            sum(
                (
                    line.tax_amount
                    for line in purchase_order.line_items
                ),
                start=Decimal("0.00"),
            )
        )
        purchase_order.total_amount = cls._money(
            sum(
                (
                    line.line_total
                    for line in purchase_order.line_items
                ),
                start=Decimal("0.00"),
            )
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
                str(key): PurchaseOrderService._json_safe(nested)
                for key, nested in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            return [
                PurchaseOrderService._json_safe(nested)
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
        purchase_order: PurchaseOrder,
        summary: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.audit_logs.record_event(
            organization_id=organization_id,
            payload=AuditLogCreate(
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action=action,
                entity_type="purchase_order",
                entity_id=purchase_order.id,
                summary=summary,
                status="success",
                details=self._json_safe(details or {}),
            ),
            commit=False,
        )

    def _record_requisition_conversion(
        self,
        *,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
        requisition: PurchaseRequisition,
        purchase_order: PurchaseOrder,
    ) -> None:
        self.audit_logs.record_event(
            organization_id=organization_id,
            payload=AuditLogCreate(
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="purchase_requisition_converted",
                entity_type="purchase_requisition",
                entity_id=requisition.id,
                summary=(
                    "Purchase requisition converted to a purchase "
                    "order."
                ),
                status="success",
                details={
                    "purchase_order_id": str(purchase_order.id),
                    "purchase_order_number": (
                        purchase_order.purchase_order_number
                    ),
                },
            ),
            commit=False,
        )

    def _rollback_conflict(self, exc: IntegrityError) -> None:
        self.db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The purchase order conflicts with an existing "
                "organization record."
            ),
        ) from exc

    @staticmethod
    def _generated_number() -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%d")
        suffix = uuid.uuid4().hex[:8].upper()
        return f"PO-{timestamp}-{suffix}"

    def _build_line(
        self,
        organization_id: uuid.UUID,
        payload: PurchaseOrderLineCreate,
        *,
        position: int,
        source_requisition_line_id: uuid.UUID | None = None,
    ) -> PurchaseOrderLineItem:
        data = payload.model_dump()
        self._validate_inventory_item(
            organization_id,
            data["inventory_item_id"],
        )

        line = PurchaseOrderLineItem(
            source_requisition_line_id=(
                source_requisition_line_id
            ),
            inventory_item_id=data["inventory_item_id"],
            description=data["description"],
            quantity_ordered=data["quantity_ordered"],
            unit_of_measure=data["unit_of_measure"],
            unit_price=data["unit_price"],
            discount_amount=data["discount_amount"],
            tax_rate=data["tax_rate"],
            position=position,
            notes=data["notes"],
            details=data["details"],
        )
        self._calculate_line(line)
        return line

    def create_purchase_order(
        self,
        organization_id: uuid.UUID,
        payload: CreatePurchaseOrderSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseOrder:
        supplier = self._get_supplier_or_404(
            organization_id,
            payload.supplier_id,
        )
        self._validate_location(
            organization_id,
            payload.delivery_location_id,
        )

        purchase_order_number = (
            payload.purchase_order_number
            or self._generated_number()
        )

        if self.purchase_orders.number_exists(
            organization_id,
            purchase_order_number,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A purchase order with this number already "
                    "exists in the organization."
                ),
            )

        purchase_order = PurchaseOrder(
            organization_id=organization_id,
            purchase_order_number=purchase_order_number,
            supplier_id=supplier.id,
            title=payload.title,
            currency=payload.currency,
            expected_delivery_date=(
                payload.expected_delivery_date
            ),
            delivery_location_id=payload.delivery_location_id,
            delivery_address=payload.delivery_address,
            payment_terms_days=payload.payment_terms_days,
            supplier_reference=payload.supplier_reference,
            notes=payload.notes,
            terms_and_conditions=payload.terms_and_conditions,
            details=payload.details,
            created_by_user_id=actor_user_id,
            **self._supplier_snapshot(supplier),
        )

        used_positions: set[int] = set()

        for index, line_payload in enumerate(payload.line_items):
            position = (
                line_payload.position
                if line_payload.position is not None
                else index
            )

            if position in used_positions:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Line-item positions must be unique.",
                )

            used_positions.add(position)
            purchase_order.line_items.append(
                self._build_line(
                    organization_id,
                    line_payload,
                    position=position,
                )
            )

        self._recalculate_totals(purchase_order)

        try:
            self.purchase_orders.create(purchase_order)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="purchase_order_created",
                purchase_order=purchase_order,
                summary="Purchase order created.",
                details={
                    "supplier_id": supplier.id,
                    "line_count": len(purchase_order.line_items),
                    "total_amount": purchase_order.total_amount,
                },
            )
            self.db.commit()
            return self._get_or_404(
                organization_id,
                purchase_order.id,
            )

        except IntegrityError as exc:
            self._rollback_conflict(exc)

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def convert_requisition(
        self,
        organization_id: uuid.UUID,
        requisition_id: uuid.UUID,
        payload: ConvertRequisitionToPurchaseOrderSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseOrder:
        requisition = self.requisitions.get_for_organization(
            organization_id,
            requisition_id,
            for_update=True,
        )

        if requisition is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase requisition not found.",
            )

        if requisition.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only approved purchase requisitions can be "
                    "converted."
                ),
            )

        if not requisition.line_items:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The purchase requisition has no line items to "
                    "convert."
                ),
            )

        if self.purchase_orders.get_by_source_requisition(
            organization_id,
            requisition.id,
        ) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This purchase requisition has already been "
                    "converted."
                ),
            )

        supplier_id = (
            payload.supplier_id
            or requisition.preferred_supplier_id
        )

        if supplier_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "A supplier is required to convert this purchase "
                    "requisition."
                ),
            )

        supplier = self._get_supplier_or_404(
            organization_id,
            supplier_id,
        )

        conflicting_lines = [
            line.id
            for line in requisition.line_items
            if (
                line.preferred_supplier_id is not None
                and line.preferred_supplier_id != supplier.id
            )
        ]

        if conflicting_lines:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "One or more requisition lines prefer a different "
                    "supplier."
                ),
            )

        delivery_location_id = (
            payload.delivery_location_id
            if payload.delivery_location_id is not None
            else requisition.delivery_location_id
        )
        self._validate_location(
            organization_id,
            delivery_location_id,
        )

        purchase_order_number = (
            payload.purchase_order_number
            or self._generated_number()
        )

        if self.purchase_orders.number_exists(
            organization_id,
            purchase_order_number,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A purchase order with this number already "
                    "exists in the organization."
                ),
            )

        payment_terms_days = (
            payload.payment_terms_days
            if payload.payment_terms_days is not None
            else supplier.payment_terms_days
        )

        purchase_order = PurchaseOrder(
            organization_id=organization_id,
            purchase_order_number=purchase_order_number,
            source_requisition_id=requisition.id,
            supplier_id=supplier.id,
            title=payload.title or requisition.title,
            currency=requisition.currency,
            expected_delivery_date=(
                payload.expected_delivery_date
                if payload.expected_delivery_date is not None
                else requisition.requested_delivery_date
            ),
            delivery_location_id=delivery_location_id,
            delivery_address=payload.delivery_address,
            payment_terms_days=payment_terms_days,
            supplier_reference=payload.supplier_reference,
            notes=(
                payload.notes
                if payload.notes is not None
                else requisition.notes
            ),
            terms_and_conditions=payload.terms_and_conditions,
            details={
                **(requisition.details or {}),
                **payload.details,
            },
            created_by_user_id=actor_user_id,
            **self._supplier_snapshot(supplier),
        )

        for line in requisition.line_items:
            po_line = PurchaseOrderLineItem(
                source_requisition_line_id=line.id,
                inventory_item_id=line.inventory_item_id,
                description=line.description,
                quantity_ordered=line.quantity,
                unit_of_measure=line.unit_of_measure,
                unit_price=line.estimated_unit_cost,
                discount_amount=Decimal("0.00"),
                tax_rate=Decimal("0.0000"),
                position=line.position,
                notes=line.notes,
                details=dict(line.details or {}),
            )
            self._calculate_line(po_line)
            purchase_order.line_items.append(po_line)

        self._recalculate_totals(purchase_order)
        requisition.status = "converted"

        try:
            self.purchase_orders.create(purchase_order)
            self.requisitions.update(requisition)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="purchase_order_created_from_requisition",
                purchase_order=purchase_order,
                summary=(
                    "Purchase order created from approved purchase "
                    "requisition."
                ),
                details={
                    "source_requisition_id": requisition.id,
                    "supplier_id": supplier.id,
                    "line_count": len(purchase_order.line_items),
                    "total_amount": purchase_order.total_amount,
                },
            )
            self._record_requisition_conversion(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                requisition=requisition,
                purchase_order=purchase_order,
            )
            self.db.commit()
            return self._get_or_404(
                organization_id,
                purchase_order.id,
            )

        except IntegrityError as exc:
            self._rollback_conflict(exc)

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def list_purchase_orders(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        status_filter: str | None = None,
        supplier_id: uuid.UUID | None = None,
        source_requisition_id: uuid.UUID | None = None,
        expected_from: date | None = None,
        expected_to: date | None = None,
        include_inactive: bool = False,
    ) -> PurchaseOrderListResponse:
        if (
            expected_from is not None
            and expected_to is not None
            and expected_from > expected_to
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="expected_from cannot be after expected_to.",
            )

        total = self.purchase_orders.count_for_organization(
            organization_id,
            search=search,
            status_filter=status_filter,
            supplier_id=supplier_id,
            source_requisition_id=source_requisition_id,
            expected_from=expected_from,
            expected_to=expected_to,
            include_inactive=include_inactive,
        )
        items = self.purchase_orders.list_for_organization(
            organization_id,
            skip=skip,
            limit=limit,
            search=search,
            status_filter=status_filter,
            supplier_id=supplier_id,
            source_requisition_id=source_requisition_id,
            expected_from=expected_from,
            expected_to=expected_to,
            include_inactive=include_inactive,
        )
        return PurchaseOrderListResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_purchase_order(
        self,
        organization_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> PurchaseOrder:
        return self._get_or_404(
            organization_id,
            purchase_order_id,
            include_inactive=include_inactive,
        )

    def update_purchase_order(
        self,
        organization_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        payload: UpdatePurchaseOrderSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseOrder:
        purchase_order = self._get_or_404(
            organization_id,
            purchase_order_id,
            for_update=True,
        )
        self._ensure_draft(purchase_order)
        update_data = payload.model_dump(exclude_unset=True)

        if not update_data:
            return purchase_order

        if "supplier_id" in update_data:
            supplier_id = update_data["supplier_id"]

            if supplier_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Supplier cannot be cleared.",
                )

            if (
                purchase_order.source_requisition_id is not None
                and supplier_id != purchase_order.supplier_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The supplier cannot be changed on a purchase "
                        "order converted from a requisition."
                    ),
                )

            supplier = self._get_supplier_or_404(
                organization_id,
                supplier_id,
            )
            purchase_order.supplier_id = supplier.id

            for key, value in self._supplier_snapshot(
                supplier
            ).items():
                setattr(purchase_order, key, value)

            update_data.pop("supplier_id")

        if "delivery_location_id" in update_data:
            self._validate_location(
                organization_id,
                update_data["delivery_location_id"],
            )

        for field_name, value in update_data.items():
            setattr(purchase_order, field_name, value)

        try:
            self.purchase_orders.update(purchase_order)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="purchase_order_updated",
                purchase_order=purchase_order,
                summary="Purchase order updated.",
                details={
                    "changed_fields": sorted(
                        payload.model_fields_set
                    ),
                },
            )
            self.db.commit()
            return self._get_or_404(
                organization_id,
                purchase_order_id,
            )

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
        purchase_order_id: uuid.UUID,
        payload: PurchaseOrderLineCreate,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseOrder:
        purchase_order = self._get_or_404(
            organization_id,
            purchase_order_id,
            for_update=True,
        )
        self._ensure_draft(purchase_order)
        position = (
            payload.position
            if payload.position is not None
            else self.purchase_orders.next_position(
                purchase_order_id
            )
        )
        line_item = self._build_line(
            organization_id,
            payload,
            position=position,
        )
        line_item.purchase_order_id = purchase_order.id

        try:
            self.purchase_orders.add_line_item(line_item)
            purchase_order.line_items.append(line_item)
            self._recalculate_totals(purchase_order)
            self.purchase_orders.update(purchase_order)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="purchase_order_line_added",
                purchase_order=purchase_order,
                summary="Purchase order line added.",
                details={
                    "line_item_id": line_item.id,
                    "position": position,
                    "line_total": line_item.line_total,
                },
            )
            self.db.commit()
            return self._get_or_404(
                organization_id,
                purchase_order_id,
            )

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
        purchase_order_id: uuid.UUID,
        line_item_id: uuid.UUID,
        payload: PurchaseOrderLineUpdate,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseOrder:
        purchase_order = self._get_or_404(
            organization_id,
            purchase_order_id,
            for_update=True,
        )
        self._ensure_draft(purchase_order)
        line_item = self._get_line_or_404(
            organization_id,
            purchase_order_id,
            line_item_id,
            for_update=True,
        )
        update_data = payload.model_dump(exclude_unset=True)

        if not update_data:
            return purchase_order

        if "inventory_item_id" in update_data:
            self._validate_inventory_item(
                organization_id,
                update_data["inventory_item_id"],
            )

        for field_name, value in update_data.items():
            setattr(line_item, field_name, value)

        if line_item.quantity_ordered < line_item.quantity_received:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Ordered quantity cannot be lower than quantity "
                    "already received."
                ),
            )

        self._calculate_line(line_item)

        try:
            self.purchase_orders.update_line_item(line_item)
            self._recalculate_totals(purchase_order)
            self.purchase_orders.update(purchase_order)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="purchase_order_line_updated",
                purchase_order=purchase_order,
                summary="Purchase order line updated.",
                details={
                    "line_item_id": line_item.id,
                    "changed_fields": sorted(update_data),
                    "line_total": line_item.line_total,
                },
            )
            self.db.commit()
            return self._get_or_404(
                organization_id,
                purchase_order_id,
            )

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
        purchase_order_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseOrder:
        purchase_order = self._get_or_404(
            organization_id,
            purchase_order_id,
            for_update=True,
        )
        self._ensure_draft(purchase_order)
        line_item = self._get_line_or_404(
            organization_id,
            purchase_order_id,
            line_item_id,
            for_update=True,
        )
        removed_total = line_item.line_total

        try:
            purchase_order.line_items.remove(line_item)
            self.purchase_orders.delete_line_item(line_item)
            self._recalculate_totals(purchase_order)
            self.purchase_orders.update(purchase_order)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="purchase_order_line_removed",
                purchase_order=purchase_order,
                summary="Purchase order line removed.",
                details={
                    "line_item_id": line_item_id,
                    "removed_line_total": removed_total,
                },
            )
            self.db.commit()
            return self._get_or_404(
                organization_id,
                purchase_order_id,
            )

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def issue_purchase_order(
        self,
        organization_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseOrder:
        purchase_order = self._get_or_404(
            organization_id,
            purchase_order_id,
            for_update=True,
        )
        self._ensure_draft(purchase_order)

        if not purchase_order.line_items:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A purchase order must contain at least one line "
                    "item before issue."
                ),
            )

        self._get_supplier_or_404(
            organization_id,
            purchase_order.supplier_id,
        )
        previous_status = purchase_order.status
        now = datetime.now(UTC)
        purchase_order.status = "issued"
        purchase_order.issue_date = now.date()
        purchase_order.issued_at = now
        purchase_order.issued_by_user_id = actor_user_id

        return self._commit_status_change(
            organization_id=organization_id,
            purchase_order=purchase_order,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            action="purchase_order_issued",
            summary="Purchase order issued to supplier.",
            from_status=previous_status,
        )

    def acknowledge_purchase_order(
        self,
        organization_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        payload: AcknowledgePurchaseOrderSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseOrder:
        purchase_order = self._get_or_404(
            organization_id,
            purchase_order_id,
            for_update=True,
        )

        if purchase_order.status != "issued":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only issued purchase orders can be "
                    "acknowledged."
                ),
            )

        purchase_order.status = "acknowledged"
        purchase_order.acknowledged_at = datetime.now(UTC)
        purchase_order.acknowledged_by_user_id = actor_user_id

        if payload.supplier_reference is not None:
            purchase_order.supplier_reference = (
                payload.supplier_reference
            )

        return self._commit_status_change(
            organization_id=organization_id,
            purchase_order=purchase_order,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            action="purchase_order_acknowledged",
            summary="Supplier acknowledgement recorded.",
            from_status="issued",
            details={
                "supplier_reference": (
                    purchase_order.supplier_reference
                ),
            },
        )

    def cancel_purchase_order(
        self,
        organization_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        payload: CancelPurchaseOrderSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseOrder:
        purchase_order = self._get_or_404(
            organization_id,
            purchase_order_id,
            for_update=True,
        )

        if purchase_order.status not in CANCELLABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This purchase order cannot be cancelled in its "
                    "current status."
                ),
            )

        if any(
            line.quantity_received > Decimal("0")
            for line in purchase_order.line_items
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A purchase order with received quantities cannot "
                    "be cancelled."
                ),
            )

        previous_status = purchase_order.status
        purchase_order.status = "cancelled"
        purchase_order.cancelled_at = datetime.now(UTC)
        purchase_order.cancelled_by_user_id = actor_user_id
        purchase_order.cancellation_reason = payload.reason

        return self._commit_status_change(
            organization_id=organization_id,
            purchase_order=purchase_order,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            action="purchase_order_cancelled",
            summary="Purchase order cancelled.",
            from_status=previous_status,
            details={"reason": payload.reason},
        )

    def close_purchase_order(
        self,
        organization_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> PurchaseOrder:
        purchase_order = self._get_or_404(
            organization_id,
            purchase_order_id,
            for_update=True,
        )

        if purchase_order.status != "received":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only fully received purchase orders can be "
                    "closed."
                ),
            )

        purchase_order.status = "closed"
        purchase_order.closed_at = datetime.now(UTC)
        purchase_order.closed_by_user_id = actor_user_id

        return self._commit_status_change(
            organization_id=organization_id,
            purchase_order=purchase_order,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            action="purchase_order_closed",
            summary="Purchase order closed.",
            from_status="received",
        )

    def synchronize_receipt_status(
        self,
        purchase_order: PurchaseOrder,
    ) -> None:
        """
        Recalculate receipt-derived status without committing.

        Goods-receipt services can call this inside their own atomic
        transaction after updating line quantities.
        """

        if purchase_order.status in {"cancelled", "closed"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Receipt progress cannot be applied to a cancelled "
                    "or closed purchase order."
                ),
            )

        if purchase_order.status not in {
            "issued",
            "acknowledged",
            "partially_received",
            "received",
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Purchase order must be issued before stock can be "
                    "received."
                ),
            )

        if not purchase_order.line_items:
            purchase_order.status = "acknowledged"
            return

        received_any = any(
            line.quantity_received > Decimal("0")
            for line in purchase_order.line_items
        )
        received_all = all(
            line.quantity_received >= line.quantity_ordered
            for line in purchase_order.line_items
        )

        if received_all:
            purchase_order.status = "received"
        elif received_any:
            purchase_order.status = "partially_received"
        elif purchase_order.acknowledged_at is not None:
            purchase_order.status = "acknowledged"
        else:
            purchase_order.status = "issued"

    def _commit_status_change(
        self,
        *,
        organization_id: uuid.UUID,
        purchase_order: PurchaseOrder,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
        action: str,
        summary: str,
        from_status: str,
        details: dict[str, Any] | None = None,
    ) -> PurchaseOrder:
        try:
            self.purchase_orders.update(purchase_order)
            audit_details = {
                "from_status": from_status,
                "to_status": purchase_order.status,
            }
            audit_details.update(details or {})
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action=action,
                purchase_order=purchase_order,
                summary=summary,
                details=audit_details,
            )
            self.db.commit()
            return self._get_or_404(
                organization_id,
                purchase_order.id,
            )

        except IntegrityError as exc:
            self._rollback_conflict(exc)

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise
