"""PostgreSQL integration tests for supplier-payment settlement."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from app.models.audit_log import AuditLog
from app.models.goods_receipt import (
    GoodsReceipt,
    GoodsReceiptLineItem,
)
from app.models.inventory import InventoryLocation
from app.models.organization import Organization
from app.models.purchase_order import (
    PurchaseOrder,
    PurchaseOrderLineItem,
)
from app.models.supplier import Supplier
from app.models.supplier_bill import (
    SupplierBill,
    SupplierBillLineItem,
    SupplierBillMatchResult,
)
from app.models.supplier_payment import (
    SupplierPayment,
    SupplierPaymentAllocation,
)
from app.schemas.goods_receipt import (
    CreateGoodsReceiptSchema,
    GoodsReceiptLineCreate,
)
from app.schemas.purchase_order import (
    CreatePurchaseOrderSchema,
    PurchaseOrderLineCreate,
)
from app.schemas.supplier_bill import (
    ApproveSupplierBillSchema,
    CreateSupplierBillSchema,
    MatchSupplierBillSchema,
    SubmitSupplierBillSchema,
    SupplierBillLineCreate,
    VoidSupplierBillSchema,
)
from app.schemas.supplier_payment import (
    SupplierPaymentAllocationCreate,
    SupplierPaymentCreate,
    SupplierPaymentReverse,
)
from app.services.goods_receipt_service import GoodsReceiptService
from app.services.purchase_order_service import PurchaseOrderService
from app.services.supplier_bill_service import SupplierBillService
from app.services.supplier_payment_service import SupplierPaymentService


pytestmark = pytest.mark.integration


def test_supplier_payment_is_tenant_scoped_and_reversible(
    integration_session_factory: sessionmaker[Session],
) -> None:
    token = uuid.uuid4().hex[:10]
    organization = Organization(
        id=uuid.uuid4(),
        name=f"Supplier Payment Integration {token}",
        slug=f"supplier-payment-integration-{token}",
        timezone="UTC",
    )
    other_organization = Organization(
        id=uuid.uuid4(),
        name=f"Supplier Payment Isolation {token}",
        slug=f"supplier-payment-isolation-{token}",
        timezone="UTC",
    )
    supplier = Supplier(
        id=uuid.uuid4(),
        organization_id=organization.id,
        code="SUP-PAY-001",
        name="Settlement Supplier",
        currency="NGN",
    )
    location = InventoryLocation(
        id=uuid.uuid4(),
        organization_id=organization.id,
        code="WH-PAY-001",
        name="Settlement Warehouse",
        location_type="warehouse",
    )

    with integration_session_factory() as db:
        db.add_all(
            [
                organization,
                other_organization,
                supplier,
                location,
            ]
        )
        db.commit()

    try:
        with integration_session_factory() as db:
            purchase_order = (
                PurchaseOrderService(db).create_purchase_order(
                    organization.id,
                    CreatePurchaseOrderSchema(
                        purchase_order_number="PO-PAY-001",
                        supplier_id=supplier.id,
                        title="Supplier payment integration order",
                        delivery_location_id=location.id,
                        line_items=[
                            PurchaseOrderLineCreate(
                                description="Settlement materials",
                                quantity_ordered="2.000",
                                unit_of_measure="lot",
                                unit_price="500.0000",
                            )
                        ],
                    ),
                )
            )
            purchase_order_id = purchase_order.id
            purchase_order_line_id = purchase_order.line_items[0].id
            PurchaseOrderService(db).issue_purchase_order(
                organization.id,
                purchase_order.id,
            )

        with integration_session_factory() as db:
            receipt = GoodsReceiptService(db).create_goods_receipt(
                organization.id,
                CreateGoodsReceiptSchema(
                    goods_receipt_number="GR-PAY-001",
                    purchase_order_id=purchase_order_id,
                    receiving_location_id=location.id,
                    line_items=[
                        GoodsReceiptLineCreate(
                            purchase_order_line_item_id=(
                                purchase_order_line_id
                            ),
                            quantity_accepted="2.000",
                        )
                    ],
                ),
            )
            GoodsReceiptService(db).post_goods_receipt(
                organization.id,
                receipt.id,
            )

        with integration_session_factory() as db:
            bill_service = SupplierBillService(db)
            bill = bill_service.create_supplier_bill(
                organization.id,
                CreateSupplierBillSchema(
                    supplier_bill_number="SB-PAY-001",
                    supplier_invoice_number="VENDOR-PAY-001",
                    supplier_id=supplier.id,
                    purchase_order_id=purchase_order_id,
                    invoice_date=date.today(),
                    due_date=date.today() + timedelta(days=30),
                    currency="NGN",
                    line_items=[
                        SupplierBillLineCreate(
                            purchase_order_line_item_id=(
                                purchase_order_line_id
                            ),
                            quantity_billed="2.000",
                            unit_price="500.0000",
                        )
                    ],
                ),
            )
            bill_id = bill.id
            bill_service.submit_supplier_bill(
                organization.id,
                bill.id,
                SubmitSupplierBillSchema(),
            )
            bill_service.run_three_way_match(
                organization.id,
                bill.id,
                MatchSupplierBillSchema(),
            )
            bill_service.approve_supplier_bill(
                organization.id,
                bill.id,
                ApproveSupplierBillSchema(),
            )

        with integration_session_factory() as db:
            service = SupplierPaymentService(db)
            payment = service.record_payment(
                organization.id,
                SupplierPaymentCreate(
                    payment_number="SP-PAY-001",
                    supplier_id=supplier.id,
                    total_amount="400.00",
                    reference_number="BANK-PAY-001",
                    allocations=[
                        SupplierPaymentAllocationCreate(
                            supplier_bill_id=bill_id,
                            amount_allocated="400.00",
                        )
                    ],
                ),
            )
            payment_id = payment.id
            assert payment.status == "posted"
            assert payment.total_amount == Decimal("400.00")

            with pytest.raises(HTTPException) as paid_bill_void:
                SupplierBillService(db).void_supplier_bill(
                    organization.id,
                    bill_id,
                    VoidSupplierBillSchema(
                        reason="Attempted void after settlement.",
                    ),
                )
            assert paid_bill_void.value.status_code == 409

            payables = service.list_payables(
                organization.id,
                skip=0,
                limit=100,
            )
            payable = next(
                item
                for item in payables.items
                if item.supplier_bill_id == bill_id
            )
            assert payable.amount_paid == Decimal("400.00")
            assert payable.balance_due == Decimal("600.00")
            assert payable.settlement_status == "partially_paid"

            with pytest.raises(HTTPException) as foreign_read:
                service.get_payment(
                    other_organization.id,
                    payment_id,
                )
            assert foreign_read.value.status_code == 404

            with pytest.raises(HTTPException) as overpayment:
                service.record_payment(
                    organization.id,
                    SupplierPaymentCreate(
                        payment_number="SP-PAY-OVER",
                        supplier_id=supplier.id,
                        total_amount="700.00",
                        reference_number="BANK-PAY-OVER",
                        allocations=[
                            SupplierPaymentAllocationCreate(
                                supplier_bill_id=bill_id,
                                amount_allocated="700.00",
                            )
                        ],
                    ),
                )
            assert overpayment.value.status_code == 409

            reversed_payment = service.reverse_payment(
                organization.id,
                payment_id,
                SupplierPaymentReverse(
                    reason="Duplicate bank transfer.",
                ),
            )
            assert reversed_payment.status == "reversed"

            restored = service.list_payables(
                organization.id,
                skip=0,
                limit=100,
            )
            restored_bill = next(
                item
                for item in restored.items
                if item.supplier_bill_id == bill_id
            )
            assert restored_bill.amount_paid == Decimal("0.00")
            assert restored_bill.balance_due == Decimal("1000.00")

        with integration_session_factory() as db:
            actions = {
                action
                for (action,) in (
                    db.query(AuditLog.action)
                    .filter(
                        AuditLog.organization_id == organization.id,
                        AuditLog.action.in_(
                            [
                                "supplier_payment_posted",
                                "supplier_payment_reversed",
                            ]
                        ),
                    )
                    .all()
                )
            }
            assert {
                "supplier_payment_posted",
                "supplier_payment_reversed",
            }.issubset(actions)

    finally:
        with integration_session_factory() as db:
            organization_ids = [
                organization.id,
                other_organization.id,
            ]
            payment_ids = [
                row[0]
                for row in db.query(SupplierPayment.id)
                .filter(
                    SupplierPayment.organization_id.in_(
                        organization_ids
                    )
                )
                .all()
            ]
            if payment_ids:
                db.execute(
                    delete(SupplierPaymentAllocation).where(
                        SupplierPaymentAllocation.supplier_payment_id.in_(
                            payment_ids
                        )
                    )
                )
                db.execute(
                    delete(SupplierPayment).where(
                        SupplierPayment.id.in_(payment_ids)
                    )
                )

            bill_ids = [
                row[0]
                for row in db.query(SupplierBill.id)
                .filter(
                    SupplierBill.organization_id.in_(
                        organization_ids
                    )
                )
                .all()
            ]
            if bill_ids:
                db.execute(
                    delete(SupplierBillMatchResult).where(
                        SupplierBillMatchResult.supplier_bill_id.in_(
                            bill_ids
                        )
                    )
                )
                db.execute(
                    delete(SupplierBillLineItem).where(
                        SupplierBillLineItem.supplier_bill_id.in_(
                            bill_ids
                        )
                    )
                )
                db.execute(
                    delete(SupplierBill).where(
                        SupplierBill.id.in_(bill_ids)
                    )
                )

            receipt_ids = [
                row[0]
                for row in db.query(GoodsReceipt.id)
                .filter(
                    GoodsReceipt.organization_id.in_(
                        organization_ids
                    )
                )
                .all()
            ]
            if receipt_ids:
                db.execute(
                    delete(GoodsReceiptLineItem).where(
                        GoodsReceiptLineItem.goods_receipt_id.in_(
                            receipt_ids
                        )
                    )
                )
                db.execute(
                    delete(GoodsReceipt).where(
                        GoodsReceipt.id.in_(receipt_ids)
                    )
                )

            purchase_order_ids = [
                row[0]
                for row in db.query(PurchaseOrder.id)
                .filter(
                    PurchaseOrder.organization_id.in_(
                        organization_ids
                    )
                )
                .all()
            ]
            if purchase_order_ids:
                db.execute(
                    delete(PurchaseOrderLineItem).where(
                        PurchaseOrderLineItem.purchase_order_id.in_(
                            purchase_order_ids
                        )
                    )
                )
                db.execute(
                    delete(PurchaseOrder).where(
                        PurchaseOrder.id.in_(purchase_order_ids)
                    )
                )

            db.execute(
                delete(InventoryLocation).where(
                    InventoryLocation.organization_id.in_(
                        organization_ids
                    )
                )
            )
            db.execute(
                delete(Supplier).where(
                    Supplier.organization_id.in_(
                        organization_ids
                    )
                )
            )
            db.execute(
                delete(AuditLog).where(
                    AuditLog.organization_id.in_(
                        organization_ids
                    )
                )
            )
            db.execute(
                delete(Organization).where(
                    Organization.id.in_(organization_ids)
                )
            )
            db.commit()
