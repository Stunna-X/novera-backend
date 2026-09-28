"""
Persistence operations for work-order material shortage allowances.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models.work_order_material_shortage_allowance import (
    WorkOrderMaterialShortageAllowance,
)
from app.repositories.base import BaseRepository


class WorkOrderMaterialShortageAllowanceRepository(
    BaseRepository[WorkOrderMaterialShortageAllowance]
):
    """Repository for work-order material shortage allowance records."""

    def __init__(self, db: Session) -> None:
        super().__init__(
            db,
            WorkOrderMaterialShortageAllowance,
        )

    def _response_options(self) -> tuple[Any, ...]:
        """
        Eager-load relationships needed by allowance responses.

        The allowance model already uses joined loading for these
        relationships. Explicit options here keep repository queries
        predictable and make the intended response graph obvious.
        """
        return (
            joinedload(
                WorkOrderMaterialShortageAllowance.work_order_material_requirement
            ),
            joinedload(WorkOrderMaterialShortageAllowance.created_by),
            joinedload(WorkOrderMaterialShortageAllowance.submitted_by),
            joinedload(WorkOrderMaterialShortageAllowance.approved_by),
            joinedload(WorkOrderMaterialShortageAllowance.rejected_by),
            joinedload(WorkOrderMaterialShortageAllowance.cancelled_by),
        )

    def create(
        self,
        allowance: WorkOrderMaterialShortageAllowance,
    ) -> WorkOrderMaterialShortageAllowance:
        """
        Add an allowance and flush without committing.

        The service records the corresponding work-order activity in
        the same transaction. The activity repository performs the
        final commit.
        """
        self.db.add(allowance)
        self.db.flush()
        return allowance

    def update(
        self,
        allowance: WorkOrderMaterialShortageAllowance,
    ) -> WorkOrderMaterialShortageAllowance:
        """
        Flush an existing allowance without committing.
        """
        self.db.add(allowance)
        self.db.flush()
        return allowance

    def get_for_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        allowance_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> WorkOrderMaterialShortageAllowance | None:
        """
        Get one allowance scoped to an organization and work order.
        """
        query = (
            self.db.query(WorkOrderMaterialShortageAllowance)
            .options(*self._response_options())
            .filter(
                WorkOrderMaterialShortageAllowance.id == allowance_id,
                WorkOrderMaterialShortageAllowance.organization_id
                == organization_id,
                WorkOrderMaterialShortageAllowance.work_order_id
                == work_order_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrderMaterialShortageAllowance.is_active.is_(True)
            )

        if for_update:
            query = query.with_for_update(
                of=WorkOrderMaterialShortageAllowance
            )

        return query.first()

    def get_for_requirement(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        requirement_id: uuid.UUID,
        *,
        include_inactive: bool = True,
        for_update: bool = False,
    ) -> WorkOrderMaterialShortageAllowance | None:
        """
        Get the allowance associated with one material requirement.
        """
        query = (
            self.db.query(WorkOrderMaterialShortageAllowance)
            .options(*self._response_options())
            .filter(
                WorkOrderMaterialShortageAllowance.organization_id
                == organization_id,
                WorkOrderMaterialShortageAllowance.work_order_id
                == work_order_id,
                WorkOrderMaterialShortageAllowance.work_order_material_requirement_id
                == requirement_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrderMaterialShortageAllowance.is_active.is_(True)
            )

        if for_update:
            query = query.with_for_update(
                of=WorkOrderMaterialShortageAllowance
            )

        return query.first()

    def list_for_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        allowance_status: str | None = None,
        include_inactive: bool = False,
    ) -> list[WorkOrderMaterialShortageAllowance]:
        """
        List allowances belonging to a work order.
        """
        query = (
            self.db.query(WorkOrderMaterialShortageAllowance)
            .options(*self._response_options())
            .filter(
                WorkOrderMaterialShortageAllowance.organization_id
                == organization_id,
                WorkOrderMaterialShortageAllowance.work_order_id
                == work_order_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrderMaterialShortageAllowance.is_active.is_(True)
            )

        if allowance_status is not None:
            query = query.filter(
                WorkOrderMaterialShortageAllowance.status
                == allowance_status
            )

        return (
            query.order_by(
                WorkOrderMaterialShortageAllowance.created_at.desc()
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
        allowance_status: str | None = None,
        include_inactive: bool = False,
    ) -> int:
        """
        Count allowances belonging to a work order.
        """
        query = self.db.query(
            WorkOrderMaterialShortageAllowance.id
        ).filter(
            WorkOrderMaterialShortageAllowance.organization_id
            == organization_id,
            WorkOrderMaterialShortageAllowance.work_order_id
            == work_order_id,
        )

        if not include_inactive:
            query = query.filter(
                WorkOrderMaterialShortageAllowance.is_active.is_(True)
            )

        if allowance_status is not None:
            query = query.filter(
                WorkOrderMaterialShortageAllowance.status
                == allowance_status
            )

        return query.count()