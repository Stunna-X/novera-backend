"""
Work-order checklist service.

Contains checklist validation, progress calculation,
status transitions, ordering, soft deletion, and activity
timeline recording for work-order checklist items.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.enums.work_order_checklist import (
    WorkOrderChecklistStatus,
)
from app.models.work_order import WorkOrder
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_checklist import (
    WorkOrderChecklistItem,
)
from app.repositories.work_order import WorkOrderRepository
from app.repositories.work_order_activity import (
    WorkOrderActivityRepository,
)
from app.repositories.work_order_checklist import (
    WorkOrderChecklistRepository,
)
from app.schemas.work_order_checklist import (
    WorkOrderChecklistItemCreate,
    WorkOrderChecklistItemResponse,
    WorkOrderChecklistItemUpdate,
    WorkOrderChecklistListResponse,
    WorkOrderChecklistProgressResponse,
    WorkOrderChecklistReorderRequest,
    WorkOrderChecklistStatusUpdate,
)


TERMINAL_WORK_ORDER_STATUSES = {
    "completed",
    "cancelled",
}


class WorkOrderChecklistService:
    """
    Handles work-order checklist business logic.
    """

    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.work_orders = WorkOrderRepository(db)
        self.checklist = WorkOrderChecklistRepository(db)
        self.activities = WorkOrderActivityRepository(db)

    @staticmethod
    def _build_response(
        item: WorkOrderChecklistItem,
    ) -> WorkOrderChecklistItemResponse:
        """
        Convert a checklist model into an API response.
        """

        return WorkOrderChecklistItemResponse(
            id=item.id,
            work_order_id=item.work_order_id,
            title=item.title,
            description=item.description,
            status=item.status,
            is_required=item.is_required,
            position=item.position,
            completion_note=item.completion_note,
            completed_by_user_id=(
                item.completed_by_user_id
            ),
            completed_at=item.completed_at,
            skipped_by_user_id=(
                item.skipped_by_user_id
            ),
            skipped_at=item.skipped_at,
            is_active=item.is_active,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def _record_activity(
        self,
        *,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        activity_type: str,
        summary: str,
        note: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> WorkOrderActivity:
        """
        Record an immutable checklist activity.
        """

        activity = WorkOrderActivity(
            organization_id=organization_id,
            work_order_id=work_order_id,
            actor_user_id=actor_user_id,
            activity_type=activity_type,
            summary=summary,
            note=note,
            details=details or {},
        )

        return self.activities.create_activity(
            activity
        )

    def _get_work_order_or_404(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrder:
        """
        Retrieve an organization work order or raise 404.
        """

        work_order = (
            self.work_orders.get_for_organization(
                organization_id=organization_id,
                work_order_id=work_order_id,
                include_inactive=include_inactive,
            )
        )

        if work_order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work order not found.",
            )

        return work_order

    def _get_item_or_404(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrderChecklistItem:
        """
        Retrieve an organization-scoped checklist item.
        """

        item = self.checklist.get_for_work_order(
            organization_id=organization_id,
            work_order_id=work_order_id,
            item_id=item_id,
            include_inactive=include_inactive,
        )

        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Checklist item not found.",
            )

        return item

    @staticmethod
    def _ensure_work_order_mutable(
        work_order: WorkOrder,
    ) -> None:
        """
        Reject checklist mutations on terminal work orders.
        """

        if work_order.status in TERMINAL_WORK_ORDER_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Checklist items cannot be changed "
                    "after the work order is completed "
                    "or cancelled."
                ),
            )

    def create_item(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        payload: WorkOrderChecklistItemCreate,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderChecklistItemResponse:
        """
        Create a checklist item.
        """

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        self._ensure_work_order_mutable(
            work_order
        )

        position = payload.position

        if position is None:
            position = self.checklist.get_next_position(
                work_order_id
            )

        elif self.checklist.position_exists(
            work_order_id=work_order_id,
            position=position,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another checklist item already "
                    "occupies this position."
                ),
            )

        item = WorkOrderChecklistItem(
            work_order_id=work_order_id,
            title=payload.title,
            description=payload.description,
            status=(
                WorkOrderChecklistStatus.PENDING.value
            ),
            is_required=payload.is_required,
            position=position,
        )

        try:
            created = self.checklist.create_item(
                item
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                activity_type=(
                    "checklist_item_created"
                ),
                summary=(
                    f"Checklist item "
                    f"'{created.title}' created."
                ),
                details={
                    "checklist_item_id": str(
                        created.id
                    ),
                    "title": created.title,
                    "is_required": (
                        created.is_required
                    ),
                    "position": created.position,
                },
            )

            return self._build_response(
                created
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The checklist item conflicts "
                    "with an existing record."
                ),
            ) from exc

    def list_items(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        include_inactive: bool = False,
    ) -> WorkOrderChecklistListResponse:
        """
        List checklist items in execution order.
        """

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            include_inactive=include_inactive,
        )

        items = self.checklist.list_for_work_order(
            organization_id=organization_id,
            work_order_id=work_order_id,
            skip=skip,
            limit=limit,
            include_inactive=include_inactive,
        )

        total = self.checklist.count_for_work_order(
            organization_id=organization_id,
            work_order_id=work_order_id,
            include_inactive=include_inactive,
        )

        return WorkOrderChecklistListResponse(
            items=[
                self._build_response(item)
                for item in items
            ],
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_item(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrderChecklistItemResponse:
        """
        Return one checklist item.
        """

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            include_inactive=include_inactive,
        )

        item = self._get_item_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            item_id=item_id,
            include_inactive=include_inactive,
        )

        return self._build_response(
            item
        )

    def update_item(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: WorkOrderChecklistItemUpdate,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderChecklistItemResponse:
        """
        Update checklist-item details.
        """

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        self._ensure_work_order_mutable(
            work_order
        )

        item = self._get_item_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            item_id=item_id,
        )

        update_data = payload.model_dump(
            exclude_unset=True
        )

        if not update_data:
            return self._build_response(
                item
            )

        if (
            "title" in update_data
            and update_data["title"] is None
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=(
                    "Checklist-item title "
                    "cannot be null."
                ),
            )

        changed_fields = sorted(
            update_data.keys()
        )

        for field_name, field_value in update_data.items():
            setattr(
                item,
                field_name,
                field_value,
            )

        try:
            updated = self.checklist.update_item(
                item
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                activity_type=(
                    "checklist_item_updated"
                ),
                summary=(
                    f"Checklist item "
                    f"'{updated.title}' updated."
                ),
                details={
                    "checklist_item_id": str(
                        updated.id
                    ),
                    "changed_fields": changed_fields,
                },
            )

            return self._build_response(
                updated
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The checklist update conflicts "
                    "with an existing record."
                ),
            ) from exc

    def change_item_status(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: WorkOrderChecklistStatusUpdate,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderChecklistItemResponse:
        """
        Complete, skip, or reopen a checklist item.
        """

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        self._ensure_work_order_mutable(
            work_order
        )

        item = self._get_item_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            item_id=item_id,
        )

        target_status = payload.status.value
        previous_status = item.status

        if target_status == previous_status:
            return self._build_response(
                item
            )

        now = datetime.now(
            timezone.utc
        )

        if (
            target_status
            == WorkOrderChecklistStatus.COMPLETED.value
        ):
            item.status = target_status
            item.completion_note = payload.note
            item.completed_by_user_id = (
                actor_user_id
            )
            item.completed_at = now
            item.skipped_by_user_id = None
            item.skipped_at = None

            activity_type = (
                "checklist_item_completed"
            )

            summary = (
                f"Checklist item "
                f"'{item.title}' completed."
            )

        elif (
            target_status
            == WorkOrderChecklistStatus.SKIPPED.value
        ):
            item.status = target_status
            item.completion_note = payload.note
            item.skipped_by_user_id = (
                actor_user_id
            )
            item.skipped_at = now
            item.completed_by_user_id = None
            item.completed_at = None

            activity_type = (
                "checklist_item_skipped"
            )

            summary = (
                f"Checklist item "
                f"'{item.title}' skipped."
            )

        else:
            item.status = (
                WorkOrderChecklistStatus.PENDING.value
            )
            item.completion_note = None
            item.completed_by_user_id = None
            item.completed_at = None
            item.skipped_by_user_id = None
            item.skipped_at = None

            activity_type = (
                "checklist_item_reopened"
            )

            summary = (
                f"Checklist item "
                f"'{item.title}' reopened."
            )

        try:
            updated = self.checklist.update_item(
                item
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                activity_type=activity_type,
                summary=summary,
                note=payload.note,
                details={
                    "checklist_item_id": str(
                        updated.id
                    ),
                    "title": updated.title,
                    "from_status": previous_status,
                    "to_status": updated.status,
                    "is_required": (
                        updated.is_required
                    ),
                },
            )

            return self._build_response(
                updated
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The checklist status change "
                    "could not be saved."
                ),
            ) from exc

    def reorder_items(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        payload: WorkOrderChecklistReorderRequest,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderChecklistListResponse:
        """
        Replace the complete active checklist ordering.
        """

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        self._ensure_work_order_mutable(
            work_order
        )

        active_items = (
            self.checklist.list_for_work_order(
                organization_id=organization_id,
                work_order_id=work_order_id,
                skip=0,
                limit=10_000,
                include_inactive=False,
            )
        )

        active_item_ids = {
            item.id
            for item in active_items
        }

        requested_item_ids = set(
            payload.item_ids
        )

        if requested_item_ids != active_item_ids:
            missing_ids = sorted(
                str(item_id)
                for item_id
                in active_item_ids
                - requested_item_ids
            )

            unknown_ids = sorted(
                str(item_id)
                for item_id
                in requested_item_ids
                - active_item_ids
            )

            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail={
                    "message": (
                        "The reorder request must "
                        "contain every active checklist "
                        "item exactly once."
                    ),
                    "missing_item_ids": missing_ids,
                    "unknown_item_ids": unknown_ids,
                },
            )

        previous_order = [
            str(item.id)
            for item in active_items
        ]

        try:
            reordered = self.checklist.reorder_items(
                items=active_items,
                ordered_item_ids=payload.item_ids,
            )

            new_order = [
                str(item.id)
                for item in reordered
            ]

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                activity_type=(
                    "checklist_reordered"
                ),
                summary=(
                    "Work-order checklist reordered."
                ),
                details={
                    "previous_order": previous_order,
                    "new_order": new_order,
                },
            )

            return WorkOrderChecklistListResponse(
                items=[
                    self._build_response(item)
                    for item in reordered
                ],
                total=len(reordered),
                skip=0,
                limit=len(reordered),
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The checklist ordering could "
                    "not be saved."
                ),
            ) from exc

    def deactivate_item(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
    ) -> None:
        """
        Soft-delete a checklist item.
        """

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        self._ensure_work_order_mutable(
            work_order
        )

        item = self._get_item_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            item_id=item_id,
        )

        self.checklist.deactivate_item(
            item
        )

        self._record_activity(
            organization_id=organization_id,
            work_order_id=work_order_id,
            actor_user_id=actor_user_id,
            activity_type=(
                "checklist_item_deactivated"
            ),
            summary=(
                f"Checklist item "
                f"'{item.title}' deactivated."
            ),
            details={
                "checklist_item_id": str(
                    item.id
                ),
                "title": item.title,
            },
        )

    def reactivate_item(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderChecklistItemResponse:
        """
        Reactivate a checklist item.
        """

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        self._ensure_work_order_mutable(
            work_order
        )

        item = self._get_item_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            item_id=item_id,
            include_inactive=True,
        )

        if not item.is_active:
            item = self.checklist.reactivate_item(
                item
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                activity_type=(
                    "checklist_item_reactivated"
                ),
                summary=(
                    f"Checklist item "
                    f"'{item.title}' reactivated."
                ),
                details={
                    "checklist_item_id": str(
                        item.id
                    ),
                    "title": item.title,
                },
            )

        return self._build_response(
            item
        )

    def get_progress(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
    ) -> WorkOrderChecklistProgressResponse:
        """
        Return checklist progress for one work order.
        """

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        counts = self.checklist.get_progress_counts(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        total_items = counts["total_items"]
        completed_items = counts["completed_items"]
        required_items = counts["required_items"]

        completed_required_items = counts[
            "completed_required_items"
        ]

        incomplete_required_items = max(
            required_items
            - completed_required_items,
            0,
        )

        if total_items == 0:
            completion_percentage = 100.0
        else:
            completion_percentage = round(
                (
                    completed_items
                    / total_items
                )
                * 100,
                2,
            )

        return WorkOrderChecklistProgressResponse(
            total_items=total_items,
            pending_items=counts["pending_items"],
            completed_items=completed_items,
            skipped_items=counts["skipped_items"],
            required_items=required_items,
            completed_required_items=(
                completed_required_items
            ),
            incomplete_required_items=(
                incomplete_required_items
            ),
            completion_percentage=(
                completion_percentage
            ),
            can_complete_work_order=(
                incomplete_required_items == 0
            ),
        )