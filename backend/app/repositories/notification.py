"""
Notification repository.

Provides organization-scoped notification persistence helpers.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.notification import Notification


class NotificationRepository:
    """
    Repository for Notification records.
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def get_for_recipient(
        self,
        *,
        organization_id: uuid.UUID,
        notification_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
    ) -> Notification | None:
        """
        Return one notification for a recipient.
        """

        return (
            self.db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.organization_id == organization_id,
                Notification.recipient_user_id == recipient_user_id,
            )
            .first()
        )

    def list_for_recipient(
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
    ) -> tuple[list[Notification], int]:
        """
        Return paginated notifications and total count.
        """

        query = self.db.query(Notification).filter(
            Notification.organization_id == organization_id,
            Notification.recipient_user_id == recipient_user_id,
        )

        if unread_only:
            query = query.filter(
                Notification.is_read.is_(False),
            )

        if not include_archived:
            query = query.filter(
                Notification.is_archived.is_(False),
            )

        if notification_type is not None:
            query = query.filter(
                Notification.notification_type == notification_type,
            )

        if entity_type is not None:
            query = query.filter(
                Notification.entity_type == entity_type,
            )

        if priority is not None:
            query = query.filter(
                Notification.priority == priority,
            )

        total = query.count()

        items = (
            query.order_by(
                Notification.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

        return items, total

    def unread_count(
        self,
        *,
        organization_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
    ) -> int:
        """
        Return unread count for a recipient.
        """

        value = (
            self.db.query(Notification)
            .filter(
                Notification.organization_id == organization_id,
                Notification.recipient_user_id == recipient_user_id,
                Notification.is_read.is_(False),
                Notification.is_archived.is_(False),
            )
            .count()
        )

        return int(value or 0)

    def create(
        self,
        notification: Notification,
    ) -> Notification:
        """
        Persist a new notification.
        """

        self.db.add(notification)
        self.db.flush()
        self.db.refresh(notification)

        return notification

    def mark_as_read(
        self,
        *,
        notification: Notification,
        read_at: datetime,
    ) -> Notification:
        """
        Mark a notification as read.
        """

        notification.is_read = True
        notification.read_at = notification.read_at or read_at

        self.db.flush()
        self.db.refresh(notification)

        return notification

    def mark_all_as_read(
        self,
        *,
        organization_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        read_at: datetime,
    ) -> int:
        """
        Mark all unread notifications as read for a recipient.
        """

        notifications = (
            self.db.query(Notification)
            .filter(
                Notification.organization_id == organization_id,
                Notification.recipient_user_id == recipient_user_id,
                Notification.is_read.is_(False),
                Notification.is_archived.is_(False),
            )
            .all()
        )

        for notification in notifications:
            notification.is_read = True
            notification.read_at = read_at

        self.db.flush()

        return len(notifications)

    def archive(
        self,
        *,
        notification: Notification,
        archived_at: datetime,
    ) -> Notification:
        """
        Archive a notification.
        """

        notification.is_archived = True
        notification.archived_at = notification.archived_at or archived_at

        self.db.flush()
        self.db.refresh(notification)

        return notification
