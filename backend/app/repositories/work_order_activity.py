"""
Work-order activity repository.

Contains persistence operations for work-order timeline
entries.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func
from sqlalchemy.orm import (
    Session,
    joinedload,
)

from app.models.work_order_activity import WorkOrderActivity
from app.repositories.base import BaseRepository


class WorkOrderActivityRepository(
    BaseRepository[WorkOrderActivity]
):
    """
    Repository for work-order activity operations.
    """

    def __init__(
        self,
        db: Session,
    ):
        super().__init__(
            db,
            WorkOrderActivity,
        )

    def create_activity(
        self,
        activity: WorkOrderActivity,
    ) -> WorkOrderActivity:
        """
        Persist a work-order activity entry.
        """

        return self.create(
            activity
        )

    def list_for_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        activity_type: str | None = None,
    ) -> list[WorkOrderActivity]:
        """
        List timeline entries for a work order.
        """

        query = (
            self.db.query(WorkOrderActivity)
            .options(
                joinedload(
                    WorkOrderActivity.actor
                )
            )
            .filter(
                WorkOrderActivity.organization_id
                == organization_id,
                WorkOrderActivity.work_order_id
                == work_order_id,
            )
        )

        if activity_type:
            query = query.filter(
                WorkOrderActivity.activity_type
                == activity_type
            )

        return (
            query.order_by(
                WorkOrderActivity.created_at.asc()
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        activity_type: str | None = None,
    ) -> int:
        """
        Count timeline entries for a work order.
        """

        query = (
            self.db.query(
                func.count(
                    WorkOrderActivity.id
                )
            )
            .filter(
                WorkOrderActivity.organization_id
                == organization_id,
                WorkOrderActivity.work_order_id
                == work_order_id,
            )
        )

        if activity_type:
            query = query.filter(
                WorkOrderActivity.activity_type
                == activity_type
            )

        return query.scalar() or 0