"""Schema tests for procurement documents and approval evidence."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.procurement_document import (
    ArchiveProcurementDocumentSchema,
    CreateProcurementApprovalEvidenceSchema,
    CreateProcurementDocumentVersionSchema,
    UpdateProcurementDocumentSchema,
    VerifyProcurementDocumentVersionSchema,
)


CHECKSUM = "a" * 64


def test_version_normalizes_checksum() -> None:
    payload = CreateProcurementDocumentVersionSchema(
        file_name="invoice.pdf",
        storage_key="procurement/invoice.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        sha256_checksum="A" * 64,
    )
    assert payload.sha256_checksum == CHECKSUM


def test_version_rejects_invalid_checksum() -> None:
    with pytest.raises(ValidationError):
        CreateProcurementDocumentVersionSchema(
            file_name="invoice.pdf",
            storage_key="procurement/invoice.pdf",
            content_type="application/pdf",
            file_size_bytes=1024,
            sha256_checksum="z" * 64,
        )


def test_version_rejects_file_over_twenty_five_megabytes() -> None:
    with pytest.raises(ValidationError):
        CreateProcurementDocumentVersionSchema(
            file_name="invoice.pdf",
            storage_key="procurement/invoice.pdf",
            content_type="application/pdf",
            file_size_bytes=(25 * 1024 * 1024) + 1,
            sha256_checksum=CHECKSUM,
        )


def test_verify_schema_normalizes_checksum() -> None:
    payload = VerifyProcurementDocumentVersionSchema(
        observed_sha256_checksum="B" * 64
    )
    assert payload.observed_sha256_checksum == "b" * 64


def test_document_update_requires_field() -> None:
    with pytest.raises(ValidationError):
        UpdateProcurementDocumentSchema()


def test_archive_reason_cannot_be_blank() -> None:
    with pytest.raises(ValidationError):
        ArchiveProcurementDocumentSchema(reason="   ")


def test_approval_evidence_requires_timezone() -> None:
    with pytest.raises(ValidationError):
        CreateProcurementApprovalEvidenceSchema(
            entity_type="purchase_order",
            entity_id=uuid.uuid4(),
            action_type="purchase_order_issue",
            decision="approved",
            statement="Approved for issue.",
            occurred_at=datetime(2026, 7, 27, 12, 0),
        )
