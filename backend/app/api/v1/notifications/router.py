"""
Notification routes.

Provides organization-scoped notification inbox endpoints.
"""

from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from sqlalchemy.orm import Session

from app.api.deps import (
    OrganizationContext,
    require_permission,
)
from app.database.session import get_db
from app.schemas.notification import (
    CreateNotificationSchema,
    NotificationBulkUpdateResponse,
    NotificationListResponse,
    NotificationPriority,
    NotificationResponse,
    NotificationUnreadCountResponse,
)
from app.services.notification_service import NotificationService


router = APIRouter(
    prefix="/organizations/{organization_id}/notifications",
    tags=["Notifications"],
)


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="List notifications",
)
def list_notifications(
    unread_only: bool = Query(
        default=False,
    ),
    include_archived: bool = Query(
        default=False,
    ),
    notification_type: str | None = Query(
        default=None,
        max_length=80,
    ),
    entity_type: str | None = Query(
        default=None,
        max_length=80,
    ),
    priority: NotificationPriority | None = Query(
        default=None,
    ),
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    context: OrganizationContext = Depends(
        require_permission("work_orders.read")
    ),
    db: Session = Depends(get_db),
) -> NotificationListResponse:
    """
    Return notifications for the current user.
    """

    service = NotificationService(db)

    return service.list_notifications(
        organization_id=context.organization.id,
        recipient_user_id=_current_user_id(context),
        unread_only=unread_only,
        include_archived=include_archived,
        notification_type=notification_type,
        entity_type=entity_type,
        priority=priority,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/unread-count",
    response_model=NotificationUnreadCountResponse,
    summary="Get unread notification count",
)
def get_unread_notification_count(
    context: OrganizationContext = Depends(
        require_permission("work_orders.read")
    ),
    db: Session = Depends(get_db),
) -> NotificationUnreadCountResponse:
    """
    Return unread notification count for the current user.
    """

    service = NotificationService(db)

    return service.get_unread_count(
        organization_id=context.organization.id,
        recipient_user_id=_current_user_id(context),
    )


@router.post(
    "",
    response_model=NotificationResponse,
    status_code=201,
    summary="Create notification",
)
def create_notification(
    payload: CreateNotificationSchema,
    context: OrganizationContext = Depends(
        require_permission("work_orders.read")
    ),
    db: Session = Depends(get_db),
) -> NotificationResponse:
    """
    Create a notification.

    This is backend-ready for system events and also useful for
    development/testing until workflow events are wired in.
    """

    service = NotificationService(db)

    return service.create_notification(
        organization_id=context.organization.id,
        actor_user_id=_current_user_id(context),
        payload=payload,
    )


@router.patch(
    "/read-all",
    response_model=NotificationBulkUpdateResponse,
    summary="Mark all notifications as read",
)
def mark_all_notifications_as_read(
    context: OrganizationContext = Depends(
        require_permission("work_orders.read")
    ),
    db: Session = Depends(get_db),
) -> NotificationBulkUpdateResponse:
    """
    Mark all unread notifications as read for the current user.
    """

    service = NotificationService(db)

    return service.mark_all_as_read(
        organization_id=context.organization.id,
        recipient_user_id=_current_user_id(context),
    )


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark notification as read",
)
def mark_notification_as_read(
    notification_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("work_orders.read")
    ),
    db: Session = Depends(get_db),
) -> NotificationResponse:
    """
    Mark one notification as read.
    """

    service = NotificationService(db)

    return service.mark_as_read(
        organization_id=context.organization.id,
        notification_id=notification_id,
        recipient_user_id=_current_user_id(context),
    )


@router.patch(
    "/{notification_id}/archive",
    response_model=NotificationResponse,
    summary="Archive notification",
)
def archive_notification(
    notification_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("work_orders.read")
    ),
    db: Session = Depends(get_db),
) -> NotificationResponse:
    """
    Archive one notification.
    """

    service = NotificationService(db)

    return service.archive_notification(
        organization_id=context.organization.id,
        notification_id=notification_id,
        recipient_user_id=_current_user_id(context),
    )


def _current_user_id(
    context: OrganizationContext,
) -> uuid.UUID:
    """
    Return the current authenticated user's ID from organization context.
    """

    membership = getattr(
        context,
        "membership",
        None,
    )

    if membership is not None:
        user_id = getattr(
            membership,
            "user_id",
            None,
        )

        if user_id is not None:
            return user_id

    user = getattr(
        context,
        "user",
        None,
    )

    if user is not None:
        user_id = getattr(
            user,
            "id",
            None,
        )

        if user_id is not None:
            return user_id

    current_user = getattr(
        context,
        "current_user",
        None,
    )

    if current_user is not None:
        user_id = getattr(
            current_user,
            "id",
            None,
        )

        if user_id is not None:
            return user_id

    user_id = getattr(
        context,
        "user_id",
        None,
    )

    if user_id is not None:
        return user_id

    raise RuntimeError(
        "Unable to resolve current user id from organization context."
    )
