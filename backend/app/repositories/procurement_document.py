"""Tenant-scoped persistence for procurement documents and evidence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.procurement_document import (
    ProcurementApprovalEvidence,
    ProcurementDocument,
    ProcurementDocumentVersion,
)


class ProcurementDocumentRepository:
    """Repository mutations flush but never commit."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _document_options():
        return (
            selectinload(ProcurementDocument.versions),
            joinedload(ProcurementDocument.created_by),
            joinedload(ProcurementDocument.archived_by),
        )

    def document_number_exists(
        self,
        organization_id: uuid.UUID,
        document_number: str,
    ) -> bool:
        return (
            self.db.query(ProcurementDocument.id)
            .filter(
                ProcurementDocument.organization_id == organization_id,
                func.lower(ProcurementDocument.document_number)
                == document_number.strip().lower(),
            )
            .first()
            is not None
        )

    def storage_key_exists(self, storage_key: str) -> bool:
        return (
            self.db.query(ProcurementDocumentVersion.id)
            .filter(
                ProcurementDocumentVersion.storage_key
                == storage_key.strip()
            )
            .first()
            is not None
        )

    def create_document(
        self,
        document: ProcurementDocument,
    ) -> ProcurementDocument:
        self.db.add(document)
        self.db.flush()
        return document

    def update_document(
        self,
        document: ProcurementDocument,
    ) -> ProcurementDocument:
        self.db.add(document)
        self.db.flush()
        return document

    def get_document(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> ProcurementDocument | None:
        query = (
            self.db.query(ProcurementDocument)
            .options(*self._document_options())
            .populate_existing()
            .filter(
                ProcurementDocument.id == document_id,
                ProcurementDocument.organization_id == organization_id,
            )
        )
        if for_update:
            query = query.with_for_update(of=ProcurementDocument)
        return query.first()

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
    ) -> list[ProcurementDocument]:
        query = (
            self.db.query(ProcurementDocument)
            .options(*self._document_options())
            .filter(
                ProcurementDocument.organization_id == organization_id
            )
        )
        query = self._apply_document_filters(
            query,
            entity_type=entity_type,
            entity_id=entity_id,
            document_type=document_type,
            status_filter=status_filter,
            search=search,
        )
        return (
            query.order_by(
                ProcurementDocument.created_at.desc(),
                ProcurementDocument.document_number.asc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_documents(
        self,
        organization_id: uuid.UUID,
        *,
        entity_type: str | None,
        entity_id: uuid.UUID | None,
        document_type: str | None,
        status_filter: str | None,
        search: str | None,
    ) -> int:
        query = self.db.query(func.count(ProcurementDocument.id)).filter(
            ProcurementDocument.organization_id == organization_id
        )
        query = self._apply_document_filters(
            query,
            entity_type=entity_type,
            entity_id=entity_id,
            document_type=document_type,
            status_filter=status_filter,
            search=search,
        )
        return int(query.scalar() or 0)

    @staticmethod
    def _apply_document_filters(
        query,
        *,
        entity_type: str | None,
        entity_id: uuid.UUID | None,
        document_type: str | None,
        status_filter: str | None,
        search: str | None,
    ):
        if entity_type is not None:
            query = query.filter(
                ProcurementDocument.entity_type == entity_type
            )
        if entity_id is not None:
            query = query.filter(
                ProcurementDocument.entity_id == entity_id
            )
        if document_type is not None:
            query = query.filter(
                ProcurementDocument.document_type == document_type
            )
        if status_filter is not None:
            query = query.filter(
                ProcurementDocument.status == status_filter
            )
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    ProcurementDocument.document_number.ilike(pattern),
                    ProcurementDocument.title.ilike(pattern),
                    ProcurementDocument.description.ilike(pattern),
                )
            )
        return query

    def next_version_number(
        self,
        document_id: uuid.UUID,
    ) -> int:
        highest = (
            self.db.query(
                func.max(ProcurementDocumentVersion.version_number)
            )
            .filter(
                ProcurementDocumentVersion.procurement_document_id
                == document_id
            )
            .scalar()
        )
        return int(highest or 0) + 1

    def create_version(
        self,
        version: ProcurementDocumentVersion,
    ) -> ProcurementDocumentVersion:
        self.db.add(version)
        self.db.flush()
        return version

    def update_version(
        self,
        version: ProcurementDocumentVersion,
    ) -> ProcurementDocumentVersion:
        self.db.add(version)
        self.db.flush()
        return version

    def get_version(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> ProcurementDocumentVersion | None:
        query = (
            self.db.query(ProcurementDocumentVersion)
            .join(
                ProcurementDocument,
                ProcurementDocument.id
                == ProcurementDocumentVersion.procurement_document_id,
            )
            .filter(
                ProcurementDocument.organization_id == organization_id,
                ProcurementDocument.id == document_id,
                ProcurementDocumentVersion.id == version_id,
            )
        )
        if for_update:
            query = query.with_for_update(
                of=ProcurementDocumentVersion
            )
        return query.first()

    def get_version_for_organization(
        self,
        organization_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> ProcurementDocumentVersion | None:
        return (
            self.db.query(ProcurementDocumentVersion)
            .options(joinedload(ProcurementDocumentVersion.document))
            .join(
                ProcurementDocument,
                ProcurementDocument.id
                == ProcurementDocumentVersion.procurement_document_id,
            )
            .filter(
                ProcurementDocument.organization_id == organization_id,
                ProcurementDocumentVersion.id == version_id,
            )
            .first()
        )

    def list_versions(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> list[ProcurementDocumentVersion]:
        return (
            self.db.query(ProcurementDocumentVersion)
            .join(
                ProcurementDocument,
                ProcurementDocument.id
                == ProcurementDocumentVersion.procurement_document_id,
            )
            .filter(
                ProcurementDocument.organization_id == organization_id,
                ProcurementDocument.id == document_id,
            )
            .order_by(
                ProcurementDocumentVersion.version_number.desc()
            )
            .all()
        )

    def evidence_hash_exists(
        self,
        organization_id: uuid.UUID,
        evidence_hash: str,
    ) -> bool:
        return (
            self.db.query(ProcurementApprovalEvidence.id)
            .filter(
                ProcurementApprovalEvidence.organization_id
                == organization_id,
                ProcurementApprovalEvidence.evidence_hash
                == evidence_hash,
            )
            .first()
            is not None
        )

    def create_evidence(
        self,
        evidence: ProcurementApprovalEvidence,
    ) -> ProcurementApprovalEvidence:
        self.db.add(evidence)
        self.db.flush()
        return evidence

    def get_evidence(
        self,
        organization_id: uuid.UUID,
        evidence_id: uuid.UUID,
    ) -> ProcurementApprovalEvidence | None:
        return (
            self.db.query(ProcurementApprovalEvidence)
            .options(
                joinedload(
                    ProcurementApprovalEvidence.document_version
                ),
                joinedload(ProcurementApprovalEvidence.actor),
            )
            .filter(
                ProcurementApprovalEvidence.id == evidence_id,
                ProcurementApprovalEvidence.organization_id
                == organization_id,
            )
            .first()
        )

    def list_evidence(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        entity_type: str | None,
        entity_id: uuid.UUID | None,
        action_type: str | None,
        decision: str | None,
    ) -> list[ProcurementApprovalEvidence]:
        query = self.db.query(ProcurementApprovalEvidence).filter(
            ProcurementApprovalEvidence.organization_id
            == organization_id
        )
        query = self._apply_evidence_filters(
            query,
            entity_type=entity_type,
            entity_id=entity_id,
            action_type=action_type,
            decision=decision,
        )
        return (
            query.order_by(
                ProcurementApprovalEvidence.occurred_at.desc(),
                ProcurementApprovalEvidence.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_evidence(
        self,
        organization_id: uuid.UUID,
        *,
        entity_type: str | None,
        entity_id: uuid.UUID | None,
        action_type: str | None,
        decision: str | None,
    ) -> int:
        query = self.db.query(
            func.count(ProcurementApprovalEvidence.id)
        ).filter(
            ProcurementApprovalEvidence.organization_id
            == organization_id
        )
        query = self._apply_evidence_filters(
            query,
            entity_type=entity_type,
            entity_id=entity_id,
            action_type=action_type,
            decision=decision,
        )
        return int(query.scalar() or 0)

    @staticmethod
    def _apply_evidence_filters(
        query,
        *,
        entity_type: str | None,
        entity_id: uuid.UUID | None,
        action_type: str | None,
        decision: str | None,
    ):
        if entity_type is not None:
            query = query.filter(
                ProcurementApprovalEvidence.entity_type == entity_type
            )
        if entity_id is not None:
            query = query.filter(
                ProcurementApprovalEvidence.entity_id == entity_id
            )
        if action_type is not None:
            query = query.filter(
                ProcurementApprovalEvidence.action_type == action_type
            )
        if decision is not None:
            query = query.filter(
                ProcurementApprovalEvidence.decision == decision
            )
        return query
