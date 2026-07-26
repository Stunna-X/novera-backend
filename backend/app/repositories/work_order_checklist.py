"""
Work-order checklist repository.

Contains organization-scoped persistence operations for
work-order checklist items.
"""

from __future__ import annotations

import uuid

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.work_order import WorkOrder
from app.models.work_order_checklist import (
    WorkOrderChecklistItem,
)
from app.repositories.base import BaseRepository


class WorkOrderChecklistRepository(
    BaseRepository[WorkOrderChecklistItem]
):
    """
    Repository for work-order checklist-item operations.
    """

    def __init__(
        self,
        db: Session,
    ):
        super().__init__(
            db,
            WorkOrderChecklistItem,
        )

    def get_for_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrderChecklistItem | None:
        """
        Retrieve one organization-scoped checklist item.
        """

        query = (
            self.db.query(
                WorkOrderChecklistItem
            )
            .join(
                WorkOrder,
                WorkOrder.id
                == WorkOrderChecklistItem.work_order_id,
            )
            .filter(
                WorkOrder.organization_id
                == organization_id,
                WorkOrder.id == work_order_id,
                WorkOrderChecklistItem.id == item_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrder.is_active.is_(True),
                WorkOrderChecklistItem.is_active.is_(
                    True
                ),
            )

        return query.first()

    def list_for_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        include_inactive: bool = False,
    ) -> list[WorkOrderChecklistItem]:
        """
        List checklist items in execution order.
        """

        query = (
            self.db.query(
                WorkOrderChecklistItem
            )
            .join(
                WorkOrder,
                WorkOrder.id
                == WorkOrderChecklistItem.work_order_id,
            )
            .filter(
                WorkOrder.organization_id
                == organization_id,
                WorkOrder.id == work_order_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrder.is_active.is_(True),
                WorkOrderChecklistItem.is_active.is_(
                    True
                ),
            )

        return (
            query.order_by(
                WorkOrderChecklistItem.position.asc(),
                WorkOrderChecklistItem.created_at.asc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_all_for_work_order(
        self,
        work_order_id: uuid.UUID,
    ) -> list[WorkOrderChecklistItem]:
        """
        List active and inactive checklist items.

        This is used internally when positions must be
        reorganized without violating the uniqueness constraint.
        """

        return (
            self.db.query(
                WorkOrderChecklistItem
            )
            .filter(
                WorkOrderChecklistItem.work_order_id
                == work_order_id
            )
            .order_by(
                WorkOrderChecklistItem.position.asc(),
                WorkOrderChecklistItem.created_at.asc(),
            )
            .all()
        )

    def count_for_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> int:
        """
        Count checklist items for one work order.
        """

        query = (
            self.db.query(
                func.count(
                    WorkOrderChecklistItem.id
                )
            )
            .join(
                WorkOrder,
                WorkOrder.id
                == WorkOrderChecklistItem.work_order_id,
            )
            .filter(
                WorkOrder.organization_id
                == organization_id,
                WorkOrder.id == work_order_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrder.is_active.is_(True),
                WorkOrderChecklistItem.is_active.is_(
                    True
                ),
            )

        return query.scalar() or 0

    def get_next_position(
        self,
        work_order_id: uuid.UUID,
    ) -> int:
        """
        Return the next available checklist position.
        """

        highest_position = (
            self.db.query(
                func.max(
                    WorkOrderChecklistItem.position
                )
            )
            .filter(
                WorkOrderChecklistItem.work_order_id
                == work_order_id
            )
            .scalar()
        )

        if highest_position is None:
            return 0

        return highest_position + 1

    def position_exists(
        self,
        work_order_id: uuid.UUID,
        position: int,
        *,
        exclude_item_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Check whether a checklist position is already occupied.
        """

        query = (
            self.db.query(
                WorkOrderChecklistItem.id
            )
            .filter(
                WorkOrderChecklistItem.work_order_id
                == work_order_id,
                WorkOrderChecklistItem.position
                == position,
            )
        )

        if exclude_item_id:
            query = query.filter(
                WorkOrderChecklistItem.id
                != exclude_item_id
            )

        return query.first() is not None

    def create_item(
        self,
        item: WorkOrderChecklistItem,
    ) -> WorkOrderChecklistItem:
        """
        Persist a checklist item.
        """

        item.title = item.title.strip()

        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)

        return item

    def update_item(
        self,
        item: WorkOrderChecklistItem,
    ) -> WorkOrderChecklistItem:
        """
        Persist checklist-item changes.
        """

        item.title = item.title.strip()

        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)

        return item

    def deactivate_item(
        self,
        item: WorkOrderChecklistItem,
    ) -> WorkOrderChecklistItem:
        """
        Soft-delete a checklist item.
        """

        item.is_active = False

        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)

        return item

    def reactivate_item(
        self,
        item: WorkOrderChecklistItem,
    ) -> WorkOrderChecklistItem:
        """
        Reactivate a checklist item.
        """

        item.is_active = True

        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)

        return item

    def reorder_items(
        self,
        items: list[WorkOrderChecklistItem],
        ordered_item_ids: list[uuid.UUID],
    ) -> list[WorkOrderChecklistItem]:
        """
        Persist the requested active checklist ordering.

        Every row is first moved to a high, non-negative
        temporary position. This prevents uniqueness collisions
        while respecting the database constraint that positions
        cannot be negative.

        Inactive items are placed after active items so their
        stored positions cannot collide with the new ordering.
        """

        if not items:
            return []

        work_order_id = items[0].work_order_id

        all_items = self.list_all_for_work_order(
            work_order_id
        )

        item_by_id = {
            item.id: item
            for item in all_items
        }

        highest_position = max(
            (
                item.position
                for item in all_items
            ),
            default=-1,
        )

        temporary_start = (
            highest_position
            + len(all_items)
            + 1
        )

        for offset, item in enumerate(all_items):
            item.position = temporary_start + offset

        self.db.flush()

        for position, item_id in enumerate(
            ordered_item_ids
        ):
            item_by_id[item_id].position = position

        ordered_id_set = set(
            ordered_item_ids
        )

        remaining_items = [
            item
            for item in all_items
            if item.id not in ordered_id_set
        ]

        remaining_items.sort(
            key=lambda item: (
                item.position,
                item.created_at,
            )
        )

        next_position = len(
            ordered_item_ids
        )

        for item in remaining_items:
            item.position = next_position
            next_position += 1

        self.db.commit()

        reordered_items = [
            item_by_id[item_id]
            for item_id in ordered_item_ids
        ]

        for item in reordered_items:
            self.db.refresh(item)

        return reordered_items

    def get_progress_counts(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
    ) -> dict[str, int]:
        """
        Aggregate checklist progress for one work order.
        """

        row = (
            self.db.query(
                func.count(
                    WorkOrderChecklistItem.id
                ).label("total_items"),
                func.sum(
                    case(
                        (
                            WorkOrderChecklistItem.status
                            == "pending",
                            1,
                        ),
                        else_=0,
                    )
                ).label("pending_items"),
                func.sum(
                    case(
                        (
                            WorkOrderChecklistItem.status
                            == "completed",
                            1,
                        ),
                        else_=0,
                    )
                ).label("completed_items"),
                func.sum(
                    case(
                        (
                            WorkOrderChecklistItem.status
                            == "skipped",
                            1,
                        ),
                        else_=0,
                    )
                ).label("skipped_items"),
                func.sum(
                    case(
                        (
                            WorkOrderChecklistItem.is_required
                            .is_(True),
                            1,
                        ),
                        else_=0,
                    )
                ).label("required_items"),
                func.sum(
                    case(
                        (
                            (
                                WorkOrderChecklistItem
                                .is_required.is_(True)
                            )
                            & (
                                WorkOrderChecklistItem.status
                                == "completed"
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label(
                    "completed_required_items"
                ),
            )
            .join(
                WorkOrder,
                WorkOrder.id
                == WorkOrderChecklistItem.work_order_id,
            )
            .filter(
                WorkOrder.organization_id
                == organization_id,
                WorkOrder.id == work_order_id,
                WorkOrder.is_active.is_(True),
                WorkOrderChecklistItem.is_active.is_(
                    True
                ),
            )
            .one()
        )

        return {
            "total_items": row.total_items or 0,
            "pending_items": row.pending_items or 0,
            "completed_items": (
                row.completed_items or 0
            ),
            "skipped_items": row.skipped_items or 0,
            "required_items": row.required_items or 0,
            "completed_required_items": (
                row.completed_required_items or 0
            ),
        }