"""
Work-order service.

Contains validation, status transitions, assignments, checklist
completion enforcement, and activity timeline recording for
field-service work orders.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.customer import Customer
from app.models.customer_site import CustomerSite
from app.models.work_order import (
    WorkOrder,
    WorkOrderAssetAssignment,
    WorkOrderWorkforceAssignment,
)
from app.models.work_order_activity import WorkOrderActivity
from app.models.workforce_profile import WorkforceProfile
from app.repositories.work_order import WorkOrderRepository
from app.repositories.work_order_activity import (
    WorkOrderActivityRepository,
)
from app.repositories.work_order_checklist import (
    WorkOrderChecklistRepository,
)
from app.schemas.work_order import (
    ChangeWorkOrderStatusSchema,
    CreateWorkOrderSchema,
    UpdateWorkOrderSchema,
    WorkOrderListResponse,
    WorkOrderResponse,
)


ALLOWED_STATUS_TRANSITIONS = {
    "draft": {
        "scheduled",
        "cancelled",
    },
    "scheduled": {
        "dispatched",
        "in_progress",
        "on_hold",
        "cancelled",
    },
    "dispatched": {
        "in_progress",
        "on_hold",
        "cancelled",
    },
    "in_progress": {
        "on_hold",
        "completed",
        "cancelled",
    },
    "on_hold": {
        "scheduled",
        "dispatched",
        "in_progress",
        "cancelled",
    },
    "completed": set(),
    "cancelled": set(),
}


class WorkOrderService:
    """
    Handles work-order business logic.
    """

    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.work_orders = WorkOrderRepository(db)
        self.activities = WorkOrderActivityRepository(db)
        self.checklist = WorkOrderChecklistRepository(db)

    @staticmethod
    def _build_response(
        work_order: WorkOrder,
    ) -> WorkOrderResponse:
        """
        Convert a work-order model into an API response.
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
        details: dict[str, Any] | None = None,
    ) -> WorkOrderActivity:
        """
        Record one immutable activity timeline entry.
        """

        activity = WorkOrderActivity(
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
        Retrieve one work order or raise 404.
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

    def _get_customer_or_404(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
    ) -> Customer:
        """
        Retrieve an active organization customer.
        """

        customer = (
            self.db.query(Customer)
            .filter(
                Customer.id == customer_id,
                Customer.organization_id
                == organization_id,
                Customer.is_active.is_(True),
            )
            .first()
        )

        if customer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active customer not found.",
            )

        return customer

    def _validate_site(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        customer_site_id: uuid.UUID | None,
    ) -> CustomerSite | None:
        """
        Validate that a site belongs to the selected customer.
        """

        if customer_site_id is None:
            return None

        customer_site = (
            self.db.query(CustomerSite)
            .filter(
                CustomerSite.id == customer_site_id,
                CustomerSite.organization_id
                == organization_id,
                CustomerSite.customer_id
                == customer_id,
                CustomerSite.is_active.is_(True),
            )
            .first()
        )

        if customer_site is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Active customer site not found "
                    "for the selected customer."
                ),
            )

        return customer_site

    def _generate_work_order_number(
        self,
        organization_id: uuid.UUID,
    ) -> str:
        """
        Generate an organization-safe work-order number.
        """

        date_part = datetime.now(
            timezone.utc
        ).strftime("%Y%m%d")

        for _ in range(10):
            suffix = uuid.uuid4().hex[:6].upper()
            candidate = f"WO-{date_part}-{suffix}"

            if not self.work_orders.number_exists(
                organization_id=organization_id,
                work_order_number=candidate,
            ):
                return candidate

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Unable to generate a unique "
                "work-order number."
            ),
        )

    def _ensure_number_available(
        self,
        organization_id: uuid.UUID,
        work_order_number: str,
        *,
        exclude_work_order_id: uuid.UUID | None = None,
    ) -> None:
        """
        Ensure a work-order number is unique.
        """

        if self.work_orders.number_exists(
            organization_id=organization_id,
            work_order_number=work_order_number,
            exclude_work_order_id=exclude_work_order_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another work order already uses "
                    "this work-order number."
                ),
            )

    @staticmethod
    def _validate_schedule(
        scheduled_start: datetime | None,
        scheduled_end: datetime | None,
    ) -> None:
        """
        Validate start and end schedule values.
        """

        if (
            scheduled_start is not None
            and scheduled_end is not None
            and scheduled_end <= scheduled_start
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Scheduled end must be after "
                    "scheduled start."
                ),
            )

    def _ensure_required_checklist_complete(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
    ) -> None:
        """
        Prevent completion while required checklist items remain.

        Only active checklist items are considered. Required
        items must have the completed status. Skipping a required
        item does not satisfy the completion requirement.
        """

        counts = self.checklist.get_progress_counts(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        required_items = counts[
            "required_items"
        ]

        completed_required_items = counts[
            "completed_required_items"
        ]

        incomplete_required_items = max(
            required_items
            - completed_required_items,
            0,
        )

        if incomplete_required_items > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": (
                        "All required checklist items "
                        "must be completed before the "
                        "work order can be completed."
                    ),
                    "required_items": required_items,
                    "completed_required_items": (
                        completed_required_items
                    ),
                    "incomplete_required_items": (
                        incomplete_required_items
                    ),
                },
            )

    def create_work_order(
        self,
        organization_id: uuid.UUID,
        payload: CreateWorkOrderSchema,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderResponse:
        """
        Create a work order and its first activity.
        """

        self._get_customer_or_404(
            organization_id=organization_id,
            customer_id=payload.customer_id,
        )

        self._validate_site(
            organization_id=organization_id,
            customer_id=payload.customer_id,
            customer_site_id=payload.customer_site_id,
        )

        work_order_data = payload.model_dump()

        work_order_number = (
            work_order_data.pop(
                "work_order_number"
            )
            or self._generate_work_order_number(
                organization_id
            )
        )

        self._ensure_number_available(
            organization_id=organization_id,
            work_order_number=work_order_number,
        )

        work_order = WorkOrder(
            organization_id=organization_id,
            work_order_number=work_order_number,
            **work_order_data,
        )

        try:
            created = self.work_orders.create_work_order(
                work_order
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=created.id,
                actor_user_id=actor_user_id,
                activity_type="created",
                summary=(
                    f"Work order "
                    f"{created.work_order_number} created."
                ),
                to_status=created.status,
                details={
                    "customer_id": str(
                        created.customer_id
                    ),
                    "customer_site_id": (
                        str(created.customer_site_id)
                        if created.customer_site_id
                        else None
                    ),
                },
            )

            loaded = (
                self.work_orders.get_for_organization(
                    organization_id=organization_id,
                    work_order_id=created.id,
                    include_inactive=True,
                )
            )

            if loaded is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        "Unable to load the created "
                        "work order."
                    ),
                )

            return self._build_response(
                loaded
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The work order conflicts with "
                    "an existing record."
                ),
            ) from exc

    def list_work_orders(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        status_filter: str | None = None,
        priority: str | None = None,
        customer_id: uuid.UUID | None = None,
        customer_site_id: uuid.UUID | None = None,
        include_inactive: bool = False,
    ) -> WorkOrderListResponse:
        """
        List organization work orders.
        """

        work_orders = (
            self.work_orders.list_for_organization(
                organization_id=organization_id,
                skip=skip,
                limit=limit,
                search=search,
                status_filter=status_filter,
                priority=priority,
                customer_id=customer_id,
                customer_site_id=customer_site_id,
                include_inactive=include_inactive,
            )
        )

        total = (
            self.work_orders.count_for_organization(
                organization_id=organization_id,
                search=search,
                status_filter=status_filter,
                priority=priority,
                customer_id=customer_id,
                customer_site_id=customer_site_id,
                include_inactive=include_inactive,
            )
        )

        return WorkOrderListResponse(
            items=[
                self._build_response(item)
                for item in work_orders
            ],
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrderResponse:
        """
        Return one work order.
        """

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            include_inactive=include_inactive,
        )

        return self._build_response(
            work_order
        )

    def update_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        payload: UpdateWorkOrderSchema,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderResponse:
        """
        Update work-order details and record the change.
        """

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        if work_order.status in {
            "completed",
            "cancelled",
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Completed or cancelled work orders "
                    "cannot be edited."
                ),
            )

        update_data = payload.model_dump(
            exclude_unset=True
        )

        if not update_data:
            return self._build_response(
                work_order
            )

        required_fields = {
            "customer_id",
            "work_order_number",
            "title",
            "priority",
        }

        for field_name in required_fields:
            if (
                field_name in update_data
                and update_data[field_name] is None
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"{field_name.replace('_', ' ').title()} "
                        "cannot be null."
                    ),
                )

        final_customer_id = update_data.get(
            "customer_id",
            work_order.customer_id,
        )

        final_customer_site_id = update_data.get(
            "customer_site_id",
            work_order.customer_site_id,
        )

        self._get_customer_or_404(
            organization_id=organization_id,
            customer_id=final_customer_id,
        )

        self._validate_site(
            organization_id=organization_id,
            customer_id=final_customer_id,
            customer_site_id=final_customer_site_id,
        )

        final_scheduled_start = update_data.get(
            "scheduled_start",
            work_order.scheduled_start,
        )

        final_scheduled_end = update_data.get(
            "scheduled_end",
            work_order.scheduled_end,
        )

        self._validate_schedule(
            scheduled_start=final_scheduled_start,
            scheduled_end=final_scheduled_end,
        )

        if "work_order_number" in update_data:
            self._ensure_number_available(
                organization_id=organization_id,
                work_order_number=update_data[
                    "work_order_number"
                ],
                exclude_work_order_id=work_order.id,
            )

        changed_fields = sorted(
            update_data.keys()
        )

        for field_name, field_value in update_data.items():
            setattr(
                work_order,
                field_name,
                field_value,
            )

        try:
            updated = self.work_orders.update_work_order(
                work_order
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=updated.id,
                actor_user_id=actor_user_id,
                activity_type="updated",
                summary="Work-order details updated.",
                details={
                    "changed_fields": changed_fields,
                },
            )

            refreshed = self._get_work_order_or_404(
                organization_id=organization_id,
                work_order_id=updated.id,
            )

            return self._build_response(
                refreshed
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The work order conflicts with "
                    "an existing record."
                ),
            ) from exc

    def change_status(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        payload: ChangeWorkOrderStatusSchema,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderResponse:
        """
        Change work-order status and record the transition.
        """

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        if payload.status == work_order.status:
            return self._build_response(
                work_order
            )

        previous_status = work_order.status

        allowed_statuses = (
            ALLOWED_STATUS_TRANSITIONS.get(
                previous_status,
                set(),
            )
        )

        if payload.status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot change work-order status "
                    f"from {previous_status} "
                    f"to {payload.status}."
                ),
            )

        if (
            payload.status in {
                "scheduled",
                "dispatched",
            }
            and work_order.scheduled_start is None
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A scheduled start is required "
                    "before scheduling or dispatching."
                ),
            )

        if payload.status == "completed":
            self._ensure_required_checklist_complete(
                organization_id=organization_id,
                work_order_id=work_order_id,
            )

        now = datetime.now(
            timezone.utc
        )

        if payload.status == "in_progress":
            if work_order.actual_start is None:
                work_order.actual_start = now

        if payload.status == "completed":
            work_order.actual_end = now

            if payload.note:
                work_order.completion_notes = (
                    payload.note
                )

        if payload.status == "cancelled":
            work_order.cancellation_reason = (
                payload.note
                or "No cancellation reason supplied."
            )

            if work_order.actual_start is not None:
                work_order.actual_end = now

        if payload.status == "on_hold":
            if payload.note:
                work_order.completion_notes = (
                    payload.note
                )

        work_order.status = payload.status

        updated = self.work_orders.update_work_order(
            work_order
        )

        self._record_activity(
            organization_id=organization_id,
            work_order_id=updated.id,
            actor_user_id=actor_user_id,
            activity_type="status_changed",
            summary=(
                f"Status changed from "
                f"{previous_status} to {payload.status}."
            ),
            from_status=previous_status,
            to_status=payload.status,
            note=payload.note,
        )

        refreshed = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=updated.id,
        )

        return self._build_response(
            refreshed
        )

    def deactivate_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
    ) -> None:
        """
        Deactivate a work order and record the action.
        """

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        if work_order.status in {
            "dispatched",
            "in_progress",
            "on_hold",
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "An active field work order cannot "
                    "be deactivated."
                ),
            )

        self.work_orders.deactivate(
            work_order
        )

        self._record_activity(
            organization_id=organization_id,
            work_order_id=work_order.id,
            actor_user_id=actor_user_id,
            activity_type="deactivated",
            summary="Work order deactivated.",
        )

    def reactivate_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderResponse:
        """
        Reactivate a work order and record the action.
        """

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            include_inactive=True,
        )

        if not work_order.is_active:
            work_order = self.work_orders.reactivate(
                work_order
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order.id,
                actor_user_id=actor_user_id,
                activity_type="reactivated",
                summary="Work order reactivated.",
            )

        refreshed = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order.id,
            include_inactive=True,
        )

        return self._build_response(
            refreshed
        )

    def assign_workforce(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        workforce_profile_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderResponse:
        """
        Assign workforce and record the assignment.
        """

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        workforce_profile = (
            self.db.query(WorkforceProfile)
            .filter(
                WorkforceProfile.id
                == workforce_profile_id,
                WorkforceProfile.organization_id
                == organization_id,
                WorkforceProfile.is_active.is_(True),
                WorkforceProfile.status == "active",
            )
            .first()
        )

        if workforce_profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Active workforce profile not found."
                ),
            )

        existing_assignment = (
            self.work_orders.get_workforce_assignment(
                work_order_id=work_order.id,
                workforce_profile_id=(
                    workforce_profile.id
                ),
            )
        )

        if existing_assignment is None:
            assignment = WorkOrderWorkforceAssignment(
                work_order_id=work_order.id,
                workforce_profile_id=(
                    workforce_profile.id
                ),
            )

            try:
                self.work_orders.add_workforce_assignment(
                    assignment
                )

                self._record_activity(
                    organization_id=organization_id,
                    work_order_id=work_order.id,
                    actor_user_id=actor_user_id,
                    activity_type="workforce_assigned",
                    summary=(
                        "Workforce member assigned "
                        "to work order."
                    ),
                    details={
                        "workforce_profile_id": str(
                            workforce_profile.id
                        ),
                    },
                )

            except IntegrityError as exc:
                self.db.rollback()

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The workforce member is already "
                        "assigned to this work order."
                    ),
                ) from exc

        refreshed = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order.id,
        )

        return self._build_response(
            refreshed
        )

    def remove_workforce(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        workforce_profile_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
    ) -> None:
        """
        Remove workforce and record the removal.
        """

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        assignment = (
            self.work_orders.get_workforce_assignment(
                work_order_id=work_order.id,
                workforce_profile_id=(
                    workforce_profile_id
                ),
            )
        )

        if assignment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Workforce assignment not found."
                ),
            )

        self.work_orders.remove_workforce_assignment(
            assignment
        )

        self._record_activity(
            organization_id=organization_id,
            work_order_id=work_order.id,
            actor_user_id=actor_user_id,
            activity_type="workforce_removed",
            summary=(
                "Workforce member removed "
                "from work order."
            ),
            details={
                "workforce_profile_id": str(
                    workforce_profile_id
                ),
            },
        )

    def assign_asset(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        asset_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderResponse:
        """
        Assign an asset and record the assignment.
        """

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        asset = (
            self.db.query(Asset)
            .filter(
                Asset.id == asset_id,
                Asset.organization_id
                == organization_id,
                Asset.is_active.is_(True),
            )
            .first()
        )

        if asset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active asset not found.",
            )

        if asset.status in {
            "unavailable",
            "retired",
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Unavailable or retired assets "
                    "cannot be assigned."
                ),
            )

        existing_assignment = (
            self.work_orders.get_asset_assignment(
                work_order_id=work_order.id,
                asset_id=asset.id,
            )
        )

        if existing_assignment is None:
            assignment = WorkOrderAssetAssignment(
                work_order_id=work_order.id,
                asset_id=asset.id,
            )

            try:
                self.work_orders.add_asset_assignment(
                    assignment
                )

                self._record_activity(
                    organization_id=organization_id,
                    work_order_id=work_order.id,
                    actor_user_id=actor_user_id,
                    activity_type="asset_assigned",
                    summary=(
                        "Asset assigned to work order."
                    ),
                    details={
                        "asset_id": str(asset.id),
                    },
                )

            except IntegrityError as exc:
                self.db.rollback()

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The asset is already assigned "
                        "to this work order."
                    ),
                ) from exc

        refreshed = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order.id,
        )

        return self._build_response(
            refreshed
        )

    def remove_asset(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        asset_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
    ) -> None:
        """
        Remove an asset and record the removal.
        """

        work_order = self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        assignment = (
            self.work_orders.get_asset_assignment(
                work_order_id=work_order.id,
                asset_id=asset_id,
            )
        )

        if assignment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asset assignment not found.",
            )

        self.work_orders.remove_asset_assignment(
            assignment
        )

        self._record_activity(
            organization_id=organization_id,
            work_order_id=work_order.id,
            actor_user_id=actor_user_id,
            activity_type="asset_removed",
            summary="Asset removed from work order.",
            details={
                "asset_id": str(asset_id),
            },
        )