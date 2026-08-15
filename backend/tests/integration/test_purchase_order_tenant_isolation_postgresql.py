"""PostgreSQL tenant and workflow tests for purchase orders."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.purchase_requisition import PurchaseRequisition
from app.models.supplier import Supplier
from app.repositories.purchase_order import PurchaseOrderRepository
from app.schemas.purchase_order import (
    AcknowledgePurchaseOrderSchema,
    ConvertRequisitionToPurchaseOrderSchema,
)
from app.schemas.purchase_requisition import (
    CreatePurchaseRequisitionSchema,
    PurchaseRequisitionLineCreate,
)
from app.services.purchase_order_service import PurchaseOrderService
from app.services.purchase_requisition_service import (
    PurchaseRequisitionService,
)


def test_purchase_order_is_tenant_isolated_and_converts_requisition(
    integration_session_factory: sessionmaker[Session],
) -> None:
    token = uuid.uuid4().hex
    organization = Organization(
        id=uuid.uuid4(),
        name=f"Purchase Order Integration {token}",
        slug=f"purchase-order-integration-{token}",
        timezone="UTC",
    )
    other_organization = Organization(
        id=uuid.uuid4(),
        name=f"Purchase Order Isolation {token}",
        slug=f"purchase-order-isolation-{token}",
        timezone="UTC",
    )
    supplier = Supplier(
        id=uuid.uuid4(),
        organization_id=organization.id,
        code="SUP-001",
        name="Pump Supplier",
        currency="NGN",
        payment_terms_days=30,
    )
    other_supplier = Supplier(
        id=uuid.uuid4(),
        organization_id=other_organization.id,
        code="SUP-001",
        name="Other Supplier",
        currency="NGN",
    )

    with integration_session_factory() as db:
        db.add_all(
            [
                organization,
                other_organization,
                supplier,
                other_supplier,
            ]
        )
        db.commit()

    try:
        with integration_session_factory() as db:
            requisition_service = PurchaseRequisitionService(db)
            requisition = requisition_service.create_requisition(
                organization.id,
                CreatePurchaseRequisitionSchema(
                    requisition_number="PR-PO-001",
                    title="Replacement pumps",
                    preferred_supplier_id=supplier.id,
                    line_items=[
                        PurchaseRequisitionLineCreate(
                            description="Submersible pump",
                            quantity="2.000",
                            estimated_unit_cost="1000.0000",
                        )
                    ],
                ),
            )
            requisition_service.submit_requisition(
                organization.id,
                requisition.id,
            )
            requisition_service.approve_requisition(
                organization.id,
                requisition.id,
            )
            requisition_id = requisition.id

        with integration_session_factory() as db:
            service = PurchaseOrderService(db)
            created = service.convert_requisition(
                organization.id,
                requisition_id,
                ConvertRequisitionToPurchaseOrderSchema(
                    purchase_order_number="PO-001",
                ),
            )
            purchase_order_id = created.id

            assert created.status == "draft"
            assert created.supplier_id == supplier.id
            assert created.source_requisition_id == requisition_id
            assert str(created.total_amount) == "2000.00"
            assert len(created.line_items) == 1
            assert str(
                created.line_items[0].quantity_received
            ) == "0.000"

        with integration_session_factory() as db:
            repository = PurchaseOrderRepository(db)

            assert repository.get_for_organization(
                organization.id,
                purchase_order_id,
            ) is not None
            assert repository.get_for_organization(
                other_organization.id,
                purchase_order_id,
            ) is None

            requisition_status = (
                db.query(PurchaseRequisition.status)
                .filter(PurchaseRequisition.id == requisition_id)
                .scalar()
            )
            assert requisition_status == "converted"

        with integration_session_factory() as db:
            service = PurchaseOrderService(db)

            with pytest.raises(HTTPException) as conflict:
                service.convert_requisition(
                    organization.id,
                    requisition_id,
                    ConvertRequisitionToPurchaseOrderSchema(),
                )

            assert conflict.value.status_code == 409

            issued = service.issue_purchase_order(
                organization.id,
                purchase_order_id,
            )
            assert issued.status == "issued"

            acknowledged = service.acknowledge_purchase_order(
                organization.id,
                purchase_order_id,
                AcknowledgePurchaseOrderSchema(
                    supplier_reference="ACK-001"
                ),
            )
            assert acknowledged.status == "acknowledged"
            assert acknowledged.supplier_reference == "ACK-001"

        with integration_session_factory() as db:
            actions = {
                action
                for (action,) in (
                    db.query(AuditLog.action)
                    .filter(
                        AuditLog.organization_id == organization.id,
                        AuditLog.entity_type == "purchase_order",
                        AuditLog.entity_id == purchase_order_id,
                    )
                    .all()
                )
            }

            assert {
                "purchase_order_created_from_requisition",
                "purchase_order_issued",
                "purchase_order_acknowledged",
            }.issubset(actions)

    finally:
        with integration_session_factory() as db:
            db.execute(
                delete(Organization).where(
                    Organization.id.in_(
                        [organization.id, other_organization.id]
                    )
                )
            )
            db.commit()
