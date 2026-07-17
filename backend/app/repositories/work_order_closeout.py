"""Work-order closeout repository."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.work_order_closeout import WorkOrderCloseout
from app.repositories.base import BaseRepository


class WorkOrderCloseoutRepository(
    BaseRepository[WorkOrderCloseout]
):
    """Repository for work-order closeout persistence."""

    def __init__(
        self,
        db: Session,
    ):
        super().__init__(
            db,
            WorkOrderCloseout,
        )

    def create_closeout(
        self,
        closeout: WorkOrderCloseout,
    ) -> WorkOrderCloseout:
        """Persist a closeout record."""

        return self.create(
            closeout
        )

    def update_closeout(
        self,
        closeout: WorkOrderCloseout,
    ) -> WorkOrderCloseout:
        """Persist closeout changes."""

        return self.update(
            closeout
        )

    def get_for_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> WorkOrderCloseout | None:
        """Retrieve the closeout for one work order."""

        query = self.db.query(WorkOrderCloseout).filter(
            WorkOrderCloseout.organization_id
            == organization_id,
            WorkOrderCloseout.work_order_id
            == work_order_id,
        )

        if for_update:
            query = query.with_for_update(
                of=WorkOrderCloseout
            )

        return query.first()
