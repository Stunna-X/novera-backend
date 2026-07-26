"""
Audit log repository.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    """
    Database operations for audit logs.
    """

    def __init__(
        self,
        db: Session,
    ):
        super().__init__(
            db,
            AuditLog,
        )

    def create_audit_log(
        self,
        audit_log: AuditLog,
    ) -> AuditLog:
        """
        Persist an audit log.
        """

        return self.create(
            audit_log
        )

    def get_for_organization(
        self,
        *,
        organization_id: uuid.UUID,
        audit_log_id: uuid.UUID,
    ) -> AuditLog | None:
        """
        Retrieve one organization audit log.
        """

        return (
            self.db.query(AuditLog)
            .filter(
                AuditLog.id == audit_log_id,
                AuditLog.organization_id == organization_id,
            )
            .first()
        )

    def _filtered_query(
        self,
        *,
        organization_id: uuid.UUID,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        status_filter: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ):
        """
        Build filtered audit-log query.
        """

        query = self.db.query(AuditLog).filter(
            AuditLog.organization_id == organization_id,
        )

        if action:
            query = query.filter(
                AuditLog.action == action
            )

        if entity_type:
            query = query.filter(
                AuditLog.entity_type == entity_type
            )

        if entity_id:
            query = query.filter(
                AuditLog.entity_id == entity_id
            )

        if actor_user_id:
            query = query.filter(
                AuditLog.actor_user_id == actor_user_id
            )

        if status_filter:
            query = query.filter(
                AuditLog.status == status_filter
            )

        if date_from:
            query = query.filter(
                AuditLog.created_at >= date_from
            )

        if date_to:
            query = query.filter(
                AuditLog.created_at <= date_to
            )

        return query

    def list_for_organization(
        self,
        *,
        organization_id: uuid.UUID,
        skip: int,
        limit: int,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        status_filter: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[AuditLog]:
        """
        List organization audit logs.
        """

        return (
            self._filtered_query(
                organization_id=organization_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                actor_user_id=actor_user_id,
                status_filter=status_filter,
                date_from=date_from,
                date_to=date_to,
            )
            .order_by(
                AuditLog.created_at.desc(),
                AuditLog.id.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_organization(
        self,
        *,
        organization_id: uuid.UUID,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        status_filter: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> int:
        """
        Count organization audit logs.
        """

        return (
            self._filtered_query(
                organization_id=organization_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                actor_user_id=actor_user_id,
                status_filter=status_filter,
                date_from=date_from,
                date_to=date_to,
            )
            .count()
        )
