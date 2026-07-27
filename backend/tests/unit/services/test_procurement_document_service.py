"""Pure helper tests for procurement document service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.services.procurement_document_service import (
    ENTITY_MODELS,
    ProcurementDocumentService,
)


def _hash(statement: str, checksum: str | None) -> str:
    return ProcurementDocumentService.evidence_hash(
        organization_id=uuid.UUID(
            "00000000-0000-0000-0000-000000000001"
        ),
        entity_type="purchase_order",
        entity_id=uuid.UUID(
            "00000000-0000-0000-0000-000000000002"
        ),
        action_type="purchase_order_issue",
        decision="approved",
        statement=statement,
        document_checksum=checksum,
        actor_user_id=uuid.UUID(
            "00000000-0000-0000-0000-000000000003"
        ),
        actor_membership_id=uuid.UUID(
            "00000000-0000-0000-0000-000000000004"
        ),
        occurred_at=datetime(2026, 7, 27, 12, 0, tzinfo=UTC),
    )


def test_generated_document_number_has_prefix() -> None:
    assert (
        ProcurementDocumentService.generated_document_number()
        .startswith("PD-")
    )


def test_pdf_content_type_is_allowed() -> None:
    assert ProcurementDocumentService.content_type_is_allowed(
        "application/pdf"
    )


def test_executable_content_type_is_rejected() -> None:
    assert not ProcurementDocumentService.content_type_is_allowed(
        "application/x-msdownload"
    )


def test_evidence_hash_is_stable() -> None:
    assert _hash("Approved.", "a" * 64) == _hash(
        "Approved.",
        "a" * 64,
    )


def test_evidence_hash_changes_with_statement() -> None:
    assert _hash("Approved.", "a" * 64) != _hash(
        "Rejected.",
        "a" * 64,
    )


def test_evidence_hash_changes_with_document_checksum() -> None:
    assert _hash("Approved.", "a" * 64) != _hash(
        "Approved.",
        "b" * 64,
    )


def test_all_procurement_entity_types_are_mapped() -> None:
    assert set(ENTITY_MODELS) == {
        "supplier",
        "purchase_requisition",
        "purchase_order",
        "goods_receipt",
        "supplier_bill",
        "supplier_payment",
        "supplier_return",
        "supplier_debit_note",
    }
