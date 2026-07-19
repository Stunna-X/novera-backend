"""
Document delivery service.

Creates document delivery records and queues email outbox jobs.
This service does not perform network email sending.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status

from app.core.config import settings
from sqlalchemy.orm import Session

from app.models.document_delivery import DocumentDelivery
from app.models.invoice import Invoice
from app.models.quote import Quote
from app.repositories.document_delivery import (
    DocumentDeliveryRepository,
)
from app.schemas.audit_log import AuditLogCreate
from app.schemas.document_delivery import (
    DocumentDeliveryListResponse,
    DocumentDeliveryResponse,
    DocumentDeliverySendRequest,
)
from app.services.audit_log_service import AuditLogService
from app.services.document_pdf_service import DocumentPDFService
from app.services.email_outbox_service import EmailOutboxService


class DocumentDeliveryService:
    """
    Business logic for document delivery tracking.
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db
        self.deliveries = DocumentDeliveryRepository(db)
        self.audit_logs = AuditLogService(db)
        self.pdfs = DocumentPDFService(db)
        self.email_outbox = EmailOutboxService(db)

    def send_invoice(
        self,
        *,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        payload: DocumentDeliverySendRequest,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
        include_inactive: bool = False,
    ) -> DocumentDeliveryResponse:
        """
        Queue an invoice email and record delivery metadata.
        """

        invoice = self._get_invoice_or_404(
            organization_id=organization_id,
            invoice_id=invoice_id,
            include_inactive=include_inactive,
        )

        _, filename = self.pdfs.build_invoice_pdf(
            organization_id=organization_id,
            invoice_id=invoice_id,
            include_inactive=include_inactive,
        )

        subject = (
            payload.subject
            or f"Invoice {invoice.invoice_number}"
        )

        message = (
            payload.message
            or (
                f"Please find invoice {invoice.invoice_number} "
                "attached for your records."
            )
        )

        delivery = self._create_delivery(
            organization_id=organization_id,
            document_type="invoice",
            document_id=invoice.id,
            document_number=invoice.invoice_number,
            recipient_email=str(payload.recipient_email).lower(),
            recipient_name=(
                payload.recipient_name
                or invoice.customer_name
            ),
            subject=subject,
            message=message,
            pdf_filename=filename if payload.include_pdf else None,
            actor_user_id=actor_user_id,
            details={
                "customer_id": str(invoice.customer_id),
                "work_order_id": str(invoice.work_order_id),
                "invoice_status": invoice.status,
                "include_pdf": payload.include_pdf,
                "provider_mode": "email_outbox_queued",
            },
        )

        email = self.email_outbox.enqueue_for_delivery(
            delivery=delivery,
            body_text=message,
            attachment_filename=(
                filename if payload.include_pdf else None
            ),
            actor_user_id=actor_user_id,
        )

        delivery.details = {
            **(delivery.details or {}),
            "email_outbox_id": str(email.id),
            "email_outbox_status": email.status,
            "provider": email.provider,
        }

        self._record_audit_event(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            delivery=delivery,
            email_outbox_id=email.id,
        )

        self.db.commit()
        self.db.refresh(delivery)

        return self._build_response(delivery)

    def send_quote(
        self,
        *,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        payload: DocumentDeliverySendRequest,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
        include_inactive: bool = False,
    ) -> DocumentDeliveryResponse:
        """
        Queue a quote email and record delivery metadata.
        """

        quote = self._get_quote_or_404(
            organization_id=organization_id,
            quote_id=quote_id,
            include_inactive=include_inactive,
        )

        _, filename = self.pdfs.build_quote_pdf(
            organization_id=organization_id,
            quote_id=quote_id,
            include_inactive=include_inactive,
        )

        subject = (
            payload.subject
            or f"Quote {quote.quote_number}"
        )

        message = (
            payload.message
            or (
                f"Please find quote {quote.quote_number} "
                "attached for your review."
            )
        )

        delivery = self._create_delivery(
            organization_id=organization_id,
            document_type="quote",
            document_id=quote.id,
            document_number=quote.quote_number,
            recipient_email=str(payload.recipient_email).lower(),
            recipient_name=(
                payload.recipient_name
                or quote.customer_name
            ),
            subject=subject,
            message=message,
            pdf_filename=filename if payload.include_pdf else None,
            actor_user_id=actor_user_id,
            details={
                "customer_id": str(quote.customer_id),
                "customer_site_id": (
                    str(quote.customer_site_id)
                    if quote.customer_site_id
                    else None
                ),
                "quote_status": quote.status,
                "include_pdf": payload.include_pdf,
                "provider_mode": "email_outbox_queued",
            },
        )

        email = self.email_outbox.enqueue_for_delivery(
            delivery=delivery,
            body_text=message,
            attachment_filename=(
                filename if payload.include_pdf else None
            ),
            actor_user_id=actor_user_id,
        )

        delivery.details = {
            **(delivery.details or {}),
            "email_outbox_id": str(email.id),
            "email_outbox_status": email.status,
            "provider": email.provider,
        }

        self._record_audit_event(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            delivery=delivery,
            email_outbox_id=email.id,
        )

        self.db.commit()
        self.db.refresh(delivery)

        return self._build_response(delivery)

    def list_deliveries(
        self,
        *,
        organization_id: uuid.UUID,
        skip: int,
        limit: int,
        document_type: str | None = None,
        document_id: uuid.UUID | None = None,
        delivery_status: str | None = None,
        recipient_email: str | None = None,
    ) -> DocumentDeliveryListResponse:
        """
        List document deliveries for an organization.
        """

        total = self.deliveries.count_for_organization(
            organization_id=organization_id,
            document_type=document_type,
            document_id=document_id,
            delivery_status=delivery_status,
            recipient_email=recipient_email,
        )

        items = self.deliveries.list_for_organization(
            organization_id=organization_id,
            skip=skip,
            limit=limit,
            document_type=document_type,
            document_id=document_id,
            delivery_status=delivery_status,
            recipient_email=recipient_email,
        )

        return DocumentDeliveryListResponse(
            items=[
                self._build_response(item)
                for item in items
            ],
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_delivery(
        self,
        *,
        organization_id: uuid.UUID,
        delivery_id: uuid.UUID,
    ) -> DocumentDeliveryResponse:
        """
        Return one delivery record.
        """

        delivery = self.deliveries.get_for_organization(
            organization_id=organization_id,
            delivery_id=delivery_id,
        )

        if delivery is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document delivery not found.",
            )

        return self._build_response(delivery)

    def _get_invoice_or_404(
        self,
        *,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        include_inactive: bool,
    ) -> Invoice:
        query = self.db.query(Invoice).filter(
            Invoice.organization_id == organization_id,
            Invoice.id == invoice_id,
        )

        if not include_inactive:
            query = query.filter(
                Invoice.is_active.is_(True)
            )

        invoice = query.first()

        if invoice is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found.",
            )

        return invoice

    def _get_quote_or_404(
        self,
        *,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        include_inactive: bool,
    ) -> Quote:
        query = self.db.query(Quote).filter(
            Quote.organization_id == organization_id,
            Quote.id == quote_id,
        )

        if not include_inactive:
            query = query.filter(
                Quote.is_active.is_(True)
            )

        quote = query.first()

        if quote is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quote not found.",
            )

        return quote

    def _create_delivery(
        self,
        *,
        organization_id: uuid.UUID,
        document_type: str,
        document_id: uuid.UUID,
        document_number: str,
        recipient_email: str,
        recipient_name: str | None,
        subject: str,
        message: str | None,
        pdf_filename: str | None,
        actor_user_id: uuid.UUID | None,
        details: dict,
    ) -> DocumentDelivery:
        delivery = DocumentDelivery(
            organization_id=organization_id,
            document_type=document_type,
            document_id=document_id,
            document_number=document_number,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=subject,
            message=message,
            delivery_channel="email",
            delivery_status="queued",
            provider=settings.EMAIL_PROVIDER,
            pdf_filename=pdf_filename,
            sent_at=None,
            sent_by_user_id=actor_user_id,
            details=details,
        )

        return self.deliveries.create(delivery)

    def _record_audit_event(
        self,
        *,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
        delivery: DocumentDelivery,
        email_outbox_id: uuid.UUID,
    ) -> None:
        self.audit_logs.record_event(
            organization_id=organization_id,
            payload=AuditLogCreate(
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action=(
                    f"{delivery.document_type}.delivery_queued"
                ),
                entity_type="document_delivery",
                entity_id=delivery.id,
                summary=(
                    f"{delivery.document_type.title()} "
                    f"{delivery.document_number} email queued "
                    f"for {delivery.recipient_email}."
                ),
                status="success",
                request_method="SYSTEM",
                request_path="/system/document-delivery",
                details={
                    "document_type": delivery.document_type,
                    "document_id": str(delivery.document_id),
                    "document_number": delivery.document_number,
                    "recipient_email": delivery.recipient_email,
                    "delivery_status": delivery.delivery_status,
                    "pdf_filename": delivery.pdf_filename,
                    "email_outbox_id": str(email_outbox_id),
                },
            ),
            commit=False,
        )

    def _build_response(
        self,
        delivery: DocumentDelivery,
    ) -> DocumentDeliveryResponse:
        sent_by = delivery.sent_by

        return DocumentDeliveryResponse(
            id=delivery.id,
            organization_id=delivery.organization_id,
            document_type=delivery.document_type,
            document_id=delivery.document_id,
            document_number=delivery.document_number,
            recipient_email=delivery.recipient_email,
            recipient_name=delivery.recipient_name,
            subject=delivery.subject,
            message=delivery.message,
            delivery_channel=delivery.delivery_channel,
            delivery_status=delivery.delivery_status,
            provider=delivery.provider,
            pdf_filename=delivery.pdf_filename,
            sent_at=delivery.sent_at,
            sent_by_user_id=delivery.sent_by_user_id,
            sent_by_first_name=(
                sent_by.first_name
                if sent_by
                else None
            ),
            sent_by_last_name=(
                sent_by.last_name
                if sent_by
                else None
            ),
            sent_by_email=(
                sent_by.email
                if sent_by
                else None
            ),
            details=delivery.details or {},
            is_active=delivery.is_active,
            created_at=delivery.created_at,
            updated_at=delivery.updated_at,
        )
