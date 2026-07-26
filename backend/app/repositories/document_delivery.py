"""
Document delivery repository.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.document_delivery import DocumentDelivery


class DocumentDeliveryRepository:
    """
    Persistence helper for document delivery records.
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def create(
        self,
        delivery: DocumentDelivery,
    ) -> DocumentDelivery:
        self.db.add(delivery)
        self.db.flush()
        return delivery

    def get_for_organization(
        self,
        *,
        organization_id: uuid.UUID,
        delivery_id: uuid.UUID,
    ) -> DocumentDelivery | None:
        return (
            self.db.query(DocumentDelivery)
            .filter(
                DocumentDelivery.organization_id == organization_id,
                DocumentDelivery.id == delivery_id,
                DocumentDelivery.is_active.is_(True),
            )
            .first()
        )

    def list_for_organization(
        self,
        *,
        organization_id: uuid.UUID,
        skip: int,
        limit: int,
        document_type: str | None = None,
        document_id: uuid.UUID | None = None,
        delivery_status: str | None = None,
        recipient_email: str | None = None,
    ) -> list[DocumentDelivery]:
        query = self._filtered_query(
            organization_id=organization_id,
            document_type=document_type,
            document_id=document_id,
            delivery_status=delivery_status,
            recipient_email=recipient_email,
        )

        return (
            query.order_by(DocumentDelivery.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_organization(
        self,
        *,
        organization_id: uuid.UUID,
        document_type: str | None = None,
        document_id: uuid.UUID | None = None,
        delivery_status: str | None = None,
        recipient_email: str | None = None,
    ) -> int:
        query = self._filtered_query(
            organization_id=organization_id,
            document_type=document_type,
            document_id=document_id,
            delivery_status=delivery_status,
            recipient_email=recipient_email,
        )

        return int(query.count())

    def _filtered_query(
        self,
        *,
        organization_id: uuid.UUID,
        document_type: str | None,
        document_id: uuid.UUID | None,
        delivery_status: str | None,
        recipient_email: str | None,
    ):
        query = self.db.query(DocumentDelivery).filter(
            DocumentDelivery.organization_id == organization_id,
            DocumentDelivery.is_active.is_(True),
        )

        if document_type is not None:
            query = query.filter(
                DocumentDelivery.document_type == document_type,
            )

        if document_id is not None:
            query = query.filter(
                DocumentDelivery.document_id == document_id,
            )

        if delivery_status is not None:
            query = query.filter(
                DocumentDelivery.delivery_status == delivery_status,
            )

        if recipient_email is not None:
            query = query.filter(
                DocumentDelivery.recipient_email.ilike(
                    f"%{recipient_email.strip()}%"
                )
            )

        return query
