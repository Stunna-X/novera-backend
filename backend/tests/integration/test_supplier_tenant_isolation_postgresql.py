"""PostgreSQL integration tests for the supplier foundation."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.supplier import Supplier
from app.repositories.supplier import SupplierRepository
from app.schemas.supplier import (
    CreateSupplierSchema,
    UpdateSupplierSchema,
)
from app.services.supplier_service import SupplierService


def test_supplier_crud_is_tenant_isolated_and_audited(
    integration_session_factory: sessionmaker[Session],
) -> None:
    token = uuid.uuid4().hex

    organization = Organization(
        id=uuid.uuid4(),
        name=f"Supplier Integration {token}",
        slug=f"supplier-integration-{token}",
        timezone="UTC",
    )
    other_organization = Organization(
        id=uuid.uuid4(),
        name=f"Supplier Isolation {token}",
        slug=f"supplier-isolation-{token}",
        timezone="UTC",
    )

    with integration_session_factory() as db:
        db.add_all([organization, other_organization])
        db.commit()

    try:
        with integration_session_factory() as db:
            service = SupplierService(db)

            created = service.create_supplier(
                organization.id,
                CreateSupplierSchema(
                    code="SUP-001",
                    name="Primary Supplier",
                    tax_id=f"TIN-{token[:12]}",
                    currency="NGN",
                ),
            )

            other_created = service.create_supplier(
                other_organization.id,
                CreateSupplierSchema(
                    code="SUP-001",
                    name="Other Tenant Supplier",
                    tax_id=f"TIN-{token[12:24]}",
                    currency="NGN",
                ),
            )

            supplier_id = created.id
            other_supplier_id = other_created.id

        with integration_session_factory() as db:
            repository = SupplierRepository(db)

            assert repository.get_for_organization(
                organization.id,
                supplier_id,
            ) is not None

            assert repository.get_for_organization(
                organization.id,
                other_supplier_id,
            ) is None

            assert repository.get_for_organization(
                other_organization.id,
                supplier_id,
            ) is None

        with integration_session_factory() as db:
            service = SupplierService(db)

            with pytest.raises(HTTPException) as conflict:
                service.create_supplier(
                    organization.id,
                    CreateSupplierSchema(
                        code="sup-001",
                        name="Duplicate Supplier",
                    ),
                )

            assert conflict.value.status_code == 409

            updated = service.update_supplier(
                organization.id,
                supplier_id,
                UpdateSupplierSchema(
                    name="Updated Primary Supplier",
                    payment_terms_days=30,
                ),
            )

            assert updated.name == "Updated Primary Supplier"
            assert updated.payment_terms_days == 30

            service.deactivate_supplier(
                organization.id,
                supplier_id,
            )

            with pytest.raises(HTTPException) as not_found:
                service.get_supplier(
                    organization.id,
                    supplier_id,
                )

            assert not_found.value.status_code == 404

            inactive = service.get_supplier(
                organization.id,
                supplier_id,
                include_inactive=True,
            )
            assert inactive.is_active is False

            reactivated = service.reactivate_supplier(
                organization.id,
                supplier_id,
            )
            assert reactivated.is_active is True

        with integration_session_factory() as db:
            actions = {
                action
                for (action,) in (
                    db.query(AuditLog.action)
                    .filter(
                        AuditLog.organization_id == organization.id,
                        AuditLog.entity_type == "supplier",
                        AuditLog.entity_id == supplier_id,
                    )
                    .all()
                )
            }

            assert {
                "supplier_created",
                "supplier_updated",
                "supplier_deactivated",
                "supplier_reactivated",
            }.issubset(actions)

    finally:
        with integration_session_factory() as db:
            db.execute(
                delete(Organization).where(
                    Organization.id.in_(
                        [
                            organization.id,
                            other_organization.id,
                        ]
                    )
                )
            )
            db.commit()
