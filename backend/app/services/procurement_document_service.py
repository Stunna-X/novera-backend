"""Business logic for procurement documents and approval evidence."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.goods_receipt import GoodsReceipt
from app.models.procurement_document import (
    ProcurementApprovalEvidence,
    ProcurementDocument,
    ProcurementDocumentVersion,
)
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_requisition import PurchaseRequisition
from app.models.supplier import Supplier
from app.models.supplier_bill import SupplierBill
from app.models.supplier_payment import SupplierPayment
from app.models.supplier_return import (
    SupplierDebitNote,
    SupplierReturn,
)
from app.repositories.procurement_document import (
    ProcurementDocumentRepository,
)
from app.schemas.audit_log import AuditLogCreate
from app.schemas.procurement_document import (
    ArchiveProcurementDocumentSchema,
    CreateProcurementApprovalEvidenceSchema,
    CreateProcurementDocumentSchema,
    CreateProcurementDocumentVersionSchema,
    ProcurementApprovalEvidenceListResponse,
    ProcurementApprovalEvidenceResponse,
    ProcurementDocumentListResponse,
    ProcurementDocumentResponse,
    ProcurementDocumentVersionResponse,
    UpdateProcurementDocumentSchema,
    VerifyProcurementDocumentVersionSchema,
)
from app.services.audit_log_service import AuditLogService


ALLOWED_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
        "text/plain",
        "text/csv",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
)

ENTITY_MODELS = {
    "supplier": Supplier,
    "purchase_requisition": PurchaseRequisition,
    "purchase_order": PurchaseOrder,
    "goods_receipt": GoodsReceipt,
    "supplier_bill": SupplierBill,
    "supplier_payment": SupplierPayment,
    "supplier_return": SupplierReturn,
    "supplier_debit_note": SupplierDebitNote,
}


class ProcurementDocumentService:
    """Own transaction boundaries for document and evidence operations."""

    def __init__(self, db: Session):
        self.db = db
        self.documents = ProcurementDocumentRepository(db)
        self.audit_logs = AuditLogService(db)

    @staticmethod
    def generated_document_number() -> str:
        return (
            f"PD-{datetime.now(UTC):%Y%m%d}-"
            f"{uuid.uuid4().hex[:8].upper()}"
        )

    @staticmethod
    def content_type_is_allowed(content_type: str) -> bool:
        return content_type.strip().lower() in ALLOWED_CONTENT_TYPES

    @staticmethod
    def evidence_hash(
        *,
        organization_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        action_type: str,
        decision: str,
        statement: str,
        document_checksum: str | None,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
        occurred_at: datetime,
    ) -> str:
        canonical = {
            "organization_id": str(organization_id),
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "action_type": action_type,
            "decision": decision,
            "statement": statement.strip(),
            "document_checksum": document_checksum,
            "actor_user_id": (
                str(actor_user_id)
                if actor_user_id is not None
                else None
            ),
            "actor_membership_id": (
                str(actor_membership_id)
                if actor_membership_id is not None
                else None
            ),
            "occurred_at": occurred_at.astimezone(UTC).isoformat(),
        }
        serialized = json.dumps(
            canonical,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _record_audit(
        self,
        *,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
        summary: str,
        details: dict[str, Any],
    ) -> None:
        self.audit_logs.record_event(
            organization_id=organization_id,
            payload=AuditLogCreate(
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                summary=summary,
                status="success",
                request_method="SYSTEM",
                request_path="/system/procurement-document-evidence",
                details=details,
            ),
            commit=False,
        )

    def _ensure_entity_exists(
        self,
        organization_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
    ) -> None:
        model = ENTITY_MODELS[entity_type]
        query = self.db.query(model.id).filter(
            model.id == entity_id,
            model.organization_id == organization_id,
        )
        if hasattr(model, "is_active"):
            query = query.filter(model.is_active.is_(True))
        if query.first() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Procurement entity not found.",
            )

    def _get_document_or_404(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> ProcurementDocument:
        document = self.documents.get_document(
            organization_id,
            document_id,
            for_update=for_update,
        )
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Procurement document not found.",
            )
        return document

    def _get_version_or_404(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> ProcurementDocumentVersion:
        version = self.documents.get_version(
            organization_id,
            document_id,
            version_id,
            for_update=for_update,
        )
        if version is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Procurement document version not found.",
            )
        return version

    @staticmethod
    def _ensure_document_active(
        document: ProcurementDocument,
    ) -> None:
        if document.status != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Archived procurement documents cannot be changed.",
            )

    def create_document(
        self,
        organization_id: uuid.UUID,
        payload: CreateProcurementDocumentSchema,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> ProcurementDocument:
        self._ensure_entity_exists(
            organization_id,
            payload.entity_type.value,
            payload.entity_id,
        )
        document_number = (
            payload.document_number
            or self.generated_document_number()
        ).strip().upper()
        if self.documents.document_number_exists(
            organization_id,
            document_number,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Procurement document number already exists.",
            )
        document = ProcurementDocument(
            organization_id=organization_id,
            document_number=document_number,
            entity_type=payload.entity_type.value,
            entity_id=payload.entity_id,
            document_type=payload.document_type.value,
            title=payload.title,
            description=payload.description,
            required_for_action=payload.required_for_action,
            status="active",
            current_version_number=0,
            created_by_user_id=actor_user_id,
            details=dict(payload.details),
        )
        try:
            self.documents.create_document(document)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="procurement_document.created",
                entity_type="procurement_document",
                entity_id=document.id,
                summary="Procurement document created.",
                details={
                    "document_number": document_number,
                    "document_type": document.document_type,
                    "linked_entity_type": document.entity_type,
                    "linked_entity_id": document.entity_id,
                },
            )
            self.db.commit()
            return self._get_document_or_404(
                organization_id,
                document.id,
            )
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Procurement document conflicts with existing data.",
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def list_documents(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        entity_type: str | None,
        entity_id: uuid.UUID | None,
        document_type: str | None,
        status_filter: str | None,
        search: str | None,
    ) -> ProcurementDocumentListResponse:
        return ProcurementDocumentListResponse(
            items=self.documents.list_documents(
                organization_id,
                skip=skip,
                limit=limit,
                entity_type=entity_type,
                entity_id=entity_id,
                document_type=document_type,
                status_filter=status_filter,
                search=search,
            ),
            total=self.documents.count_documents(
                organization_id,
                entity_type=entity_type,
                entity_id=entity_id,
                document_type=document_type,
                status_filter=status_filter,
                search=search,
            ),
            skip=skip,
            limit=limit,
        )

    def get_document(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> ProcurementDocument:
        return self._get_document_or_404(
            organization_id,
            document_id,
        )

    def update_document(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        payload: UpdateProcurementDocumentSchema,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> ProcurementDocument:
        document = self._get_document_or_404(
            organization_id,
            document_id,
            for_update=True,
        )
        self._ensure_document_active(document)
        for field_name in payload.model_fields_set:
            setattr(document, field_name, getattr(payload, field_name))
        try:
            self.documents.update_document(document)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="procurement_document.updated",
                entity_type="procurement_document",
                entity_id=document.id,
                summary="Procurement document metadata updated.",
                details={
                    "changed_fields": sorted(payload.model_fields_set)
                },
            )
            self.db.commit()
            return self._get_document_or_404(
                organization_id,
                document.id,
            )
        except Exception:
            self.db.rollback()
            raise

    def create_version(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        payload: CreateProcurementDocumentVersionSchema,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> ProcurementDocument:
        document = self._get_document_or_404(
            organization_id,
            document_id,
            for_update=True,
        )
        self._ensure_document_active(document)
        if not self.content_type_is_allowed(payload.content_type):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Unsupported procurement document content type.",
            )
        if self.documents.storage_key_exists(payload.storage_key):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The storage key is already registered.",
            )
        version_number = self.documents.next_version_number(document.id)
        version = ProcurementDocumentVersion(
            procurement_document_id=document.id,
            version_number=version_number,
            file_name=payload.file_name,
            storage_key=payload.storage_key,
            content_type=payload.content_type.lower(),
            file_size_bytes=payload.file_size_bytes,
            sha256_checksum=payload.sha256_checksum,
            upload_state="available",
            integrity_status="unverified",
            uploaded_by_user_id=actor_user_id,
            notes=payload.notes,
            details=dict(payload.details),
        )
        try:
            self.documents.create_version(version)
            document.current_version_number = version_number
            self.documents.update_document(document)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="procurement_document.version_created",
                entity_type="procurement_document",
                entity_id=document.id,
                summary="Procurement document version registered.",
                details={
                    "version_id": version.id,
                    "version_number": version.version_number,
                    "file_name": version.file_name,
                    "storage_key": version.storage_key,
                    "content_type": version.content_type,
                    "file_size_bytes": version.file_size_bytes,
                    "sha256_checksum": version.sha256_checksum,
                },
            )
            self.db.commit()
            return self._get_document_or_404(
                organization_id,
                document.id,
            )
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Document version number or storage key "
                    "conflicts with existing data."
                ),
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def list_versions(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> list[ProcurementDocumentVersion]:
        self._get_document_or_404(organization_id, document_id)
        return self.documents.list_versions(
            organization_id,
            document_id,
        )

    def verify_version(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        payload: VerifyProcurementDocumentVersionSchema,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> ProcurementDocumentVersion:
        document = self._get_document_or_404(
            organization_id,
            document_id,
        )
        self._ensure_document_active(document)
        version = self._get_version_or_404(
            organization_id,
            document_id,
            version_id,
            for_update=True,
        )
        matched = (
            payload.observed_sha256_checksum
            == version.sha256_checksum
        )
        version.integrity_status = (
            "verified" if matched else "mismatch"
        )
        version.upload_state = (
            "available" if matched else "quarantined"
        )
        version.verified_by_user_id = actor_user_id
        version.verified_at = datetime.now(UTC)
        try:
            self.documents.update_version(version)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action=(
                    "procurement_document.version_verified"
                    if matched
                    else "procurement_document.version_mismatch"
                ),
                entity_type="procurement_document",
                entity_id=document.id,
                summary=(
                    "Procurement document version checksum verified."
                    if matched
                    else "Procurement document version quarantined."
                ),
                details={
                    "version_id": version.id,
                    "version_number": version.version_number,
                    "matched": matched,
                    "expected_sha256": version.sha256_checksum,
                    "observed_sha256": (
                        payload.observed_sha256_checksum
                    ),
                },
            )
            self.db.commit()
            self.db.refresh(version)
            return version
        except Exception:
            self.db.rollback()
            raise

    def archive_document(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        payload: ArchiveProcurementDocumentSchema,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> ProcurementDocument:
        document = self._get_document_or_404(
            organization_id,
            document_id,
            for_update=True,
        )
        self._ensure_document_active(document)
        document.status = "archived"
        document.archived_at = datetime.now(UTC)
        document.archived_by_user_id = actor_user_id
        document.archive_reason = payload.reason
        try:
            self.documents.update_document(document)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="procurement_document.archived",
                entity_type="procurement_document",
                entity_id=document.id,
                summary="Procurement document archived.",
                details={"reason": payload.reason},
            )
            self.db.commit()
            return self._get_document_or_404(
                organization_id,
                document.id,
            )
        except Exception:
            self.db.rollback()
            raise

    def restore_document(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> ProcurementDocument:
        document = self._get_document_or_404(
            organization_id,
            document_id,
            for_update=True,
        )
        if document.status != "archived":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only archived procurement documents can be restored.",
            )
        document.status = "active"
        document.archived_at = None
        document.archived_by_user_id = None
        document.archive_reason = None
        try:
            self.documents.update_document(document)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="procurement_document.restored",
                entity_type="procurement_document",
                entity_id=document.id,
                summary="Procurement document restored.",
                details={},
            )
            self.db.commit()
            return self._get_document_or_404(
                organization_id,
                document.id,
            )
        except Exception:
            self.db.rollback()
            raise

    def create_approval_evidence(
        self,
        organization_id: uuid.UUID,
        payload: CreateProcurementApprovalEvidenceSchema,
        *,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
    ) -> ProcurementApprovalEvidence:
        self._ensure_entity_exists(
            organization_id,
            payload.entity_type.value,
            payload.entity_id,
        )
        version = None
        document_checksum = None
        if payload.procurement_document_version_id is not None:
            version = self.documents.get_version_for_organization(
                organization_id,
                payload.procurement_document_version_id,
            )
            if version is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Procurement document version not found.",
                )
            if (
                version.integrity_status != "verified"
                or version.upload_state != "available"
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Approval evidence requires an available, "
                        "checksum-verified document version."
                    ),
                )
            if (
                version.document.entity_type
                != payload.entity_type.value
                or version.document.entity_id != payload.entity_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Evidence document is linked to a different "
                        "procurement entity."
                    ),
                )
            document_checksum = version.sha256_checksum
        evidence_hash = self.evidence_hash(
            organization_id=organization_id,
            entity_type=payload.entity_type.value,
            entity_id=payload.entity_id,
            action_type=payload.action_type.value,
            decision=payload.decision.value,
            statement=payload.statement,
            document_checksum=document_checksum,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            occurred_at=payload.occurred_at,
        )
        if self.documents.evidence_hash_exists(
            organization_id,
            evidence_hash,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Identical approval evidence already exists.",
            )
        evidence = ProcurementApprovalEvidence(
            organization_id=organization_id,
            entity_type=payload.entity_type.value,
            entity_id=payload.entity_id,
            action_type=payload.action_type.value,
            decision=payload.decision.value,
            statement=payload.statement,
            procurement_document_version_id=(
                payload.procurement_document_version_id
            ),
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            occurred_at=payload.occurred_at,
            evidence_hash=evidence_hash,
            details=dict(payload.details),
        )
        try:
            self.documents.create_evidence(evidence)
            self._record_audit(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="procurement_approval_evidence.recorded",
                entity_type="procurement_approval_evidence",
                entity_id=evidence.id,
                summary="Immutable procurement approval evidence recorded.",
                details={
                    "linked_entity_type": evidence.entity_type,
                    "linked_entity_id": evidence.entity_id,
                    "action_type": evidence.action_type,
                    "decision": evidence.decision,
                    "document_version_id": (
                        evidence.procurement_document_version_id
                    ),
                    "evidence_hash": evidence.evidence_hash,
                },
            )
            self.db.commit()
            return self.get_approval_evidence(
                organization_id,
                evidence.id,
            )
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Identical approval evidence already exists.",
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def list_approval_evidence(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        entity_type: str | None,
        entity_id: uuid.UUID | None,
        action_type: str | None,
        decision: str | None,
    ) -> ProcurementApprovalEvidenceListResponse:
        return ProcurementApprovalEvidenceListResponse(
            items=self.documents.list_evidence(
                organization_id,
                skip=skip,
                limit=limit,
                entity_type=entity_type,
                entity_id=entity_id,
                action_type=action_type,
                decision=decision,
            ),
            total=self.documents.count_evidence(
                organization_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action_type=action_type,
                decision=decision,
            ),
            skip=skip,
            limit=limit,
        )

    def get_approval_evidence(
        self,
        organization_id: uuid.UUID,
        evidence_id: uuid.UUID,
    ) -> ProcurementApprovalEvidence:
        evidence = self.documents.get_evidence(
            organization_id,
            evidence_id,
        )
        if evidence is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Procurement approval evidence not found.",
            )
        return evidence
