"""
Scheduling service.

Contains scheduling, dispatch, calendar listing, and resource
conflict detection for work orders.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Iterable

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    Session,
    joinedload,
    selectinload,
)

from app.models.asset import Asset
from app.models.membership import Membership
from app.models.work_order import (
    WorkOrder,
    WorkOrderAssetAssignment,
    WorkOrderWorkforceAssignment,
)
from app.models.work_order_activity import WorkOrderActivity
from app.models.workforce_profile import WorkforceProfile
from app.schemas.scheduling import (
    DispatchWorkOrderSchema,
    ScheduleCalendarItem,
    ScheduleCalendarResponse,
    ScheduleConflictCheckSchema,
    ScheduleConflictItem,
    ScheduleConflictResponse,
    ScheduleWorkOrderResponse,
    ScheduleWorkOrderSchema,
)
from app.schemas.work_order import WorkOrderResponse


BLOCKED_SCHEDULE_STATUSES = {
    "completed",
    "cancelled",
}

CONFLICT_STATUS_EXCLUSIONS = {
    "completed",
    "cancelled",
}

BLOCKED_ASSET_STATUSES = {
    "maintenance",
    "unavailable",
    "retired",
}


class SchedulingService:
    """
    Handles work-order scheduling and dispatch logic.
    """

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    @staticmethod
    def _normalize_datetime(
        value: datetime,
    ) -> datetime:
        """
        Ensure datetime values are timezone-aware.
        """

        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc,
            )

        return value

    @staticmethod
    def _dedupe_ids(
        values: Iterable[uuid.UUID],
    ) -> list[uuid.UUID]:
        """
        Preserve UUID order while removing duplicates.
        """

        seen: set[uuid.UUID] = set()
        deduped: list[uuid.UUID] = []

        for value in values:
            if value in seen:
                continue

            seen.add(value)
            deduped.append(value)

        return deduped

    @staticmethod
    def _work_order_options():
        """
        Return eager-loading options for calendar responses.
        """

        return (
            joinedload(WorkOrder.customer),
            joinedload(WorkOrder.customer_site),
            selectinload(
                WorkOrder.workforce_assignments
            ),
            selectinload(
                WorkOrder.asset_assignments
            ),
        )

    def _get_work_order_or_404(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrder:
        """
        Retrieve one organization work order.
        """

        query = (
            self.db.query(WorkOrder)
            .options(
                *self._work_order_options()
            )
            .populate_existing()
            .filter(
                WorkOrder.id == work_order_id,
                WorkOrder.organization_id == organization_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrder.is_active.is_(True)
            )

        work_order = query.first()

        if work_order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work order not found.",
            )

        return work_order

    @staticmethod
    def _build_work_order_response(
        work_order: WorkOrder,
    ) -> WorkOrderResponse:
        """
        Convert a work-order ORM object into the existing response
        schema.
        """

        return WorkOrderResponse(
            id=work_order.id,
            organization_id=work_order.organization_id,
            customer_id=work_order.customer_id,
            customer_site_id=work_order.customer_site_id,
            work_order_number=work_order.work_order_number,
            title=work_order.title,
            description=work_order.description,
            job_type=work_order.job_type,
            customer_reference=work_order.customer_reference,
            priority=work_order.priority,
            status=work_order.status,
            scheduled_start=work_order.scheduled_start,
            scheduled_end=work_order.scheduled_end,
            actual_start=work_order.actual_start,
            actual_end=work_order.actual_end,
            estimated_cost=work_order.estimated_cost,
            actual_cost=work_order.actual_cost,
            instructions=work_order.instructions,
            completion_notes=work_order.completion_notes,
            cancellation_reason=work_order.cancellation_reason,
            workforce_profile_ids=[
                assignment.workforce_profile_id
                for assignment
                in work_order.workforce_assignments
            ],
            asset_ids=[
                assignment.asset_id
                for assignment
                in work_order.asset_assignments
            ],
            is_active=work_order.is_active,
            created_at=work_order.created_at,
            updated_at=work_order.updated_at,
        )

    @staticmethod
    def _build_calendar_item(
        work_order: WorkOrder,
    ) -> ScheduleCalendarItem:
        """
        Convert a work order into one calendar row.
        """

        return ScheduleCalendarItem(
            id=work_order.id,
            organization_id=work_order.organization_id,
            work_order_number=work_order.work_order_number,
            title=work_order.title,
            description=work_order.description,
            job_type=work_order.job_type,
            customer_id=work_order.customer_id,
            customer_name=(
                work_order.customer.name
                if work_order.customer
                else None
            ),
            customer_site_id=work_order.customer_site_id,
            customer_site_name=(
                work_order.customer_site.name
                if work_order.customer_site
                else None
            ),
            priority=work_order.priority,
            status=work_order.status,
            scheduled_start=work_order.scheduled_start,
            scheduled_end=work_order.scheduled_end,
            workforce_profile_ids=[
                assignment.workforce_profile_id
                for assignment
                in work_order.workforce_assignments
            ],
            asset_ids=[
                assignment.asset_id
                for assignment
                in work_order.asset_assignments
            ],
        )

    @staticmethod
    def _resource_name(
        resource: WorkforceProfile | Asset | None,
    ) -> str | None:
        """
        Return a human-readable resource name.
        """

        if resource is None:
            return None

        if isinstance(resource, Asset):
            return resource.name

        membership = resource.membership

        if membership and membership.user:
            user = membership.user

            return (
                f"{user.first_name} {user.last_name}"
            ).strip()

        if resource.employee_code:
            return resource.employee_code

        return str(resource.id)

    def _record_activity(
        self,
        *,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        activity_type: str,
        summary: str,
        from_status: str | None = None,
        to_status: str | None = None,
        note: str | None = None,
        details: dict | None = None,
    ) -> None:
        """
        Add a work-order timeline entry.
        """

        self.db.add(
            WorkOrderActivity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                activity_type=activity_type,
                summary=summary,
                from_status=from_status,
                to_status=to_status,
                note=note,
                details=details or {},
            )
        )

    def _validate_workforce(
        self,
        organization_id: uuid.UUID,
        workforce_profile_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, WorkforceProfile]:
        """
        Validate workforce profiles used for scheduling.
        """

        if not workforce_profile_ids:
            return {}

        profiles = (
            self.db.query(WorkforceProfile)
            .options(
                joinedload(
                    WorkforceProfile.membership
                ).joinedload(
                    Membership.user
                )
            )
            .filter(
                WorkforceProfile.organization_id == organization_id,
                WorkforceProfile.id.in_(workforce_profile_ids),
                WorkforceProfile.is_active.is_(True),
            )
            .all()
        )

        profile_map = {
            profile.id: profile
            for profile in profiles
        }

        missing_ids = [
            profile_id
            for profile_id in workforce_profile_ids
            if profile_id not in profile_map
        ]

        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "One or more active workforce profiles "
                    "were not found."
                ),
            )

        unavailable = [
            profile
            for profile in profiles
            if (
                profile.status != "active"
                or not profile.is_available
            )
        ]

        if unavailable:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only active and available workforce "
                    "profiles can be scheduled."
                ),
            )

        return profile_map

    def _validate_assets(
        self,
        organization_id: uuid.UUID,
        asset_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, Asset]:
        """
        Validate assets used for scheduling.
        """

        if not asset_ids:
            return {}

        assets = (
            self.db.query(Asset)
            .filter(
                Asset.organization_id == organization_id,
                Asset.id.in_(asset_ids),
                Asset.is_active.is_(True),
            )
            .all()
        )

        asset_map = {
            asset.id: asset
            for asset in assets
        }

        missing_ids = [
            asset_id
            for asset_id in asset_ids
            if asset_id not in asset_map
        ]

        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "One or more active assets were not found."
                ),
            )

        blocked_assets = [
            asset
            for asset in assets
            if asset.status in BLOCKED_ASSET_STATUSES
        ]

        if blocked_assets:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Assets in maintenance, unavailable, "
                    "or retired status cannot be scheduled."
                ),
            )

        return asset_map

    def _replace_workforce_assignments(
        self,
        work_order: WorkOrder,
        workforce_profile_ids: list[uuid.UUID],
    ) -> None:
        """
        Replace all workforce assignments for a work order.
        """

        (
            self.db.query(WorkOrderWorkforceAssignment)
            .filter(
                WorkOrderWorkforceAssignment.work_order_id
                == work_order.id
            )
            .delete(
                synchronize_session=False,
            )
        )

        for profile_id in workforce_profile_ids:
            self.db.add(
                WorkOrderWorkforceAssignment(
                    work_order_id=work_order.id,
                    workforce_profile_id=profile_id,
                )
            )

    def _replace_asset_assignments(
        self,
        work_order: WorkOrder,
        asset_ids: list[uuid.UUID],
    ) -> None:
        """
        Replace all asset assignments for a work order.
        """

        (
            self.db.query(WorkOrderAssetAssignment)
            .filter(
                WorkOrderAssetAssignment.work_order_id
                == work_order.id
            )
            .delete(
                synchronize_session=False,
            )
        )

        for asset_id in asset_ids:
            self.db.add(
                WorkOrderAssetAssignment(
                    work_order_id=work_order.id,
                    asset_id=asset_id,
                )
            )

    def _overlapping_work_orders_query(
        self,
        organization_id: uuid.UUID,
        scheduled_start: datetime,
        scheduled_end: datetime,
    ):
        """
        Base query for overlapping active work orders.
        """

        return (
            self.db.query(WorkOrder)
            .options(
                *self._work_order_options()
            )
            .filter(
                WorkOrder.organization_id == organization_id,
                WorkOrder.is_active.is_(True),
                WorkOrder.scheduled_start.isnot(None),
                WorkOrder.scheduled_end.isnot(None),
                WorkOrder.scheduled_start < scheduled_end,
                WorkOrder.scheduled_end > scheduled_start,
                WorkOrder.status.notin_(
                    CONFLICT_STATUS_EXCLUSIONS
                ),
            )
        )

    def check_conflicts(
        self,
        organization_id: uuid.UUID,
        payload: ScheduleConflictCheckSchema,
    ) -> ScheduleConflictResponse:
        """
        Check workforce and asset conflicts for a proposed booking.
        """

        scheduled_start = self._normalize_datetime(
            payload.scheduled_start
        )
        scheduled_end = self._normalize_datetime(
            payload.scheduled_end
        )

        workforce_profile_ids = self._dedupe_ids(
            payload.workforce_profile_ids
        )
        asset_ids = self._dedupe_ids(
            payload.asset_ids
        )

        workforce_map = self._validate_workforce(
            organization_id=organization_id,
            workforce_profile_ids=workforce_profile_ids,
        )
        asset_map = self._validate_assets(
            organization_id=organization_id,
            asset_ids=asset_ids,
        )

        conflicts: list[ScheduleConflictItem] = []

        if workforce_profile_ids:
            rows = (
                self._overlapping_work_orders_query(
                    organization_id,
                    scheduled_start,
                    scheduled_end,
                )
                .join(
                    WorkOrderWorkforceAssignment,
                    WorkOrderWorkforceAssignment.work_order_id
                    == WorkOrder.id,
                )
                .filter(
                    WorkOrderWorkforceAssignment
                    .workforce_profile_id
                    .in_(workforce_profile_ids)
                )
            )

            if payload.exclude_work_order_id:
                rows = rows.filter(
                    WorkOrder.id != payload.exclude_work_order_id
                )

            for work_order in rows.all():
                for assignment in work_order.workforce_assignments:
                    if (
                        assignment.workforce_profile_id
                        not in workforce_profile_ids
                    ):
                        continue

                    conflicts.append(
                        ScheduleConflictItem(
                            conflict_type="workforce",
                            resource_id=(
                                assignment.workforce_profile_id
                            ),
                            resource_name=self._resource_name(
                                workforce_map.get(
                                    assignment.workforce_profile_id
                                )
                            ),
                            work_order_id=work_order.id,
                            work_order_number=(
                                work_order.work_order_number
                            ),
                            title=work_order.title,
                            status=work_order.status,
                            scheduled_start=(
                                work_order.scheduled_start
                            ),
                            scheduled_end=(
                                work_order.scheduled_end
                            ),
                        )
                    )

        if asset_ids:
            rows = (
                self._overlapping_work_orders_query(
                    organization_id,
                    scheduled_start,
                    scheduled_end,
                )
                .join(
                    WorkOrderAssetAssignment,
                    WorkOrderAssetAssignment.work_order_id
                    == WorkOrder.id,
                )
                .filter(
                    WorkOrderAssetAssignment.asset_id.in_(
                        asset_ids
                    )
                )
            )

            if payload.exclude_work_order_id:
                rows = rows.filter(
                    WorkOrder.id != payload.exclude_work_order_id
                )

            for work_order in rows.all():
                for assignment in work_order.asset_assignments:
                    if assignment.asset_id not in asset_ids:
                        continue

                    conflicts.append(
                        ScheduleConflictItem(
                            conflict_type="asset",
                            resource_id=assignment.asset_id,
                            resource_name=self._resource_name(
                                asset_map.get(
                                    assignment.asset_id
                                )
                            ),
                            work_order_id=work_order.id,
                            work_order_number=(
                                work_order.work_order_number
                            ),
                            title=work_order.title,
                            status=work_order.status,
                            scheduled_start=(
                                work_order.scheduled_start
                            ),
                            scheduled_end=(
                                work_order.scheduled_end
                            ),
                        )
                    )

        conflicts.sort(
            key=lambda item: (
                item.scheduled_start,
                item.conflict_type,
                item.resource_name or "",
            )
        )

        return ScheduleConflictResponse(
            has_conflicts=bool(conflicts),
            conflicts=conflicts,
        )

    def list_calendar(
        self,
        organization_id: uuid.UUID,
        *,
        start: datetime,
        end: datetime,
        skip: int = 0,
        limit: int = 100,
        status_filter: str | None = None,
        workforce_profile_id: uuid.UUID | None = None,
        asset_id: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
        customer_site_id: uuid.UUID | None = None,
        include_unscheduled: bool = False,
        include_inactive: bool = False,
    ) -> ScheduleCalendarResponse:
        """
        Return work orders for the scheduling calendar.
        """

        start = self._normalize_datetime(
            start
        )
        end = self._normalize_datetime(
            end
        )

        if end <= start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="end must be after start.",
            )

        query = (
            self.db.query(WorkOrder)
            .options(
                *self._work_order_options()
            )
            .filter(
                WorkOrder.organization_id == organization_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrder.is_active.is_(True)
            )

        scheduled_overlap = (
            WorkOrder.scheduled_start.isnot(None),
            WorkOrder.scheduled_end.isnot(None),
            WorkOrder.scheduled_start < end,
            WorkOrder.scheduled_end > start,
        )

        if include_unscheduled:
            query = query.filter(
                or_(
                    WorkOrder.scheduled_start.is_(None),
                    WorkOrder.scheduled_end.is_(None),
                    *scheduled_overlap,
                )
            )
        else:
            query = query.filter(
                *scheduled_overlap,
            )

        if status_filter:
            query = query.filter(
                WorkOrder.status == status_filter
            )

        if customer_id:
            query = query.filter(
                WorkOrder.customer_id == customer_id
            )

        if customer_site_id:
            query = query.filter(
                WorkOrder.customer_site_id == customer_site_id
            )

        if workforce_profile_id:
            query = query.join(
                WorkOrderWorkforceAssignment,
                WorkOrderWorkforceAssignment.work_order_id
                == WorkOrder.id,
            ).filter(
                WorkOrderWorkforceAssignment.workforce_profile_id
                == workforce_profile_id
            )

        if asset_id:
            query = query.join(
                WorkOrderAssetAssignment,
                WorkOrderAssetAssignment.work_order_id
                == WorkOrder.id,
            ).filter(
                WorkOrderAssetAssignment.asset_id == asset_id
            )

        query = query.distinct()

        total = query.count()

        work_orders = (
            query.order_by(
                WorkOrder.scheduled_start.asc().nullslast(),
                WorkOrder.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

        return ScheduleCalendarResponse(
            items=[
                self._build_calendar_item(work_order)
                for work_order in work_orders
            ],
            total=total,
            skip=skip,
            limit=limit,
        )

    def schedule_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        payload: ScheduleWorkOrderSchema,
        *,
        actor_user_id: uuid.UUID,
    ) -> ScheduleWorkOrderResponse:
        """
        Schedule a work order, optionally replacing workforce and
        asset assignments in the same operation.
        """

        scheduled_start = self._normalize_datetime(
            payload.scheduled_start
        )
        scheduled_end = self._normalize_datetime(
            payload.scheduled_end
        )

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        if work_order.status in BLOCKED_SCHEDULE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Completed or cancelled work orders "
                    "cannot be scheduled."
                ),
            )

        workforce_profile_ids = (
            self._dedupe_ids(payload.workforce_profile_ids)
            if payload.workforce_profile_ids is not None
            else [
                assignment.workforce_profile_id
                for assignment
                in work_order.workforce_assignments
            ]
        )

        asset_ids = (
            self._dedupe_ids(payload.asset_ids)
            if payload.asset_ids is not None
            else [
                assignment.asset_id
                for assignment
                in work_order.asset_assignments
            ]
        )

        self._validate_workforce(
            organization_id=organization_id,
            workforce_profile_ids=workforce_profile_ids,
        )
        self._validate_assets(
            organization_id=organization_id,
            asset_ids=asset_ids,
        )

        conflicts_response = self.check_conflicts(
            organization_id=organization_id,
            payload=ScheduleConflictCheckSchema(
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                workforce_profile_ids=workforce_profile_ids,
                asset_ids=asset_ids,
                exclude_work_order_id=work_order.id,
            ),
        )

        if (
            conflicts_response.has_conflicts
            and payload.fail_on_conflict
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Scheduling conflict detected. "
                    "Review the calendar before booking."
                ),
            )

        previous_status = work_order.status
        next_status = previous_status

        if (
            payload.set_status_to_scheduled
            and previous_status in {"draft", "on_hold"}
        ):
            next_status = "scheduled"

        work_order.scheduled_start = scheduled_start
        work_order.scheduled_end = scheduled_end
        work_order.status = next_status

        try:
            if payload.workforce_profile_ids is not None:
                self._replace_workforce_assignments(
                    work_order,
                    workforce_profile_ids,
                )

            if payload.asset_ids is not None:
                self._replace_asset_assignments(
                    work_order,
                    asset_ids,
                )

            activity_type = (
                "status_changed"
                if previous_status != next_status
                else "updated"
            )

            summary = (
                "Work order scheduled."
                if previous_status != next_status
                else "Work-order schedule updated."
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order.id,
                actor_user_id=actor_user_id,
                activity_type=activity_type,
                summary=summary,
                from_status=(
                    previous_status
                    if previous_status != next_status
                    else None
                ),
                to_status=(
                    next_status
                    if previous_status != next_status
                    else None
                ),
                note=payload.note,
                details={
                    "scheduled_start": (
                        scheduled_start.isoformat()
                    ),
                    "scheduled_end": (
                        scheduled_end.isoformat()
                    ),
                    "workforce_profile_ids": [
                        str(profile_id)
                        for profile_id in workforce_profile_ids
                    ],
                    "asset_ids": [
                        str(asset_id)
                        for asset_id in asset_ids
                    ],
                    "conflict_count": len(
                        conflicts_response.conflicts
                    ),
                },
            )

            self.db.commit()

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The schedule conflicts with an "
                    "existing assignment."
                ),
            ) from exc

        refreshed = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order.id,
        )

        return ScheduleWorkOrderResponse(
            work_order=self._build_work_order_response(
                refreshed
            ),
            conflicts=conflicts_response.conflicts,
        )

    def dispatch_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        payload: DispatchWorkOrderSchema,
        *,
        actor_user_id: uuid.UUID,
    ) -> ScheduleWorkOrderResponse:
        """
        Dispatch a scheduled work order.
        """

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        if work_order.status == "dispatched":
            return ScheduleWorkOrderResponse(
                work_order=self._build_work_order_response(
                    work_order
                ),
                conflicts=[],
            )

        if work_order.status != "scheduled":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only scheduled work orders can be "
                    "dispatched."
                ),
            )

        if (
            work_order.scheduled_start is None
            or work_order.scheduled_end is None
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Scheduled start and end are required "
                    "before dispatch."
                ),
            )

        workforce_profile_ids = [
            assignment.workforce_profile_id
            for assignment
            in work_order.workforce_assignments
        ]

        asset_ids = [
            assignment.asset_id
            for assignment
            in work_order.asset_assignments
        ]

        if not workforce_profile_ids:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "At least one workforce member is "
                    "required before dispatch."
                ),
            )

        conflicts_response = self.check_conflicts(
            organization_id=organization_id,
            payload=ScheduleConflictCheckSchema(
                scheduled_start=work_order.scheduled_start,
                scheduled_end=work_order.scheduled_end,
                workforce_profile_ids=workforce_profile_ids,
                asset_ids=asset_ids,
                exclude_work_order_id=work_order.id,
            ),
        )

        if (
            conflicts_response.has_conflicts
            and payload.fail_on_conflict
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Dispatch blocked because one or more "
                    "assigned resources have conflicts."
                ),
            )

        previous_status = work_order.status
        work_order.status = "dispatched"

        self._record_activity(
            organization_id=organization_id,
            work_order_id=work_order.id,
            actor_user_id=actor_user_id,
            activity_type="status_changed",
            summary="Work order dispatched.",
            from_status=previous_status,
            to_status="dispatched",
            note=payload.note,
            details={
                "scheduled_start": (
                    work_order.scheduled_start.isoformat()
                ),
                "scheduled_end": (
                    work_order.scheduled_end.isoformat()
                ),
                "workforce_profile_ids": [
                    str(profile_id)
                    for profile_id in workforce_profile_ids
                ],
                "asset_ids": [
                    str(asset_id)
                    for asset_id in asset_ids
                ],
                "conflict_count": len(
                    conflicts_response.conflicts
                ),
            },
        )

        self.db.commit()

        refreshed = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order.id,
        )

        return ScheduleWorkOrderResponse(
            work_order=self._build_work_order_response(
                refreshed
            ),
            conflicts=conflicts_response.conflicts,
        )
