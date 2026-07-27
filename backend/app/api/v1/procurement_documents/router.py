"""Organization-scoped procurement document and evidence endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import OrganizationContext, require_permission
from app.database.session import get_db
from app.schemas.procurement_document import (
    ArchiveProcurementDocumentSchema,
    CreateProcurementApprovalEvidenceSchema,
    CreateProcurementDocumentSchema,
    CreateProcurementDocumentVersionSchema,
    ProcurementApprovalActionType,
    ProcurementApprovalDecision,
    ProcurementApprovalEntityType,
    ProcurementApprovalEvidenceListResponse,
    ProcurementApprovalEvidenceResponse,
    ProcurementDocumentEntityType,
    ProcurementDocumentListResponse,
    ProcurementDocumentResponse,
    ProcurementDocumentStatus,
    ProcurementDocumentType,
    ProcurementDocumentVersionResponse,
    UpdateProcurementDocumentSchema,
    VerifyProcurementDocumentVersionSchema,
)
from app.services.procurement_document_service import (
    ProcurementDocumentService,
)


documents_router = APIRouter(
    prefix="/organizations/{organization_id}/procurement-documents",
    tags=["Procurement Documents"],
)

evidence_router = APIRouter(
    prefix=(
        "/organizations/{organization_id}/"
        "procurement-approval-evidence"
    ),
    tags=["Procurement Approval Evidence"],
)


@documents_router.post(
    "",
    response_model=ProcurementDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create procurement document",
)
def create_procurement_document(
    payload: CreateProcurementDocumentSchema,
    context: OrganizationContext = Depends(
        require_permission("procurement_documents.create")
    ),
    db: Session = Depends(get_db),
) -> ProcurementDocumentResponse:
    return ProcurementDocumentService(db).create_document(
        context.organization.id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@documents_router.get(
    "",
    response_model=ProcurementDocumentListResponse,
    summary="List procurement documents",
)
def list_procurement_documents(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    entity_type: ProcurementDocumentEntityType | None = Query(
        default=None
    ),
    entity_id: uuid.UUID | None = Query(default=None),
    document_type: ProcurementDocumentType | None = Query(
        default=None
    ),
    status_filter: ProcurementDocumentStatus | None = Query(
        default=None,
        alias="status",
    ),
    search: str | None = Query(default=None, max_length=200),
    context: OrganizationContext = Depends(
        require_permission("procurement_documents.read")
    ),
    db: Session = Depends(get_db),
) -> ProcurementDocumentListResponse:
    return ProcurementDocumentService(db).list_documents(
        context.organization.id,
        skip=skip,
        limit=limit,
        entity_type=(
            entity_type.value if entity_type is not None else None
        ),
        entity_id=entity_id,
        document_type=(
            document_type.value if document_type is not None else None
        ),
        status_filter=(
            status_filter.value
            if status_filter is not None
            else None
        ),
        search=search,
    )


@documents_router.get(
    "/{document_id}",
    response_model=ProcurementDocumentResponse,
    summary="Get procurement document",
)
def get_procurement_document(
    document_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("procurement_documents.read")
    ),
    db: Session = Depends(get_db),
) -> ProcurementDocumentResponse:
    return ProcurementDocumentService(db).get_document(
        context.organization.id,
        document_id,
    )


@documents_router.patch(
    "/{document_id}",
    response_model=ProcurementDocumentResponse,
    summary="Update procurement document",
)
def update_procurement_document(
    document_id: uuid.UUID,
    payload: UpdateProcurementDocumentSchema,
    context: OrganizationContext = Depends(
        require_permission("procurement_documents.update")
    ),
    db: Session = Depends(get_db),
) -> ProcurementDocumentResponse:
    return ProcurementDocumentService(db).update_document(
        context.organization.id,
        document_id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@documents_router.post(
    "/{document_id}/versions",
    response_model=ProcurementDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register procurement document version",
)
def create_procurement_document_version(
    document_id: uuid.UUID,
    payload: CreateProcurementDocumentVersionSchema,
    context: OrganizationContext = Depends(
        require_permission("procurement_documents.update")
    ),
    db: Session = Depends(get_db),
) -> ProcurementDocumentResponse:
    return ProcurementDocumentService(db).create_version(
        context.organization.id,
        document_id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@documents_router.get(
    "/{document_id}/versions",
    response_model=list[ProcurementDocumentVersionResponse],
    summary="List procurement document versions",
)
def list_procurement_document_versions(
    document_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("procurement_documents.read")
    ),
    db: Session = Depends(get_db),
) -> list[ProcurementDocumentVersionResponse]:
    return ProcurementDocumentService(db).list_versions(
        context.organization.id,
        document_id,
    )


@documents_router.post(
    "/{document_id}/versions/{version_id}/verify",
    response_model=ProcurementDocumentVersionResponse,
    summary="Verify procurement document checksum",
)
def verify_procurement_document_version(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: VerifyProcurementDocumentVersionSchema,
    context: OrganizationContext = Depends(
        require_permission("procurement_documents.verify")
    ),
    db: Session = Depends(get_db),
) -> ProcurementDocumentVersionResponse:
    return ProcurementDocumentService(db).verify_version(
        context.organization.id,
        document_id,
        version_id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@documents_router.post(
    "/{document_id}/archive",
    response_model=ProcurementDocumentResponse,
    summary="Archive procurement document",
)
def archive_procurement_document(
    document_id: uuid.UUID,
    payload: ArchiveProcurementDocumentSchema,
    context: OrganizationContext = Depends(
        require_permission("procurement_documents.archive")
    ),
    db: Session = Depends(get_db),
) -> ProcurementDocumentResponse:
    return ProcurementDocumentService(db).archive_document(
        context.organization.id,
        document_id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@documents_router.post(
    "/{document_id}/restore",
    response_model=ProcurementDocumentResponse,
    summary="Restore procurement document",
)
def restore_procurement_document(
    document_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("procurement_documents.archive")
    ),
    db: Session = Depends(get_db),
) -> ProcurementDocumentResponse:
    return ProcurementDocumentService(db).restore_document(
        context.organization.id,
        document_id,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@evidence_router.post(
    "",
    response_model=ProcurementApprovalEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record procurement approval evidence",
)
def create_procurement_approval_evidence(
    payload: CreateProcurementApprovalEvidenceSchema,
    context: OrganizationContext = Depends(
        require_permission("procurement_approval_evidence.create")
    ),
    db: Session = Depends(get_db),
) -> ProcurementApprovalEvidenceResponse:
    return ProcurementDocumentService(db).create_approval_evidence(
        context.organization.id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@evidence_router.get(
    "",
    response_model=ProcurementApprovalEvidenceListResponse,
    summary="List procurement approval evidence",
)
def list_procurement_approval_evidence(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    entity_type: ProcurementApprovalEntityType | None = Query(
        default=None
    ),
    entity_id: uuid.UUID | None = Query(default=None),
    action_type: ProcurementApprovalActionType | None = Query(
        default=None
    ),
    decision: ProcurementApprovalDecision | None = Query(
        default=None
    ),
    context: OrganizationContext = Depends(
        require_permission("procurement_approval_evidence.read")
    ),
    db: Session = Depends(get_db),
) -> ProcurementApprovalEvidenceListResponse:
    return ProcurementDocumentService(db).list_approval_evidence(
        context.organization.id,
        skip=skip,
        limit=limit,
        entity_type=(
            entity_type.value if entity_type is not None else None
        ),
        entity_id=entity_id,
        action_type=(
            action_type.value if action_type is not None else None
        ),
        decision=decision.value if decision is not None else None,
    )


@evidence_router.get(
    "/{evidence_id}",
    response_model=ProcurementApprovalEvidenceResponse,
    summary="Get procurement approval evidence",
)
def get_procurement_approval_evidence(
    evidence_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("procurement_approval_evidence.read")
    ),
    db: Session = Depends(get_db),
) -> ProcurementApprovalEvidenceResponse:
    return ProcurementDocumentService(db).get_approval_evidence(
        context.organization.id,
        evidence_id,
    )
