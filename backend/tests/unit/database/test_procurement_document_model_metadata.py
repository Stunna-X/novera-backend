"""SQLAlchemy metadata tests for procurement document evidence."""

from app.models.procurement_document import (
    ProcurementApprovalEvidence,
    ProcurementDocument,
    ProcurementDocumentVersion,
)


def _constraint_names(model) -> set[str]:
    return {
        constraint.name
        for constraint in model.__table__.constraints
        if constraint.name is not None
    }


def test_procurement_document_table_metadata() -> None:
    assert ProcurementDocument.__tablename__ == "procurement_documents"
    names = _constraint_names(ProcurementDocument)
    assert "uq_procurement_documents_organization_number" in names
    assert "ck_procurement_documents_archive_state_valid" in names


def test_document_version_table_metadata() -> None:
    assert (
        ProcurementDocumentVersion.__tablename__
        == "procurement_document_versions"
    )
    names = _constraint_names(ProcurementDocumentVersion)
    assert "uq_procurement_document_versions_number" in names
    assert "uq_procurement_document_versions_storage_key" in names


def test_document_version_integrity_constraints() -> None:
    names = _constraint_names(ProcurementDocumentVersion)
    assert "ck_procurement_document_versions_sha256_length_valid" in names
    assert (
        "ck_procurement_document_versions_verification_state_valid"
        in names
    )


def test_approval_evidence_table_metadata() -> None:
    assert (
        ProcurementApprovalEvidence.__tablename__
        == "procurement_approval_evidence"
    )
    names = _constraint_names(ProcurementApprovalEvidence)
    assert "uq_procurement_approval_evidence_hash" in names
    assert (
        "ck_procurement_approval_evidence_evidence_hash_length_valid"
        in names
    )


def test_document_versions_use_delete_orphan() -> None:
    assert "delete-orphan" in ProcurementDocument.versions.property.cascade
