"""
Notification service.

Coordinates notification creation, listing, read state,
and archiving.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.repositories.notification import NotificationRepository
from app.services.auto_audit_service import AutoAuditService
from app.schemas.notification import (
    CreateNotificationSchema,
    NotificationBulkUpdateResponse,
    NotificationListResponse,
    NotificationResponse,
    NotificationUnreadCountResponse,
)


class NotificationService:
    """
    Application service for user notifications.
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db
        self.repository = NotificationRepository(db)
        self.auto_audit = AutoAuditService(db)

    def create_notification(
        self,
        *,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        payload: CreateNotificationSchema,
    ) -> NotificationResponse:
        """
        Create a notification.

        If no recipient is provided, the actor receives it.
        """

        recipient_user_id = payload.recipient_user_id or actor_user_id

        if recipient_user_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="recipient_user_id is required.",
            )

        notification = Notification(
            organization_id=organization_id,
            recipient_user_id=recipient_user_id,
            actor_user_id=actor_user_id,
            notification_type=payload.notification_type,
            title=payload.title,
            message=payload.message,
            priority=payload.priority,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            action_url=payload.action_url,
            payload=payload.payload,
        )

        self.repository.create(notification)
        self.auto_audit.notification_created(
            organization_id=organization_id,
            notification=notification,
            actor_user_id=actor_user_id,
        )

        self.db.commit()
        self.db.refresh(notification)

        return self._to_response(notification)

    def list_notifications(
        self,
        *,
        organization_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        unread_only: bool,
        include_archived: bool,
        notification_type: str | None,
        entity_type: str | None,
        priority: str | None,
        skip: int,
        limit: int,
    ) -> NotificationListResponse:
        """
        Return notifications for one recipient.
        """

        items, total = self.repository.list_for_recipient(
            organization_id=organization_id,
            recipient_user_id=recipient_user_id,
            unread_only=unread_only,
            include_archived=include_archived,
            notification_type=notification_type,
            entity_type=entity_type,
            priority=priority,
            skip=skip,
            limit=limit,
        )

        unread_count = self.repository.unread_count(
            organization_id=organization_id,
            recipient_user_id=recipient_user_id,
        )

        return NotificationListResponse(
            items=[
                self._to_response(notification)
                for notification in items
            ],
            total=total,
            unread_count=unread_count,
            skip=skip,
            limit=limit,
        )

    def get_unread_count(
        self,
        *,
        organization_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
    ) -> NotificationUnreadCountResponse:
        """
        Return unread notification count.
        """

        unread_count = self.repository.unread_count(
            organization_id=organization_id,
            recipient_user_id=recipient_user_id,
        )

        return NotificationUnreadCountResponse(
            organization_id=organization_id,
            unread_count=unread_count,
        )

    def mark_as_read(
        self,
        *,
        organization_id: uuid.UUID,
        notification_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
    ) -> NotificationResponse:
        """
        Mark one notification as read.
        """

        notification = self._get_owned_notification(
            organization_id=organization_id,
            notification_id=notification_id,
            recipient_user_id=recipient_user_id,
        )

        notification = self.repository.mark_as_read(
            notification=notification,
            read_at=self._now(),
        )

        self.db.commit()
        self.db.refresh(notification)

        return self._to_response(notification)

    def mark_all_as_read(
        self,
        *,
        organization_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
    ) -> NotificationBulkUpdateResponse:
        """
        Mark all unread notifications as read.
        """

        updated_count = self.repository.mark_all_as_read(
            organization_id=organization_id,
            recipient_user_id=recipient_user_id,
            read_at=self._now(),
        )

        self.db.commit()

        return NotificationBulkUpdateResponse(
            organization_id=organization_id,
            updated_count=updated_count,
        )

    def archive_notification(
        self,
        *,
        organization_id: uuid.UUID,
        notification_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
    ) -> NotificationResponse:
        """
        Archive one notification.
        """

        notification = self._get_owned_notification(
            organization_id=organization_id,
            notification_id=notification_id,
            recipient_user_id=recipient_user_id,
        )

        notification = self.repository.archive(
            notification=notification,
            archived_at=self._now(),
        )

        self.db.commit()
        self.db.refresh(notification)

        return self._to_response(notification)

    def _get_owned_notification(
        self,
        *,
        organization_id: uuid.UUID,
        notification_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
    ) -> Notification:
        notification = self.repository.get_for_recipient(
            organization_id=organization_id,
            notification_id=notification_id,
            recipient_user_id=recipient_user_id,
        )

        if notification is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found.",
            )

        return notification

    def _to_response(
        self,
        notification: Notification,
    ) -> NotificationResponse:
        return NotificationResponse(
            id=notification.id,
            organization_id=notification.organization_id,
            recipient_user_id=notification.recipient_user_id,
            actor_user_id=notification.actor_user_id,
            notification_type=notification.notification_type,
            title=notification.title,
            message=notification.message,
            priority=notification.priority,
            entity_type=notification.entity_type,
            entity_id=notification.entity_id,
            action_url=notification.action_url,
            payload=notification.payload,
            is_read=notification.is_read,
            read_at=notification.read_at,
            is_archived=notification.is_archived,
            archived_at=notification.archived_at,
            created_at=notification.created_at,
            updated_at=notification.updated_at,
        )

    def _now(
        self,
    ) -> datetime:
        return datetime.now(UTC)
