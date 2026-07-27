"""PostgreSQL tenant isolation for procurement document metadata."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from app.models.organization import Organization
from app.models.procurement_document import (
    ProcurementApprovalEvidence,
    ProcurementDocument,
    ProcurementDocumentVersion,
)
from app.repositories.procurement_document import (
    ProcurementDocumentRepository,
)


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason=(
        "TEST_DATABASE_URL is required for PostgreSQL "
        "integration tests."
    ),
)


def test_documents_versions_and_evidence_cannot_cross_tenants() -> None:
    engine = create_engine(TEST_DATABASE_URL)
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )
    token = uuid.uuid4().hex
    organization = Organization(
        name=f"Document Primary {token}",
        slug=f"document-primary-{token}",
    )
    other_organization = Organization(
        name=f"Document Foreign {token}",
        slug=f"document-foreign-{token}",
    )
    entity_id = uuid.uuid4()
    try:
        with SessionLocal() as db:
            db.add_all([organization, other_organization])
            db.flush()
            document = ProcurementDocument(
                organization_id=organization.id,
                document_number=f"PD-{token[:10]}",
                entity_type="purchase_order",
                entity_id=entity_id,
                document_type="purchase_order",
                title="Tenant isolation purchase order",
                status="active",
                current_version_number=1,
            )
            db.add(document)
            db.flush()
            version = ProcurementDocumentVersion(
                procurement_document_id=document.id,
                version_number=1,
                file_name="purchase-order.pdf",
                storage_key=f"procurement/{token}.pdf",
                content_type="application/pdf",
                file_size_bytes=100,
                sha256_checksum="a" * 64,
                upload_state="available",
                integrity_status="verified",
                verified_at=datetime.now(UTC),
            )
            db.add(version)
            db.flush()
            evidence = ProcurementApprovalEvidence(
                organization_id=organization.id,
                entity_type="purchase_order",
                entity_id=entity_id,
                action_type="purchase_order_issue",
                decision="approved",
                statement="Approved for issue.",
                procurement_document_version_id=version.id,
                occurred_at=datetime.now(UTC),
                evidence_hash=uuid.uuid4().hex * 2,
            )
            db.add(evidence)
            db.commit()
            organization_id = organization.id
            other_id = other_organization.id
            document_id = document.id
            version_id = version.id
            evidence_id = evidence.id
        with SessionLocal() as db:
            repository = ProcurementDocumentRepository(db)
            assert repository.get_document(
                organization_id,
                document_id,
            ) is not None
            assert repository.get_document(
                other_id,
                document_id,
            ) is None
            assert repository.get_version_for_organization(
                organization_id,
                version_id,
            ) is not None
            assert repository.get_version_for_organization(
                other_id,
                version_id,
            ) is None
            assert repository.get_evidence(
                organization_id,
                evidence_id,
            ) is not None
            assert repository.get_evidence(
                other_id,
                evidence_id,
            ) is None
    finally:
        with SessionLocal() as db:
            db.execute(
                delete(ProcurementApprovalEvidence).where(
                    ProcurementApprovalEvidence.organization_id
                    == organization.id
                )
            )
            db.execute(
                delete(ProcurementDocument).where(
                    ProcurementDocument.organization_id
                    == organization.id
                )
            )
            db.execute(
                delete(Organization).where(
                    Organization.id.in_(
                        [organization.id, other_organization.id]
                    )
                )
            )
            db.commit()
        engine.dispose()
