"""
Audit log routes.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    OrganizationContext,
    require_permission,
)
from app.database.session import get_db
from app.schemas.audit_log import (
    AuditLogListResponse,
    AuditLogResponse,
    AuditLogStatus,
)
from app.services.audit_log_service import AuditLogService


router = APIRouter(
    prefix="/organizations/{organization_id}/audit-logs",
    tags=["Audit Logs"],
)


@router.get(
    "",
    response_model=AuditLogListResponse,
    summary="List audit logs",
)
def list_audit_logs(
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
    ),
    action: str | None = Query(
        default=None,
        min_length=2,
        max_length=120,
    ),
    entity_type: str | None = Query(
        default=None,
        min_length=2,
        max_length=80,
    ),
    entity_id: uuid.UUID | None = Query(
        default=None,
    ),
    actor_user_id: uuid.UUID | None = Query(
        default=None,
    ),
    audit_status: AuditLogStatus | None = Query(
        default=None,
        alias="status",
    ),
    date_from: datetime | None = Query(
        default=None,
    ),
    date_to: datetime | None = Query(
        default=None,
    ),
    context: OrganizationContext = Depends(
        require_permission("audit_logs.read")
    ),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    """
    Return organization audit logs with optional filters.
    """

    service = AuditLogService(db)

    return service.list_audit_logs(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        status_filter=audit_status,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/export",
    summary="Export audit logs as CSV",
)
def export_audit_logs(
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=10000,
        ge=1,
        le=10000,
    ),
    action: str | None = Query(
        default=None,
        min_length=2,
        max_length=120,
    ),
    entity_type: str | None = Query(
        default=None,
        min_length=2,
        max_length=80,
    ),
    entity_id: uuid.UUID | None = Query(
        default=None,
    ),
    actor_user_id: uuid.UUID | None = Query(
        default=None,
    ),
    audit_status: AuditLogStatus | None = Query(
        default=None,
        alias="status",
    ),
    date_from: datetime | None = Query(
        default=None,
    ),
    date_to: datetime | None = Query(
        default=None,
    ),
    context: OrganizationContext = Depends(
        require_permission("audit_logs.read")
    ),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    Export filtered organization audit logs as a CSV file.
    """

    service = AuditLogService(db)

    csv_content = service.export_audit_logs_csv(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        status_filter=audit_status,
        date_from=date_from,
        date_to=date_to,
    )

    timestamp = datetime.utcnow().strftime(
        "%Y%m%d-%H%M%S"
    )

    filename = f"novera-audit-logs-{timestamp}.csv"

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            ),
        },
    )


@router.get(
    "/{audit_log_id}",
    response_model=AuditLogResponse,
    summary="Get audit log",
)
def get_audit_log(
    audit_log_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("audit_logs.read")
    ),
    db: Session = Depends(get_db),
) -> AuditLogResponse:
    """
    Return one organization audit log.
    """

    service = AuditLogService(db)

    return service.get_audit_log(
        organization_id=context.organization.id,
        audit_log_id=audit_log_id,
    )
