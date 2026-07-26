"""
PostgreSQL tenant-isolation tests for the document-delivery pipeline.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Protocol

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.models.document_delivery import DocumentDelivery
from app.models.email_outbox import EmailOutbox
from app.schemas.email_outbox import (
    EmailOutboxMarkFailedRequest,
    EmailOutboxMarkSentRequest,
    EmailOutboxRetryRequest,
)
from app.services.document_delivery_service import (
    DocumentDeliveryService,
)
from app.services.email_outbox_service import (
    EmailOutboxService,
)


class TenantIntegrationData(Protocol):
    """
    Minimum shared fixture contract required by these tests.
    """

    organization_id: uuid.UUID
    other_organization_id: uuid.UUID
    actor_user_id: uuid.UUID


def _assert_not_found(
    error: pytest.ExceptionInfo[HTTPException],
) -> None:
    """
    Assert an information-leak-safe not-found response.
    """

    assert error.value.status_code == 404


def _create_delivery(
    db: Session,
    *,
    organization_id: uuid.UUID,
    document_type: str,
    document_id: uuid.UUID,
    document_number: str,
    recipient_email: str,
    recipient_name: str,
    subject: str,
    message: str,
    delivery_status: str,
    details: dict[str, object],
) -> DocumentDelivery:
    """
    Insert one complete document-delivery record.
    """

    delivery = DocumentDelivery(
        id=uuid.uuid4(),
        organization_id=organization_id,
        document_type=document_type,
        document_id=document_id,
        document_number=document_number,
        recipient_email=recipient_email,
        recipient_name=recipient_name,
        subject=subject,
        message=message,
        delivery_channel="email",
        delivery_status=delivery_status,
        provider="development",
        pdf_filename=f"{document_number}.pdf",
        sent_at=None,
        sent_by_user_id=None,
        details=details,
        is_active=True,
    )

    db.add(delivery)
    db.flush()

    return delivery


def _create_outbox_email(
    db: Session,
    *,
    delivery: DocumentDelivery,
    actor_user_id: uuid.UUID | None,
    status: str,
    body_text: str,
    details: dict[str, object],
    attempts: int = 0,
    failure_reason: str | None = None,
) -> EmailOutbox:
    """
    Insert one complete outbox record linked to a delivery.
    """

    now = datetime.now(UTC)

    email = EmailOutbox(
        id=uuid.uuid4(),
        organization_id=delivery.organization_id,
        document_delivery_id=delivery.id,
        queued_by_user_id=actor_user_id,
        provider="development",
        status=status,
        from_email="no-reply@novera.local",
        from_name="Novera",
        reply_to_email=None,
        to_email=delivery.recipient_email,
        to_name=delivery.recipient_name,
        subject=delivery.subject,
        body_text=body_text,
        body_html=f"<p>{body_text}</p>",
        attachment_filename=delivery.pdf_filename,
        attempts=attempts,
        max_attempts=3,
        next_attempt_at=now,
        queued_at=now,
        sent_at=None,
        failed_at=(
            now
            if status == "failed"
            else None
        ),
        last_error=failure_reason,
        provider_message_id=None,
        details=details,
        is_active=True,
    )

    db.add(email)
    db.flush()

    return email


def test_document_deliveries_cannot_cross_organization_boundary(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: TenantIntegrationData,
) -> None:
    """
    Foreign organizations must not read document deliveries.
    """

    token = uuid.uuid4().hex

    primary_organization_id = (
        inventory_integration_data.organization_id
    )
    foreign_organization_id = (
        inventory_integration_data.other_organization_id
    )

    primary_document_id = uuid.uuid4()
    foreign_document_id = uuid.uuid4()

    primary_recipient = (
        f"primary-delivery-{token}@example.test"
    )
    foreign_recipient = (
        f"foreign-delivery-{token}@example.test"
    )

    primary_message = (
        f"Confidential primary invoice message {token}"
    )
    primary_secret = (
        f"PRIMARY-DELIVERY-SECRET-{token}"
    )

    primary_details = {
        "customer_reference": primary_secret,
        "internal_note": (
            f"Internal primary delivery note {token}"
        ),
    }

    foreign_details = {
        "customer_reference": (
            f"FOREIGN-DELIVERY-SECRET-{token}"
        ),
    }

    with integration_session_factory() as db:
        primary_delivery = _create_delivery(
            db,
            organization_id=primary_organization_id,
            document_type="invoice",
            document_id=primary_document_id,
            document_number=f"INV-PRIMARY-{token[:10]}",
            recipient_email=primary_recipient,
            recipient_name="Primary Customer",
            subject=f"Primary invoice {token[:10]}",
            message=primary_message,
            delivery_status="queued",
            details=primary_details,
        )

        foreign_delivery = _create_delivery(
            db,
            organization_id=foreign_organization_id,
            document_type="quote",
            document_id=foreign_document_id,
            document_number=f"QUO-FOREIGN-{token[:10]}",
            recipient_email=foreign_recipient,
            recipient_name="Foreign Customer",
            subject=f"Foreign quote {token[:10]}",
            message=f"Foreign delivery message {token}",
            delivery_status="recorded",
            details=foreign_details,
        )

        primary_delivery_id = primary_delivery.id
        foreign_delivery_id = foreign_delivery.id

        db.commit()

    with integration_session_factory() as db:
        service = DocumentDeliveryService(db)

        with pytest.raises(
            HTTPException
        ) as foreign_read_error:
            service.get_delivery(
                organization_id=foreign_organization_id,
                delivery_id=primary_delivery_id,
            )

        _assert_not_found(
            foreign_read_error
        )

        foreign_deliveries = service.list_deliveries(
            organization_id=foreign_organization_id,
            skip=0,
            limit=1000,
        )

        foreign_ids = {
            item.id
            for item in foreign_deliveries.items
        }

        assert foreign_delivery_id in foreign_ids
        assert primary_delivery_id not in foreign_ids

        filtered_by_document = (
            service.list_deliveries(
                organization_id=foreign_organization_id,
                skip=0,
                limit=1000,
                document_id=primary_document_id,
            )
        )

        assert filtered_by_document.total == 0
        assert filtered_by_document.items == []

        filtered_by_recipient = (
            service.list_deliveries(
                organization_id=foreign_organization_id,
                skip=0,
                limit=1000,
                recipient_email=primary_recipient,
            )
        )

        assert filtered_by_recipient.total == 0
        assert filtered_by_recipient.items == []

        unchanged_primary = service.get_delivery(
            organization_id=primary_organization_id,
            delivery_id=primary_delivery_id,
        )

        assert unchanged_primary.id == primary_delivery_id
        assert (
            unchanged_primary.organization_id
            == primary_organization_id
        )
        assert unchanged_primary.document_type == "invoice"
        assert (
            unchanged_primary.document_id
            == primary_document_id
        )
        assert (
            unchanged_primary.recipient_email
            == primary_recipient
        )
        assert unchanged_primary.message == primary_message
        assert unchanged_primary.details == primary_details
        assert unchanged_primary.delivery_status == "queued"
        assert unchanged_primary.provider == "development"
        assert unchanged_primary.sent_at is None

        primary_deliveries = service.list_deliveries(
            organization_id=primary_organization_id,
            skip=0,
            limit=1000,
        )

        primary_ids = {
            item.id
            for item in primary_deliveries.items
        }

        assert primary_delivery_id in primary_ids
        assert foreign_delivery_id not in primary_ids

        primary_serialized = repr(
            unchanged_primary.model_dump()
        )

        assert primary_secret in primary_serialized
        assert foreign_recipient not in primary_serialized
        assert str(foreign_document_id) not in primary_serialized


def test_email_outbox_cannot_cross_organization_boundary(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: TenantIntegrationData,
) -> None:
    """
    Foreign organizations must not read or mutate outbox emails.
    """

    token = uuid.uuid4().hex

    primary_organization_id = (
        inventory_integration_data.organization_id
    )
    foreign_organization_id = (
        inventory_integration_data.other_organization_id
    )
    actor_user_id = (
        inventory_integration_data.actor_user_id
    )

    queued_recipient = (
        f"queued-primary-{token}@example.test"
    )
    failed_recipient = (
        f"failed-primary-{token}@example.test"
    )
    foreign_recipient = (
        f"foreign-outbox-{token}@example.test"
    )

    queued_body = (
        f"Confidential queued email body {token}"
    )
    failed_body = (
        f"Confidential failed email body {token}"
    )

    queued_secret = (
        f"PRIMARY-QUEUED-SECRET-{token}"
    )
    failed_secret = (
        f"PRIMARY-FAILED-SECRET-{token}"
    )

    failure_reason = (
        f"Original provider failure {token}"
    )

    with integration_session_factory() as db:
        queued_delivery = _create_delivery(
            db,
            organization_id=primary_organization_id,
            document_type="invoice",
            document_id=uuid.uuid4(),
            document_number=f"INV-QUEUED-{token[:10]}",
            recipient_email=queued_recipient,
            recipient_name="Queued Primary Customer",
            subject=f"Queued primary invoice {token[:10]}",
            message=f"Queued delivery message {token}",
            delivery_status="queued",
            details={
                "pipeline": "queued",
                "secret": queued_secret,
            },
        )

        failed_delivery = _create_delivery(
            db,
            organization_id=primary_organization_id,
            document_type="quote",
            document_id=uuid.uuid4(),
            document_number=f"QUO-FAILED-{token[:10]}",
            recipient_email=failed_recipient,
            recipient_name="Failed Primary Customer",
            subject=f"Failed primary quote {token[:10]}",
            message=f"Failed delivery message {token}",
            delivery_status="failed",
            details={
                "pipeline": "failed",
                "secret": failed_secret,
            },
        )

        foreign_delivery = _create_delivery(
            db,
            organization_id=foreign_organization_id,
            document_type="invoice",
            document_id=uuid.uuid4(),
            document_number=f"INV-FOREIGN-{token[:10]}",
            recipient_email=foreign_recipient,
            recipient_name="Foreign Outbox Customer",
            subject=f"Foreign invoice {token[:10]}",
            message=f"Foreign delivery message {token}",
            delivery_status="queued",
            details={
                "pipeline": "foreign",
            },
        )

        queued_email = _create_outbox_email(
            db,
            delivery=queued_delivery,
            actor_user_id=actor_user_id,
            status="queued",
            body_text=queued_body,
            attempts=0,
            failure_reason=None,
            details={
                "secret": queued_secret,
                "pipeline_state": "original_queued",
            },
        )

        failed_email = _create_outbox_email(
            db,
            delivery=failed_delivery,
            actor_user_id=actor_user_id,
            status="failed",
            body_text=failed_body,
            attempts=1,
            failure_reason=failure_reason,
            details={
                "secret": failed_secret,
                "pipeline_state": "original_failed",
                "retryable": True,
            },
        )

        foreign_email = _create_outbox_email(
            db,
            delivery=foreign_delivery,
            actor_user_id=None,
            status="queued",
            body_text=f"Foreign email body {token}",
            attempts=0,
            failure_reason=None,
            details={
                "pipeline_state": "foreign_queued",
            },
        )

        queued_delivery_id = queued_delivery.id
        failed_delivery_id = failed_delivery.id

        queued_email_id = queued_email.id
        failed_email_id = failed_email.id
        foreign_email_id = foreign_email.id

        db.commit()

    with integration_session_factory() as db:
        service = EmailOutboxService(db)

        with pytest.raises(
            HTTPException
        ) as foreign_read_error:
            service.get_outbox_email(
                organization_id=foreign_organization_id,
                email_outbox_id=queued_email_id,
            )

        _assert_not_found(
            foreign_read_error
        )

        foreign_outbox = service.list_outbox(
            organization_id=foreign_organization_id,
            skip=0,
            limit=1000,
        )

        foreign_ids = {
            item.id
            for item in foreign_outbox.items
        }

        assert foreign_email_id in foreign_ids
        assert queued_email_id not in foreign_ids
        assert failed_email_id not in foreign_ids

        filtered_by_recipient = service.list_outbox(
            organization_id=foreign_organization_id,
            skip=0,
            limit=1000,
            recipient_email=queued_recipient,
        )

        assert filtered_by_recipient.total == 0
        assert filtered_by_recipient.items == []

        filtered_by_delivery = service.list_outbox(
            organization_id=foreign_organization_id,
            skip=0,
            limit=1000,
            document_delivery_id=queued_delivery_id,
        )

        assert filtered_by_delivery.total == 0
        assert filtered_by_delivery.items == []

        with pytest.raises(
            HTTPException
        ) as foreign_mark_sent_error:
            service.mark_sent(
                organization_id=foreign_organization_id,
                email_outbox_id=queued_email_id,
                payload=EmailOutboxMarkSentRequest(
                    provider_message_id=(
                        f"foreign-message-{token}"
                    ),
                    note=(
                        "Foreign organization attempted "
                        "to mark this email as sent."
                    ),
                ),
                actor_user_id=actor_user_id,
                actor_membership_id=None,
            )

        _assert_not_found(
            foreign_mark_sent_error
        )

        with pytest.raises(
            HTTPException
        ) as foreign_mark_failed_error:
            service.mark_failed(
                organization_id=foreign_organization_id,
                email_outbox_id=queued_email_id,
                payload=EmailOutboxMarkFailedRequest(
                    reason=(
                        "Foreign organization attempted "
                        "to fail this email."
                    ),
                    retryable=False,
                ),
                actor_user_id=actor_user_id,
                actor_membership_id=None,
            )

        _assert_not_found(
            foreign_mark_failed_error
        )

        with pytest.raises(
            HTTPException
        ) as foreign_retry_error:
            service.retry_email(
                organization_id=foreign_organization_id,
                email_outbox_id=failed_email_id,
                payload=EmailOutboxRetryRequest(
                    note=(
                        "Foreign organization attempted "
                        "to retry this email."
                    ),
                ),
                actor_user_id=actor_user_id,
                actor_membership_id=None,
            )

        _assert_not_found(
            foreign_retry_error
        )

        unchanged_queued = service.get_outbox_email(
            organization_id=primary_organization_id,
            email_outbox_id=queued_email_id,
        )

        assert unchanged_queued.status == "queued"
        assert unchanged_queued.attempts == 0
        assert unchanged_queued.sent_at is None
        assert unchanged_queued.failed_at is None
        assert unchanged_queued.last_error is None
        assert unchanged_queued.provider_message_id is None
        assert unchanged_queued.to_email == queued_recipient
        assert unchanged_queued.body_text == queued_body
        assert (
            unchanged_queued.details["secret"]
            == queued_secret
        )
        assert (
            unchanged_queued.details["pipeline_state"]
            == "original_queued"
        )

        unchanged_failed = service.get_outbox_email(
            organization_id=primary_organization_id,
            email_outbox_id=failed_email_id,
        )

        assert unchanged_failed.status == "failed"
        assert unchanged_failed.attempts == 1
        assert unchanged_failed.sent_at is None
        assert unchanged_failed.failed_at is not None
        assert unchanged_failed.last_error == failure_reason
        assert unchanged_failed.provider_message_id is None
        assert unchanged_failed.to_email == failed_recipient
        assert unchanged_failed.body_text == failed_body
        assert (
            unchanged_failed.details["secret"]
            == failed_secret
        )
        assert (
            unchanged_failed.details["pipeline_state"]
            == "original_failed"
        )

        primary_outbox = service.list_outbox(
            organization_id=primary_organization_id,
            skip=0,
            limit=1000,
        )

        primary_ids = {
            item.id
            for item in primary_outbox.items
        }

        assert queued_email_id in primary_ids
        assert failed_email_id in primary_ids
        assert foreign_email_id not in primary_ids

        delivery_service = DocumentDeliveryService(db)

        unchanged_queued_delivery = (
            delivery_service.get_delivery(
                organization_id=primary_organization_id,
                delivery_id=queued_delivery_id,
            )
        )

        unchanged_failed_delivery = (
            delivery_service.get_delivery(
                organization_id=primary_organization_id,
                delivery_id=failed_delivery_id,
            )
        )

        assert (
            unchanged_queued_delivery.delivery_status
            == "queued"
        )
        assert unchanged_queued_delivery.sent_at is None

        assert (
            unchanged_failed_delivery.delivery_status
            == "failed"
        )
        assert unchanged_failed_delivery.sent_at is None

        serialized_primary_outbox = repr(
            [
                item.model_dump()
                for item in primary_outbox.items
            ]
        )

        assert queued_secret in serialized_primary_outbox
        assert failed_secret in serialized_primary_outbox
        assert foreign_recipient not in serialized_primary_outbox
