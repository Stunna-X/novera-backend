"""
Audit log service.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.repositories.audit_log import AuditLogRepository
from app.schemas.audit_log import (
    AuditLogCreate,
    AuditLogListResponse,
    AuditLogResponse,
)


class AuditLogService:
    """
    Handles audit-log read and write logic.
    """

    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.audit_logs = AuditLogRepository(db)

    @staticmethod
    def _actor_fields(
        audit_log: AuditLog,
    ) -> dict[str, object]:
        """
        Build flattened actor fields.
        """

        actor = audit_log.actor

        return {
            "actor_first_name": (
                actor.first_name
                if actor is not None
                else None
            ),
            "actor_last_name": (
                actor.last_name
                if actor is not None
                else None
            ),
            "actor_email": (
                actor.email
                if actor is not None
                else None
            ),
        }

    @classmethod
    def _build_response(
        cls,
        audit_log: AuditLog,
    ) -> AuditLogResponse:
        """
        Convert audit log model to API response.
        """

        return AuditLogResponse(
            id=audit_log.id,
            organization_id=audit_log.organization_id,
            actor_user_id=audit_log.actor_user_id,
            actor_membership_id=(
                audit_log.actor_membership_id
            ),
            **cls._actor_fields(audit_log),
            action=audit_log.action,
            entity_type=audit_log.entity_type,
            entity_id=audit_log.entity_id,
            summary=audit_log.summary,
            status=audit_log.status,
            request_method=audit_log.request_method,
            request_path=audit_log.request_path,
            ip_address=audit_log.ip_address,
            user_agent=audit_log.user_agent,
            details=audit_log.details or {},
            created_at=audit_log.created_at,
            updated_at=audit_log.updated_at,
        )

    def record_event(
        self,
        organization_id: uuid.UUID,
        payload: AuditLogCreate,
        *,
        commit: bool = False,
    ) -> AuditLogResponse:
        """
        Record an audit event.

        By default this does not commit, so business services can
        write audit events inside their own transaction.
        """

        try:
            audit_log = self.audit_logs.create_audit_log(
                AuditLog(
                    organization_id=organization_id,
                    actor_user_id=payload.actor_user_id,
                    actor_membership_id=(
                        payload.actor_membership_id
                    ),
                    action=payload.action.strip().lower(),
                    entity_type=(
                        payload.entity_type.strip().lower()
                        if payload.entity_type
                        else None
                    ),
                    entity_id=payload.entity_id,
                    summary=payload.summary,
                    status=payload.status,
                    request_method=(
                        payload.request_method.upper()
                        if payload.request_method
                        else None
                    ),
                    request_path=payload.request_path,
                    ip_address=payload.ip_address,
                    user_agent=payload.user_agent,
                    details=payload.details,
                )
            )

            self.db.flush()

            if commit:
                self.db.commit()
                self.db.refresh(audit_log)

            return self._build_response(audit_log)

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The audit log could not be recorded.",
            ) from exc

    def list_audit_logs(
        self,
        *,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        status_filter: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> AuditLogListResponse:
        """
        List organization audit logs.
        """

        if (
            date_from is not None
            and date_to is not None
            and date_from > date_to
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="date_from cannot be after date_to.",
            )

        normalized_action = (
            action.strip().lower()
            if action
            else None
        )

        normalized_entity_type = (
            entity_type.strip().lower()
            if entity_type
            else None
        )

        total = self.audit_logs.count_for_organization(
            organization_id=organization_id,
            action=normalized_action,
            entity_type=normalized_entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            status_filter=status_filter,
            date_from=date_from,
            date_to=date_to,
        )

        items = self.audit_logs.list_for_organization(
            organization_id=organization_id,
            skip=skip,
            limit=limit,
            action=normalized_action,
            entity_type=normalized_entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            status_filter=status_filter,
            date_from=date_from,
            date_to=date_to,
        )

        return AuditLogListResponse(
            items=[
                self._build_response(item)
                for item in items
            ],
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_audit_log(
        self,
        *,
        organization_id: uuid.UUID,
        audit_log_id: uuid.UUID,
    ) -> AuditLogResponse:
        """
        Return one organization audit log.
        """

        audit_log = (
            self.audit_logs.get_for_organization(
                organization_id=organization_id,
                audit_log_id=audit_log_id,
            )
        )

        if audit_log is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit log not found.",
            )

        return self._build_response(audit_log)
