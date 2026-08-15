"""PostgreSQL tenant, posting, and rollback tests for goods receipts."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from app.models.audit_log import AuditLog
from app.models.goods_receipt import GoodsReceipt
from app.models.inventory import (
    InventoryBalance,
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
)
from app.models.organization import Organization
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLineItem
from app.models.supplier import Supplier
from app.repositories.goods_receipt import GoodsReceiptRepository
from app.schemas.goods_receipt import (
    CreateGoodsReceiptSchema,
    GoodsReceiptLineCreate,
    UpdateGoodsReceiptSchema,
)
from app.schemas.purchase_order import (
    CreatePurchaseOrderSchema,
    PurchaseOrderLineCreate,
)
from app.services.goods_receipt_service import GoodsReceiptService
from app.services.purchase_order_service import PurchaseOrderService


def test_goods_receipt_is_tenant_isolated_and_posts_atomically(
    integration_session_factory: sessionmaker[Session],
) -> None:
    token = uuid.uuid4().hex
    organization = Organization(
        id=uuid.uuid4(),
        name=f"Goods Receipt Integration {token}",
        slug=f"goods-receipt-integration-{token}",
        timezone="UTC",
    )
    other_organization = Organization(
        id=uuid.uuid4(),
        name=f"Goods Receipt Isolation {token}",
        slug=f"goods-receipt-isolation-{token}",
        timezone="UTC",
    )
    supplier = Supplier(
        id=uuid.uuid4(),
        organization_id=organization.id,
        code="SUP-GR-001",
        name="Receipt Supplier",
        currency="NGN",
    )
    location = InventoryLocation(
        id=uuid.uuid4(),
        organization_id=organization.id,
        code="WH-GR-001",
        name="Receipt Warehouse",
        location_type="warehouse",
    )
    item = InventoryItem(
        id=uuid.uuid4(),
        organization_id=organization.id,
        sku="ITEM-GR-001",
        name="Receipt Pump",
        item_type="material",
        unit_of_measure="each",
        default_unit_cost=Decimal("100.0000"),
        currency="NGN",
    )

    with integration_session_factory() as db:
        db.add_all(
            [
                organization,
                other_organization,
                supplier,
                location,
                item,
            ]
        )
        db.commit()

    try:
        with integration_session_factory() as db:
            purchase_order_service = PurchaseOrderService(db)
            purchase_order = purchase_order_service.create_purchase_order(
                organization.id,
                CreatePurchaseOrderSchema(
                    purchase_order_number="PO-GR-001",
                    supplier_id=supplier.id,
                    title="Goods receipt integration order",
                    delivery_location_id=location.id,
                    line_items=[
                        PurchaseOrderLineCreate(
                            inventory_item_id=item.id,
                            description="Receipt Pump",
                            quantity_ordered="5.000",
                            unit_of_measure="each",
                            unit_price="100.0000",
                        )
                    ],
                ),
            )
            purchase_order_id = purchase_order.id
            purchase_order_line_id = purchase_order.line_items[0].id
            purchase_order_service.issue_purchase_order(
                organization.id,
                purchase_order.id,
            )

        with integration_session_factory() as db:
            service = GoodsReceiptService(db)
            first_receipt = service.create_goods_receipt(
                organization.id,
                CreateGoodsReceiptSchema(
                    goods_receipt_number="GR-001",
                    purchase_order_id=purchase_order_id,
                    receiving_location_id=location.id,
                    supplier_delivery_note="DN-001",
                    line_items=[
                        GoodsReceiptLineCreate(
                            purchase_order_line_item_id=(
                                purchase_order_line_id
                            ),
                            quantity_accepted="2.000",
                            quantity_rejected="1.000",
                            rejection_reason="Wrong specification",
                            quantity_damaged="1.000",
                            damage_notes="Transit damage",
                        )
                    ],
                ),
            )
            first_receipt_id = first_receipt.id

            posted_first = service.post_goods_receipt(
                organization.id,
                first_receipt.id,
            )

            assert posted_first.status == "posted"
            assert posted_first.total_accepted_quantity == Decimal(
                "2.000"
            )
            assert posted_first.total_rejected_quantity == Decimal(
                "1.000"
            )
            assert posted_first.total_damaged_quantity == Decimal(
                "1.000"
            )
            assert (
                posted_first.line_items[0].inventory_movement_id
                is not None
            )

            with pytest.raises(HTTPException) as immutable:
                service.update_goods_receipt(
                    organization.id,
                    first_receipt.id,
                    UpdateGoodsReceiptSchema(notes="Too late"),
                )

            assert immutable.value.status_code == 409

        with integration_session_factory() as db:
            repository = GoodsReceiptRepository(db)

            assert repository.get_for_organization(
                organization.id,
                first_receipt_id,
            ) is not None
            assert repository.get_for_organization(
                other_organization.id,
                first_receipt_id,
            ) is None

            purchase_order = (
                db.query(PurchaseOrder)
                .filter(PurchaseOrder.id == purchase_order_id)
                .one()
            )
            purchase_order_line = (
                db.query(PurchaseOrderLineItem)
                .filter(
                    PurchaseOrderLineItem.id == purchase_order_line_id
                )
                .one()
            )
            balance = (
                db.query(InventoryBalance)
                .filter(
                    InventoryBalance.organization_id
                    == organization.id,
                    InventoryBalance.item_id == item.id,
                    InventoryBalance.location_id == location.id,
                )
                .one()
            )

            assert purchase_order.status == "partially_received"
            assert purchase_order_line.quantity_received == Decimal(
                "2.000"
            )
            assert balance.quantity_on_hand == Decimal("2.000")
            assert (
                db.query(InventoryMovement)
                .filter(
                    InventoryMovement.organization_id
                    == organization.id,
                    InventoryMovement.reference_type
                    == "goods_receipt",
                    InventoryMovement.reference_id
                    == str(first_receipt_id),
                )
                .count()
                == 1
            )

        with integration_session_factory() as db:
            service = GoodsReceiptService(db)
            second_receipt = service.create_goods_receipt(
                organization.id,
                CreateGoodsReceiptSchema(
                    goods_receipt_number="GR-002",
                    purchase_order_id=purchase_order_id,
                    receiving_location_id=location.id,
                    line_items=[
                        GoodsReceiptLineCreate(
                            purchase_order_line_item_id=(
                                purchase_order_line_id
                            ),
                            quantity_accepted="3.000",
                        )
                    ],
                ),
            )
            service.post_goods_receipt(
                organization.id,
                second_receipt.id,
            )

        with integration_session_factory() as db:
            purchase_order = (
                db.query(PurchaseOrder)
                .filter(PurchaseOrder.id == purchase_order_id)
                .one()
            )
            purchase_order_line = (
                db.query(PurchaseOrderLineItem)
                .filter(
                    PurchaseOrderLineItem.id == purchase_order_line_id
                )
                .one()
            )
            balance = (
                db.query(InventoryBalance)
                .filter(
                    InventoryBalance.organization_id
                    == organization.id,
                    InventoryBalance.item_id == item.id,
                    InventoryBalance.location_id == location.id,
                )
                .one()
            )

            assert purchase_order.status == "received"
            assert purchase_order_line.quantity_received == Decimal(
                "5.000"
            )
            assert balance.quantity_on_hand == Decimal("5.000")

            actions = {
                action
                for (action,) in (
                    db.query(AuditLog.action)
                    .filter(
                        AuditLog.organization_id == organization.id,
                        AuditLog.action.in_(
                            [
                                "goods_receipt_posted",
                                "inventory_stock_received",
                                (
                                    "purchase_order_receipt_"
                                    "progress_updated"
                                ),
                            ]
                        ),
                    )
                    .all()
                )
            }

            assert {
                "goods_receipt_posted",
                "inventory_stock_received",
                "purchase_order_receipt_progress_updated",
            }.issubset(actions)

        with integration_session_factory() as db:
            purchase_order_service = PurchaseOrderService(db)
            rollback_order = purchase_order_service.create_purchase_order(
                organization.id,
                CreatePurchaseOrderSchema(
                    purchase_order_number="PO-GR-ROLLBACK",
                    supplier_id=supplier.id,
                    title="Goods receipt rollback order",
                    delivery_location_id=location.id,
                    line_items=[
                        PurchaseOrderLineCreate(
                            inventory_item_id=item.id,
                            description="Rollback Pump",
                            quantity_ordered="1.000",
                            unit_price="100.0000",
                        )
                    ],
                ),
            )
            rollback_order_id = rollback_order.id
            rollback_line_id = rollback_order.line_items[0].id
            purchase_order_service.issue_purchase_order(
                organization.id,
                rollback_order.id,
            )

        with integration_session_factory() as db:
            service = GoodsReceiptService(db)
            rollback_receipt = service.create_goods_receipt(
                organization.id,
                CreateGoodsReceiptSchema(
                    goods_receipt_number="GR-ROLLBACK",
                    purchase_order_id=rollback_order_id,
                    receiving_location_id=location.id,
                    line_items=[
                        GoodsReceiptLineCreate(
                            purchase_order_line_item_id=rollback_line_id,
                            quantity_accepted="1.000",
                        )
                    ],
                ),
            )
            rollback_receipt_id = rollback_receipt.id

        with integration_session_factory() as db:
            line = (
                db.query(PurchaseOrderLineItem)
                .filter(PurchaseOrderLineItem.id == rollback_line_id)
                .one()
            )
            line.quantity_received = Decimal("1.000")
            db.commit()

        with integration_session_factory() as db:
            service = GoodsReceiptService(db)

            with pytest.raises(HTTPException) as conflict:
                service.post_goods_receipt(
                    organization.id,
                    rollback_receipt_id,
                )

            assert conflict.value.status_code == 409

        with integration_session_factory() as db:
            rollback_receipt_status = (
                db.query(GoodsReceipt.status)
                .filter(GoodsReceipt.id == rollback_receipt_id)
                .scalar()
            )
            rollback_movements = (
                db.query(InventoryMovement)
                .filter(
                    InventoryMovement.reference_type
                    == "goods_receipt",
                    InventoryMovement.reference_id
                    == str(rollback_receipt_id),
                )
                .count()
            )

            assert rollback_receipt_status == "draft"
            assert rollback_movements == 0

    finally:
        with integration_session_factory() as db:
            organization_ids = [
                organization.id,
                other_organization.id,
            ]
            db.execute(
                delete(GoodsReceipt).where(
                    GoodsReceipt.organization_id.in_(organization_ids)
                )
            )
            db.execute(
                delete(PurchaseOrder).where(
                    PurchaseOrder.organization_id.in_(organization_ids)
                )
            )
            db.execute(
                delete(Organization).where(
                    Organization.id.in_(organization_ids)
                )
            )
            db.commit()
