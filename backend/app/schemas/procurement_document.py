"""Schemas for procurement documents, versions, and approval evidence."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024


def _required_text(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Value cannot be blank.")
    return cleaned


class ProcurementDocumentEntityType(StrEnum):
    SUPPLIER = "supplier"
    PURCHASE_REQUISITION = "purchase_requisition"
    PURCHASE_ORDER = "purchase_order"
    GOODS_RECEIPT = "goods_receipt"
    SUPPLIER_BILL = "supplier_bill"
    SUPPLIER_PAYMENT = "supplier_payment"
    SUPPLIER_RETURN = "supplier_return"
    SUPPLIER_DEBIT_NOTE = "supplier_debit_note"


class ProcurementApprovalEntityType(StrEnum):
    PURCHASE_REQUISITION = "purchase_requisition"
    PURCHASE_ORDER = "purchase_order"
    GOODS_RECEIPT = "goods_receipt"
    SUPPLIER_BILL = "supplier_bill"
    SUPPLIER_PAYMENT = "supplier_payment"
    SUPPLIER_RETURN = "supplier_return"
    SUPPLIER_DEBIT_NOTE = "supplier_debit_note"


class ProcurementDocumentType(StrEnum):
    SUPPLIER_QUOTATION = "supplier_quotation"
    REQUISITION_SUPPORT = "requisition_support"
    PURCHASE_ORDER = "purchase_order"
    DELIVERY_NOTE = "delivery_note"
    GOODS_RECEIPT_EVIDENCE = "goods_receipt_evidence"
    SUPPLIER_INVOICE = "supplier_invoice"
    PAYMENT_EVIDENCE = "payment_evidence"
    RETURN_EVIDENCE = "return_evidence"
    DEBIT_NOTE = "debit_note"
    SUPPLIER_CREDIT_NOTE = "supplier_credit_note"
    APPROVAL_MEMO = "approval_memo"
    OTHER = "other"


class ProcurementDocumentStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class ProcurementApprovalActionType(StrEnum):
    REQUISITION_APPROVAL = "requisition_approval"
    PURCHASE_ORDER_ISSUE = "purchase_order_issue"
    GOODS_RECEIPT_POSTING = "goods_receipt_posting"
    SUPPLIER_BILL_APPROVAL = "supplier_bill_approval"
    SUPPLIER_PAYMENT_POSTING = "supplier_payment_posting"
    SUPPLIER_RETURN_DISPATCH = "supplier_return_dispatch"
    DEBIT_NOTE_ISSUE = "debit_note_issue"
    CREDIT_SETTLEMENT = "credit_settlement"
    EXCEPTION_WAIVER = "exception_waiver"


class ProcurementApprovalDecision(StrEnum):
    APPROVED = "approved"
    ACKNOWLEDGED = "acknowledged"
    REJECTED = "rejected"
    WAIVED = "waived"


class CreateProcurementDocumentSchema(BaseModel):
    document_number: str | None = Field(default=None, max_length=60)
    entity_type: ProcurementDocumentEntityType
    entity_id: uuid.UUID
    document_type: ProcurementDocumentType
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=4000)
    required_for_action: str | None = Field(
        default=None,
        max_length=80,
    )
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return _required_text(value)

    @field_validator(
        "document_number",
        "description",
        "required_for_action",
    )
    @classmethod
    def clean_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class UpdateProcurementDocumentSchema(BaseModel):
    title: str | None = Field(default=None, max_length=240)
    description: str | None = Field(default=None, max_length=4000)
    required_for_action: str | None = Field(
        default=None,
        max_length=80,
    )
    details: dict[str, Any] | None = None

    @field_validator("title")
    @classmethod
    def clean_optional_title(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        return _required_text(value)

    @field_validator(
        "description",
        "required_for_action",
    )
    @classmethod
    def clean_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError(
                "At least one procurement-document field is required."
            )
        return self


class ArchiveProcurementDocumentSchema(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return _required_text(value)


class CreateProcurementDocumentVersionSchema(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    storage_key: str = Field(min_length=3, max_length=700)
    content_type: str = Field(min_length=3, max_length=160)
    file_size_bytes: int = Field(
        gt=0,
        le=MAX_FILE_SIZE_BYTES,
    )
    sha256_checksum: str = Field(min_length=64, max_length=64)
    notes: str | None = Field(default=None, max_length=4000)
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "file_name",
        "storage_key",
        "content_type",
    )
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("sha256_checksum")
    @classmethod
    def normalize_checksum(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not SHA256_PATTERN.fullmatch(cleaned):
            raise ValueError(
                "sha256_checksum must contain 64 hexadecimal characters."
            )
        return cleaned

    @field_validator("notes")
    @classmethod
    def clean_notes(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class VerifyProcurementDocumentVersionSchema(BaseModel):
    observed_sha256_checksum: str = Field(
        min_length=64,
        max_length=64,
    )

    @field_validator("observed_sha256_checksum")
    @classmethod
    def normalize_checksum(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not SHA256_PATTERN.fullmatch(cleaned):
            raise ValueError(
                "observed_sha256_checksum must contain "
                "64 hexadecimal characters."
            )
        return cleaned


class ProcurementDocumentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    procurement_document_id: uuid.UUID
    version_number: int
    file_name: str
    storage_key: str
    content_type: str
    file_size_bytes: int
    sha256_checksum: str
    upload_state: str
    integrity_status: str
    uploaded_by_user_id: uuid.UUID | None
    verified_by_user_id: uuid.UUID | None
    verified_at: datetime | None
    notes: str | None
    details: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProcurementDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    document_number: str
    entity_type: ProcurementDocumentEntityType
    entity_id: uuid.UUID
    document_type: ProcurementDocumentType
    title: str
    description: str | None
    required_for_action: str | None
    status: ProcurementDocumentStatus
    current_version_number: int
    created_by_user_id: uuid.UUID | None
    archived_by_user_id: uuid.UUID | None
    archived_at: datetime | None
    archive_reason: str | None
    details: dict[str, Any]
    versions: list[ProcurementDocumentVersionResponse]
    created_at: datetime
    updated_at: datetime


class ProcurementDocumentListResponse(BaseModel):
    items: list[ProcurementDocumentResponse]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)


class CreateProcurementApprovalEvidenceSchema(BaseModel):
    entity_type: ProcurementApprovalEntityType
    entity_id: uuid.UUID
    action_type: ProcurementApprovalActionType
    decision: ProcurementApprovalDecision
    statement: str = Field(min_length=1, max_length=8000)
    procurement_document_version_id: uuid.UUID | None = None
    occurred_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("statement")
    @classmethod
    def clean_statement(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone.")
        return value


class ProcurementApprovalEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    entity_type: ProcurementApprovalEntityType
    entity_id: uuid.UUID
    action_type: ProcurementApprovalActionType
    decision: ProcurementApprovalDecision
    statement: str
    procurement_document_version_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    actor_membership_id: uuid.UUID | None
    occurred_at: datetime
    evidence_hash: str
    details: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProcurementApprovalEvidenceListResponse(BaseModel):
    items: list[ProcurementApprovalEvidenceResponse]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
