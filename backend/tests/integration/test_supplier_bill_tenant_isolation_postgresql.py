"""PostgreSQL tenant and three-way matching tests for supplier bills."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from app.models.audit_log import AuditLog
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptLineItem
from app.models.inventory import InventoryLocation
from app.models.organization import Organization
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLineItem
from app.models.supplier import Supplier
from app.models.supplier_bill import (
    SupplierBill,
    SupplierBillLineItem,
    SupplierBillMatchResult,
)
from app.repositories.supplier_bill import SupplierBillRepository
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
)
from app.services.goods_receipt_service import GoodsReceiptService
from app.services.purchase_order_service import PurchaseOrderService
from app.services.supplier_bill_service import SupplierBillService


pytestmark = pytest.mark.integration


def test_supplier_bill_is_tenant_isolated_and_matches_posted_receipts(
    integration_session_factory: sessionmaker[Session],
) -> None:
    token = uuid.uuid4().hex
    organization = Organization(
        id=uuid.uuid4(),
        name=f"Supplier Bill Integration {token}",
        slug=f"supplier-bill-integration-{token}",
        timezone="UTC",
    )
    other_organization = Organization(
        id=uuid.uuid4(),
        name=f"Supplier Bill Isolation {token}",
        slug=f"supplier-bill-isolation-{token}",
        timezone="UTC",
    )
    supplier = Supplier(
        id=uuid.uuid4(),
        organization_id=organization.id,
        code="SUP-BILL-001",
        name="Three Way Supplier",
        currency="NGN",
    )
    location = InventoryLocation(
        id=uuid.uuid4(),
        organization_id=organization.id,
        code="WH-BILL-001",
        name="Three Way Warehouse",
        location_type="warehouse",
    )

    with integration_session_factory() as db:
        db.add_all([organization, other_organization, supplier, location])
        db.commit()

    try:
        with integration_session_factory() as db:
            purchase_order = PurchaseOrderService(db).create_purchase_order(
                organization.id,
                CreatePurchaseOrderSchema(
                    purchase_order_number="PO-BILL-001",
                    supplier_id=supplier.id,
                    title="Three-way matching order",
                    delivery_location_id=location.id,
                    line_items=[
                        PurchaseOrderLineCreate(
                            description="Drilling consumables",
                            quantity_ordered="5.000",
                            unit_of_measure="lot",
                            unit_price="1000.0000",
                        )
                    ],
                ),
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
                    goods_receipt_number="GR-BILL-001",
                    purchase_order_id=purchase_order_id,
                    receiving_location_id=location.id,
                    line_items=[
                        GoodsReceiptLineCreate(
                            purchase_order_line_item_id=(
                                purchase_order_line_id
                            ),
                            quantity_accepted="5.000",
                        )
                    ],
                ),
            )
            GoodsReceiptService(db).post_goods_receipt(
                organization.id,
                receipt.id,
            )

        with integration_session_factory() as db:
            service = SupplierBillService(db)
            bill = service.create_supplier_bill(
                organization.id,
                CreateSupplierBillSchema(
                    supplier_bill_number="SB-001",
                    supplier_invoice_number="VENDOR-INV-001",
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
                            quantity_billed="5.000",
                            unit_price="1000.0000",
                        )
                    ],
                ),
            )
            bill_id = bill.id
            submitted = service.submit_supplier_bill(
                organization.id,
                bill.id,
                SubmitSupplierBillSchema(note="Ready for matching."),
            )
            assert submitted.status == "submitted"

            matched = service.run_three_way_match(
                organization.id,
                bill.id,
                MatchSupplierBillSchema(),
            )
            assert matched.status == "matched"
            assert matched.match_status == "matched"
            assert len(matched.match_results) == 1
            assert matched.match_results[0].quantity_received == Decimal(
                "5.000"
            )
            assert matched.match_results[0].quantity_within_tolerance is True
            assert matched.match_results[0].price_within_tolerance is True

            approved = service.approve_supplier_bill(
                organization.id,
                bill.id,
                ApproveSupplierBillSchema(),
            )
            assert approved.status == "approved"

        with integration_session_factory() as db:
            repository = SupplierBillRepository(db)
            assert repository.get_for_organization(
                organization.id,
                bill_id,
            ) is not None
            assert repository.get_for_organization(
                other_organization.id,
                bill_id,
            ) is None

            service = SupplierBillService(db)
            with pytest.raises(HTTPException) as foreign_read:
                service.get_supplier_bill(
                    other_organization.id,
                    bill_id,
                )
            assert foreign_read.value.status_code == 404

            audit_actions = {
                action
                for (action,) in (
                    db.query(AuditLog.action)
                    .filter(
                        AuditLog.organization_id == organization.id,
                        AuditLog.action.in_(
                            [
                                "supplier_bill_created",
                                "supplier_bill_submitted",
                                (
                                    "supplier_bill_three_way_"
                                    "match_completed"
                                ),
                                "supplier_bill_approved",
                            ]
                        ),
                    )
                    .all()
                )
            }
            assert {
                "supplier_bill_created",
                "supplier_bill_submitted",
                "supplier_bill_three_way_match_completed",
                "supplier_bill_approved",
            }.issubset(audit_actions)

        with integration_session_factory() as db:
            service = SupplierBillService(db)
            exception_bill = service.create_supplier_bill(
                organization.id,
                CreateSupplierBillSchema(
                    supplier_bill_number="SB-002",
                    supplier_invoice_number="VENDOR-INV-002",
                    supplier_id=supplier.id,
                    purchase_order_id=purchase_order_id,
                    invoice_date=date.today(),
                    currency="NGN",
                    line_items=[
                        SupplierBillLineCreate(
                            purchase_order_line_item_id=(
                                purchase_order_line_id
                            ),
                            quantity_billed="6.000",
                            unit_price="1100.0000",
                        )
                    ],
                ),
            )
            service.submit_supplier_bill(
                organization.id,
                exception_bill.id,
                SubmitSupplierBillSchema(),
            )
            exception_bill = service.run_three_way_match(
                organization.id,
                exception_bill.id,
                MatchSupplierBillSchema(),
            )
            assert exception_bill.status == "exception"

            with pytest.raises(HTTPException) as approval_error:
                service.approve_supplier_bill(
                    organization.id,
                    exception_bill.id,
                    ApproveSupplierBillSchema(),
                )
            assert approval_error.value.status_code == 422

            approved_override = service.approve_supplier_bill(
                organization.id,
                exception_bill.id,
                ApproveSupplierBillSchema(
                    override_reason=(
                        "Finance director accepted documented variance."
                    )
                ),
            )
            assert approved_override.status == "approved"
            assert approved_override.approval_override_reason is not None

    finally:
        with integration_session_factory() as db:
            organization_ids = [organization.id, other_organization.id]
            bill_ids = [
                row[0]
                for row in db.query(SupplierBill.id)
                .filter(SupplierBill.organization_id.in_(organization_ids))
                .all()
            ]
            if bill_ids:
                db.execute(
                    delete(SupplierBillMatchResult).where(
                        SupplierBillMatchResult.supplier_bill_id.in_(bill_ids)
                    )
                )
                db.execute(
                    delete(SupplierBillLineItem).where(
                        SupplierBillLineItem.supplier_bill_id.in_(bill_ids)
                    )
                )
                db.execute(
                    delete(SupplierBill).where(SupplierBill.id.in_(bill_ids))
                )

            receipt_ids = [
                row[0]
                for row in db.query(GoodsReceipt.id)
                .filter(GoodsReceipt.organization_id.in_(organization_ids))
                .all()
            ]
            if receipt_ids:
                db.execute(
                    delete(GoodsReceiptLineItem).where(
                        GoodsReceiptLineItem.goods_receipt_id.in_(receipt_ids)
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
                .filter(PurchaseOrder.organization_id.in_(organization_ids))
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
                    InventoryLocation.organization_id.in_(organization_ids)
                )
            )
            db.execute(
                delete(Supplier).where(
                    Supplier.organization_id.in_(organization_ids)
                )
            )
            db.execute(
                delete(AuditLog).where(
                    AuditLog.organization_id.in_(organization_ids)
                )
            )
            db.execute(
                delete(Organization).where(
                    Organization.id.in_(organization_ids)
                )
            )
            db.commit()
