"""
Email attachment service.

Regenerates immutable document attachments immediately before
provider dispatch instead of storing large PDF blobs in the
email outbox table.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.email.providers.base import EmailAttachment
from app.models.email_outbox import EmailOutbox
from app.services.document_pdf_service import (
    DocumentPDFService,
)


class EmailAttachmentBuildError(RuntimeError):
    """
    Attachment-generation failure with retry metadata.
    """

    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        code: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)

        self.retryable = retryable
        self.code = code
        self.details = details or {}


class EmailAttachmentService:
    """
    Build attachments required by an outbox message.
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db
        self.pdfs = DocumentPDFService(db)

    def build_for_outbox(
        self,
        email: EmailOutbox,
    ) -> tuple[EmailAttachment, ...]:
        """
        Regenerate all attachments for one outbox message.
        """

        if not email.attachment_filename:
            return ()

        delivery = email.document_delivery

        if delivery is None:
            raise EmailAttachmentBuildError(
                (
                    "The outbox message has no associated "
                    "document delivery record."
                ),
                retryable=False,
                code="document_delivery_missing",
                details={
                    "email_outbox_id": str(email.id),
                    "document_delivery_id": str(
                        email.document_delivery_id
                    ),
                },
            )

        try:
            if delivery.document_type == "invoice":
                content, generated_filename = (
                    self.pdfs.build_invoice_pdf(
                        organization_id=(
                            email.organization_id
                        ),
                        invoice_id=delivery.document_id,
                        include_inactive=True,
                    )
                )

            elif delivery.document_type == "quote":
                content, generated_filename = (
                    self.pdfs.build_quote_pdf(
                        organization_id=(
                            email.organization_id
                        ),
                        quote_id=delivery.document_id,
                        include_inactive=True,
                    )
                )

            else:
                raise EmailAttachmentBuildError(
                    (
                        "The delivery document type is not "
                        "supported for email attachments."
                    ),
                    retryable=False,
                    code="document_type_unsupported",
                    details={
                        "document_type": (
                            delivery.document_type
                        ),
                        "document_id": str(
                            delivery.document_id
                        ),
                    },
                )

        except EmailAttachmentBuildError:
            raise

        except HTTPException as exc:
            raise EmailAttachmentBuildError(
                (
                    "The document attachment could not be "
                    "regenerated."
                ),
                retryable=exc.status_code >= 500,
                code="document_pdf_http_error",
                details={
                    "status_code": exc.status_code,
                    "detail": str(exc.detail),
                    "document_type": (
                        delivery.document_type
                    ),
                    "document_id": str(
                        delivery.document_id
                    ),
                },
            ) from exc

        except Exception as exc:
            raise EmailAttachmentBuildError(
                (
                    "An unexpected error occurred while "
                    "regenerating the document attachment."
                ),
                retryable=True,
                code="document_pdf_generation_error",
                details={
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "document_type": (
                        delivery.document_type
                    ),
                    "document_id": str(
                        delivery.document_id
                    ),
                },
            ) from exc

        filename = (
            email.attachment_filename
            or generated_filename
        )

        return (
            EmailAttachment(
                filename=filename,
                content=content,
                content_type="application/pdf",
            ),
        )