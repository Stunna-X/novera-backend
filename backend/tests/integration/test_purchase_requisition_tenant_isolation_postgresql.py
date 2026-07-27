"""PostgreSQL tenant and workflow tests for purchase requisitions."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.repositories.purchase_requisition import (
    PurchaseRequisitionRepository,
)
from app.schemas.purchase_requisition import (
    CreatePurchaseRequisitionSchema,
    PurchaseRequisitionLineCreate,
    RejectPurchaseRequisitionSchema,
)
from app.services.purchase_requisition_service import (
    PurchaseRequisitionService,
)


def test_purchase_requisition_is_tenant_isolated_and_audited(
    integration_session_factory: sessionmaker[Session],
) -> None:
    token = uuid.uuid4().hex
    organization = Organization(
        id=uuid.uuid4(),
        name=f"Requisition Integration {token}",
        slug=f"requisition-integration-{token}",
        timezone="UTC",
    )
    other_organization = Organization(
        id=uuid.uuid4(),
        name=f"Requisition Isolation {token}",
        slug=f"requisition-isolation-{token}",
        timezone="UTC",
    )

    with integration_session_factory() as db:
        db.add_all([organization, other_organization])
        db.commit()

    try:
        with integration_session_factory() as db:
            service = PurchaseRequisitionService(db)
            created = service.create_requisition(
                organization.id,
                CreatePurchaseRequisitionSchema(
                    requisition_number="PR-001",
                    title="Replacement pump",
                    line_items=[
                        PurchaseRequisitionLineCreate(
                            description="Submersible pump",
                            quantity="2.000",
                            estimated_unit_cost="1000.0000",
                        )
                    ],
                ),
            )
            other_created = service.create_requisition(
                other_organization.id,
                CreatePurchaseRequisitionSchema(
                    requisition_number="PR-001",
                    title="Other tenant request",
                    line_items=[
                        PurchaseRequisitionLineCreate(
                            description="Other item",
                        )
                    ],
                ),
            )
            requisition_id = created.id
            other_requisition_id = other_created.id

        with integration_session_factory() as db:
            repository = PurchaseRequisitionRepository(db)

            assert repository.get_for_organization(
                organization.id,
                requisition_id,
            ) is not None
            assert repository.get_for_organization(
                organization.id,
                other_requisition_id,
            ) is None
            assert repository.get_for_organization(
                other_organization.id,
                requisition_id,
            ) is None

        with integration_session_factory() as db:
            service = PurchaseRequisitionService(db)

            with pytest.raises(HTTPException) as conflict:
                service.create_requisition(
                    organization.id,
                    CreatePurchaseRequisitionSchema(
                        requisition_number="pr-001",
                        title="Duplicate number",
                    ),
                )

            assert conflict.value.status_code == 409

            submitted = service.submit_requisition(
                organization.id,
                requisition_id,
            )
            assert submitted.status == "submitted"

            rejected = service.reject_requisition(
                organization.id,
                requisition_id,
                RejectPurchaseRequisitionSchema(
                    reason="Need a revised specification."
                ),
            )
            assert rejected.status == "rejected"

            resubmitted = service.submit_requisition(
                organization.id,
                requisition_id,
            )
            approved = service.approve_requisition(
                organization.id,
                resubmitted.id,
            )
            assert approved.status == "approved"
            assert str(approved.total_estimated_amount) == "2000.00"

        with integration_session_factory() as db:
            actions = {
                action
                for (action,) in (
                    db.query(AuditLog.action)
                    .filter(
                        AuditLog.organization_id == organization.id,
                        AuditLog.entity_type
                        == "purchase_requisition",
                        AuditLog.entity_id == requisition_id,
                    )
                    .all()
                )
            }

            assert {
                "purchase_requisition_created",
                "purchase_requisition_submitted",
                "purchase_requisition_rejected",
                "purchase_requisition_approved",
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
