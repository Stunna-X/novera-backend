"""
Work-order repository.

Contains organization-scoped persistence operations for
work orders and assignments.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_
from sqlalchemy.orm import (
    Session,
    selectinload,
)

from app.models.work_order import (
    WorkOrder,
    WorkOrderAssetAssignment,
    WorkOrderWorkforceAssignment,
)
from app.repositories.base import BaseRepository


class WorkOrderRepository(
    BaseRepository[WorkOrder]
):
    """
    Repository for work-order operations.
    """

    def __init__(
        self,
        db: Session,
    ):
        super().__init__(
            db,
            WorkOrder,
        )

    @staticmethod
    def _assignment_options():
        return (
            selectinload(
                WorkOrder.workforce_assignments
            ),
            selectinload(
                WorkOrder.asset_assignments
            ),
        )

    def create_work_order(
        self,
        work_order: WorkOrder,
    ) -> WorkOrder:
        work_order.work_order_number = (
            work_order.work_order_number.strip().upper()
        )

        work_order.title = work_order.title.strip()

        return self.create(
            work_order
        )

    def get_for_organization(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrder | None:
        query = (
            self.db.query(WorkOrder)
            .options(
                *self._assignment_options()
            )
            .filter(
                WorkOrder.id == work_order_id,
                WorkOrder.organization_id
                == organization_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrder.is_active.is_(True)
            )

        return query.first()

    def list_for_organization(
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
    ) -> list[WorkOrder]:
        query = (
            self.db.query(WorkOrder)
            .options(
                *self._assignment_options()
            )
            .filter(
                WorkOrder.organization_id
                == organization_id
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrder.is_active.is_(True)
            )

        if status_filter:
            query = query.filter(
                WorkOrder.status == status_filter
            )

        if priority:
            query = query.filter(
                WorkOrder.priority == priority
            )

        if customer_id:
            query = query.filter(
                WorkOrder.customer_id == customer_id
            )

        if customer_site_id:
            query = query.filter(
                WorkOrder.customer_site_id
                == customer_site_id
            )

        normalized_search = (
            search.strip()
            if search
            else None
        )

        if normalized_search:
            pattern = f"%{normalized_search}%"

            query = query.filter(
                or_(
                    WorkOrder.work_order_number.ilike(
                        pattern
                    ),
                    WorkOrder.title.ilike(pattern),
                    WorkOrder.description.ilike(pattern),
                    WorkOrder.job_type.ilike(pattern),
                    WorkOrder.customer_reference.ilike(
                        pattern
                    ),
                )
            )

        return (
            query.order_by(
                WorkOrder.created_at.desc()
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None = None,
        status_filter: str | None = None,
        priority: str | None = None,
        customer_id: uuid.UUID | None = None,
        customer_site_id: uuid.UUID | None = None,
        include_inactive: bool = False,
    ) -> int:
        query = (
            self.db.query(
                func.count(WorkOrder.id)
            )
            .filter(
                WorkOrder.organization_id
                == organization_id
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrder.is_active.is_(True)
            )

        if status_filter:
            query = query.filter(
                WorkOrder.status == status_filter
            )

        if priority:
            query = query.filter(
                WorkOrder.priority == priority
            )

        if customer_id:
            query = query.filter(
                WorkOrder.customer_id == customer_id
            )

        if customer_site_id:
            query = query.filter(
                WorkOrder.customer_site_id
                == customer_site_id
            )

        normalized_search = (
            search.strip()
            if search
            else None
        )

        if normalized_search:
            pattern = f"%{normalized_search}%"

            query = query.filter(
                or_(
                    WorkOrder.work_order_number.ilike(
                        pattern
                    ),
                    WorkOrder.title.ilike(pattern),
                    WorkOrder.description.ilike(pattern),
                    WorkOrder.job_type.ilike(pattern),
                    WorkOrder.customer_reference.ilike(
                        pattern
                    ),
                )
            )

        return query.scalar() or 0

    def number_exists(
        self,
        organization_id: uuid.UUID,
        work_order_number: str,
        *,
        exclude_work_order_id: uuid.UUID | None = None,
    ) -> bool:
        normalized_number = (
            work_order_number.strip().lower()
        )

        query = self.db.query(
            WorkOrder.id
        ).filter(
            WorkOrder.organization_id
            == organization_id,
            func.lower(
                WorkOrder.work_order_number
            )
            == normalized_number,
        )

        if exclude_work_order_id:
            query = query.filter(
                WorkOrder.id
                != exclude_work_order_id
            )

        return query.first() is not None

    def update_work_order(
        self,
        work_order: WorkOrder,
    ) -> WorkOrder:
        work_order.work_order_number = (
            work_order.work_order_number.strip().upper()
        )

        work_order.title = work_order.title.strip()

        return self.update(
            work_order
        )

    def deactivate(
        self,
        work_order: WorkOrder,
    ) -> WorkOrder:
        work_order.is_active = False

        return self.update(
            work_order
        )

    def reactivate(
        self,
        work_order: WorkOrder,
    ) -> WorkOrder:
        work_order.is_active = True

        return self.update(
            work_order
        )

    def get_workforce_assignment(
        self,
        work_order_id: uuid.UUID,
        workforce_profile_id: uuid.UUID,
    ) -> WorkOrderWorkforceAssignment | None:
        return (
            self.db.query(
                WorkOrderWorkforceAssignment
            )
            .filter(
                WorkOrderWorkforceAssignment.work_order_id
                == work_order_id,
                WorkOrderWorkforceAssignment
                .workforce_profile_id
                == workforce_profile_id,
            )
            .first()
        )

    def add_workforce_assignment(
        self,
        assignment: WorkOrderWorkforceAssignment,
    ) -> WorkOrderWorkforceAssignment:
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)

        return assignment

    def remove_workforce_assignment(
        self,
        assignment: WorkOrderWorkforceAssignment,
    ) -> None:
        self.db.delete(assignment)
        self.db.commit()

    def get_asset_assignment(
        self,
        work_order_id: uuid.UUID,
        asset_id: uuid.UUID,
    ) -> WorkOrderAssetAssignment | None:
        return (
            self.db.query(
                WorkOrderAssetAssignment
            )
            .filter(
                WorkOrderAssetAssignment.work_order_id
                == work_order_id,
                WorkOrderAssetAssignment.asset_id
                == asset_id,
            )
            .first()
        )

    def add_asset_assignment(
        self,
        assignment: WorkOrderAssetAssignment,
    ) -> WorkOrderAssetAssignment:
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)

        return assignment

    def remove_asset_assignment(
        self,
        assignment: WorkOrderAssetAssignment,
    ) -> None:
        self.db.delete(assignment)
        self.db.commit()