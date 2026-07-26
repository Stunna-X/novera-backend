"""
Email outbox repository.

Provides organization-scoped reads and PostgreSQL-safe worker
claiming using FOR UPDATE SKIP LOCKED.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import (
    Session,
    joinedload,
    lazyload,
)

from app.models.email_outbox import EmailOutbox


class EmailOutboxRepository:
    """
    Persistence helper for queued outbound emails.
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def create(
        self,
        email: EmailOutbox,
    ) -> EmailOutbox:
        self.db.add(email)
        self.db.flush()

        return email

    def get_for_organization(
        self,
        *,
        organization_id: uuid.UUID,
        email_outbox_id: uuid.UUID,
    ) -> EmailOutbox | None:
        return (
            self.db.query(EmailOutbox)
            .filter(
                EmailOutbox.organization_id == organization_id,
                EmailOutbox.id == email_outbox_id,
                EmailOutbox.is_active.is_(True),
            )
            .first()
        )

    def get_claimed_for_dispatch(
        self,
        *,
        email_outbox_id: uuid.UUID,
    ) -> EmailOutbox | None:
        """
        Return one message currently owned by a worker.
        """

        return (
            self.db.query(EmailOutbox)
            .options(
                joinedload(
                    EmailOutbox.document_delivery
                ),
                joinedload(
                    EmailOutbox.queued_by
                ),
            )
            .filter(
                EmailOutbox.id == email_outbox_id,
                EmailOutbox.status == "sending",
                EmailOutbox.is_active.is_(True),
            )
            .first()
        )

    def lock_due_for_dispatch(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[EmailOutbox]:
        """
        Lock due messages without blocking other workers.

        The caller must update the selected rows and commit before
        another transaction can process them.
        """

        statement = (
            select(EmailOutbox)
            .options(
                lazyload("*"),
            )
            .where(
                EmailOutbox.is_active.is_(True),
                EmailOutbox.provider != "manual",
                EmailOutbox.status.in_(
                    (
                        "queued",
                        "failed",
                    )
                ),
                EmailOutbox.attempts
                < EmailOutbox.max_attempts,
                or_(
                    EmailOutbox.next_attempt_at.is_(None),
                    EmailOutbox.next_attempt_at <= now,
                ),
            )
            .order_by(
                EmailOutbox.next_attempt_at
                .asc()
                .nullsfirst(),
                EmailOutbox.queued_at.asc(),
                EmailOutbox.id.asc(),
            )
            .limit(limit)
            .with_for_update(
                skip_locked=True,
                of=EmailOutbox,
            )
        )

        return list(
            self.db.scalars(statement).all()
        )

    def lock_stale_sending(
        self,
        *,
        stale_before: datetime,
        limit: int,
    ) -> list[EmailOutbox]:
        """
        Lock worker claims that were abandoned or crashed.
        """

        statement = (
            select(EmailOutbox)
            .options(
                lazyload("*"),
            )
            .where(
                EmailOutbox.is_active.is_(True),
                EmailOutbox.status == "sending",
                EmailOutbox.updated_at <= stale_before,
            )
            .order_by(
                EmailOutbox.updated_at.asc(),
                EmailOutbox.id.asc(),
            )
            .limit(limit)
            .with_for_update(
                skip_locked=True,
                of=EmailOutbox,
            )
        )

        return list(
            self.db.scalars(statement).all()
        )

    def list_for_organization(
        self,
        *,
        organization_id: uuid.UUID,
        skip: int,
        limit: int,
        status_filter: str | None = None,
        provider: str | None = None,
        recipient_email: str | None = None,
        document_delivery_id: uuid.UUID | None = None,
    ) -> list[EmailOutbox]:
        query = self._filtered_query(
            organization_id=organization_id,
            status_filter=status_filter,
            provider=provider,
            recipient_email=recipient_email,
            document_delivery_id=document_delivery_id,
        )

        return (
            query.order_by(
                EmailOutbox.created_at.desc()
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_organization(
        self,
        *,
        organization_id: uuid.UUID,
        status_filter: str | None = None,
        provider: str | None = None,
        recipient_email: str | None = None,
        document_delivery_id: uuid.UUID | None = None,
    ) -> int:
        query = self._filtered_query(
            organization_id=organization_id,
            status_filter=status_filter,
            provider=provider,
            recipient_email=recipient_email,
            document_delivery_id=document_delivery_id,
        )

        return int(
            query.count()
        )

    def _filtered_query(
        self,
        *,
        organization_id: uuid.UUID,
        status_filter: str | None,
        provider: str | None,
        recipient_email: str | None,
        document_delivery_id: uuid.UUID | None,
    ):
        query = self.db.query(
            EmailOutbox
        ).filter(
            EmailOutbox.organization_id
            == organization_id,
            EmailOutbox.is_active.is_(True),
        )

        if status_filter is not None:
            query = query.filter(
                EmailOutbox.status
                == status_filter,
            )

        if provider is not None:
            query = query.filter(
                EmailOutbox.provider
                == provider,
            )

        if recipient_email is not None:
            query = query.filter(
                EmailOutbox.to_email.ilike(
                    f"%{recipient_email.strip()}%"
                )
            )

        if document_delivery_id is not None:
            query = query.filter(
                EmailOutbox.document_delivery_id
                == document_delivery_id,
            )

        return query