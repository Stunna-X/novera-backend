"""
PostgreSQL tenant-isolation tests for notifications.
"""

from __future__ import annotations

import uuid
from typing import Protocol

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.schemas.notification import CreateNotificationSchema
from app.services.notification_service import NotificationService


class TenantIntegrationData(Protocol):
    """
    Minimum shared fixture contract required by this test.
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


def _list_notifications(
    service: NotificationService,
    *,
    organization_id: uuid.UUID,
    recipient_user_id: uuid.UUID,
):
    """
    List notifications without optional filters.
    """

    return service.list_notifications(
        organization_id=organization_id,
        recipient_user_id=recipient_user_id,
        unread_only=False,
        include_archived=True,
        notification_type=None,
        entity_type=None,
        priority=None,
        skip=0,
        limit=1000,
    )


def test_notifications_cannot_cross_organization_boundary(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: TenantIntegrationData,
) -> None:
    """
    Foreign organizations must not read or mutate notifications.
    """

    token = uuid.uuid4().hex

    primary_organization_id = (
        inventory_integration_data.organization_id
    )
    foreign_organization_id = (
        inventory_integration_data.other_organization_id
    )
    recipient_user_id = (
        inventory_integration_data.actor_user_id
    )

    primary_title = (
        f"Primary confidential notification {token[:10]}"
    )
    primary_message = (
        f"Primary confidential notification message {token}"
    )
    primary_secret = (
        f"PRIMARY-NOTIFICATION-SECRET-{token}"
    )
    primary_entity_id = uuid.uuid4()

    foreign_title = (
        f"Foreign notification {token[:10]}"
    )
    foreign_message = (
        f"Foreign notification message {token}"
    )
    foreign_secret = (
        f"FOREIGN-NOTIFICATION-SECRET-{token}"
    )
    foreign_entity_id = uuid.uuid4()

    with integration_session_factory() as db:
        service = NotificationService(db)

        primary_notification = service.create_notification(
            organization_id=primary_organization_id,
            actor_user_id=recipient_user_id,
            payload=CreateNotificationSchema(
                recipient_user_id=recipient_user_id,
                notification_type="tenant_isolation_primary",
                title=primary_title,
                message=primary_message,
                priority="warning",
                entity_type="work_order",
                entity_id=primary_entity_id,
                action_url=(
                    f"/work-orders/{primary_entity_id}"
                ),
                payload={
                    "secret": primary_secret,
                    "source": "primary_organization",
                },
            ),
        )

        foreign_notification = service.create_notification(
            organization_id=foreign_organization_id,
            actor_user_id=recipient_user_id,
            payload=CreateNotificationSchema(
                recipient_user_id=recipient_user_id,
                notification_type="tenant_isolation_foreign",
                title=foreign_title,
                message=foreign_message,
                priority="info",
                entity_type="quote",
                entity_id=foreign_entity_id,
                action_url=(
                    f"/quotes/{foreign_entity_id}"
                ),
                payload={
                    "secret": foreign_secret,
                    "source": "foreign_organization",
                },
            ),
        )

        primary_notification_id = primary_notification.id
        foreign_notification_id = foreign_notification.id

    with integration_session_factory() as db:
        service = NotificationService(db)

        foreign_list = _list_notifications(
            service,
            organization_id=foreign_organization_id,
            recipient_user_id=recipient_user_id,
        )

        foreign_ids = {
            item.id
            for item in foreign_list.items
        }

        assert foreign_notification_id in foreign_ids
        assert primary_notification_id not in foreign_ids

        serialized_foreign_list = repr(
            [
                item.model_dump()
                for item in foreign_list.items
            ]
        )

        assert foreign_secret in serialized_foreign_list
        assert primary_secret not in serialized_foreign_list
        assert primary_message not in serialized_foreign_list
        assert str(primary_entity_id) not in serialized_foreign_list

        foreign_unread = service.get_unread_count(
            organization_id=foreign_organization_id,
            recipient_user_id=recipient_user_id,
        )

        assert foreign_unread.organization_id == (
            foreign_organization_id
        )
        assert foreign_unread.unread_count == 1

        with pytest.raises(
            HTTPException
        ) as foreign_mark_read_error:
            service.mark_as_read(
                organization_id=foreign_organization_id,
                notification_id=primary_notification_id,
                recipient_user_id=recipient_user_id,
            )

        _assert_not_found(
            foreign_mark_read_error
        )

        with pytest.raises(
            HTTPException
        ) as foreign_archive_error:
            service.archive_notification(
                organization_id=foreign_organization_id,
                notification_id=primary_notification_id,
                recipient_user_id=recipient_user_id,
            )

        _assert_not_found(
            foreign_archive_error
        )

        foreign_bulk_update = service.mark_all_as_read(
            organization_id=foreign_organization_id,
            recipient_user_id=recipient_user_id,
        )

        assert foreign_bulk_update.organization_id == (
            foreign_organization_id
        )
        assert foreign_bulk_update.updated_count == 1

        foreign_after_update = _list_notifications(
            service,
            organization_id=foreign_organization_id,
            recipient_user_id=recipient_user_id,
        )

        foreign_record = next(
            item
            for item in foreign_after_update.items
            if item.id == foreign_notification_id
        )

        assert foreign_record.is_read is True
        assert foreign_record.read_at is not None

        primary_list = _list_notifications(
            service,
            organization_id=primary_organization_id,
            recipient_user_id=recipient_user_id,
        )

        primary_ids = {
            item.id
            for item in primary_list.items
        }

        assert primary_notification_id in primary_ids
        assert foreign_notification_id not in primary_ids

        primary_record = next(
            item
            for item in primary_list.items
            if item.id == primary_notification_id
        )

        assert primary_record.organization_id == (
            primary_organization_id
        )
        assert primary_record.recipient_user_id == (
            recipient_user_id
        )
        assert primary_record.title == primary_title
        assert primary_record.message == primary_message
        assert primary_record.priority == "warning"
        assert primary_record.entity_type == "work_order"
        assert primary_record.entity_id == primary_entity_id
        assert primary_record.payload == {
            "secret": primary_secret,
            "source": "primary_organization",
        }
        assert primary_record.is_read is False
        assert primary_record.read_at is None
        assert primary_record.is_archived is False
        assert primary_record.archived_at is None

        primary_unread = service.get_unread_count(
            organization_id=primary_organization_id,
            recipient_user_id=recipient_user_id,
        )

        assert primary_unread.organization_id == (
            primary_organization_id
        )
        assert primary_unread.unread_count == 1

        serialized_primary_list = repr(
            [
                item.model_dump()
                for item in primary_list.items
            ]
        )

        assert primary_secret in serialized_primary_list
        assert foreign_secret not in serialized_primary_list
        assert foreign_message not in serialized_primary_list
        assert str(foreign_entity_id) not in serialized_primary_list
