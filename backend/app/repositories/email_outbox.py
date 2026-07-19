"""
Email outbox repository.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

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
            query.order_by(EmailOutbox.created_at.desc())
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

        return int(query.count())

    def _filtered_query(
        self,
        *,
        organization_id: uuid.UUID,
        status_filter: str | None,
        provider: str | None,
        recipient_email: str | None,
        document_delivery_id: uuid.UUID | None,
    ):
        query = self.db.query(EmailOutbox).filter(
            EmailOutbox.organization_id == organization_id,
            EmailOutbox.is_active.is_(True),
        )

        if status_filter is not None:
            query = query.filter(
                EmailOutbox.status == status_filter,
            )

        if provider is not None:
            query = query.filter(
                EmailOutbox.provider == provider,
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
