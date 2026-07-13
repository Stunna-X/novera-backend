"""
Work-order activity service.

Provides read access to work-order timeline entries.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.work_order_activity import WorkOrderActivity
from app.repositories.work_order import WorkOrderRepository
from app.repositories.work_order_activity import (
    WorkOrderActivityRepository,
)
from app.schemas.work_order_activity import (
    WorkOrderActivityListResponse,
    WorkOrderActivityResponse,
)


class WorkOrderActivityService:
    """
    Handles work-order timeline queries.
    """

    def __init__(
        self,
        db: Session,
    ):
        self.work_orders = WorkOrderRepository(db)
        self.activities = WorkOrderActivityRepository(db)

    @staticmethod
    def _build_response(
        activity: WorkOrderActivity,
    ) -> WorkOrderActivityResponse:
        """
        Convert an activity model into an API response.
        """

        actor = activity.actor

        return WorkOrderActivityResponse(
            id=activity.id,
            organization_id=activity.organization_id,
            work_order_id=activity.work_order_id,
            actor_user_id=activity.actor_user_id,
            actor_first_name=(
                actor.first_name
                if actor is not None
                else None
            ),
            actor_last_name=(
                actor.last_name
                if actor is not None
                else None
            ),
            actor_email=(
                actor.email
                if actor is not None
                else None
            ),
            activity_type=activity.activity_type,
            summary=activity.summary,
            from_status=activity.from_status,
            to_status=activity.to_status,
            note=activity.note,
            details=activity.details or {},
            created_at=activity.created_at,
        )

    def list_activities(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        activity_type: str | None = None,
        include_inactive_work_order: bool = False,
    ) -> WorkOrderActivityListResponse:
        """
        Return the activity timeline for one work order.
        """

        work_order = (
            self.work_orders.get_for_organization(
                organization_id=organization_id,
                work_order_id=work_order_id,
                include_inactive=(
                    include_inactive_work_order
                ),
            )
        )

        if work_order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work order not found.",
            )

        activities = (
            self.activities.list_for_work_order(
                organization_id=organization_id,
                work_order_id=work_order_id,
                skip=skip,
                limit=limit,
                activity_type=activity_type,
            )
        )

        total = (
            self.activities.count_for_work_order(
                organization_id=organization_id,
                work_order_id=work_order_id,
                activity_type=activity_type,
            )
        )

        return WorkOrderActivityListResponse(
            items=[
                self._build_response(activity)
                for activity in activities
            ],
            total=total,
            skip=skip,
            limit=limit,
        )