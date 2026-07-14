"""
Work-order note repository.

Contains organization-scoped persistence operations for
work-order notes and attachment metadata.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func
from sqlalchemy.orm import (
    Session,
    joinedload,
    selectinload,
)

from app.models.work_order import WorkOrder
from app.models.work_order_note import (
    WorkOrderNote,
    WorkOrderNoteAttachment,
)
from app.repositories.base import BaseRepository


class WorkOrderNoteRepository(
    BaseRepository[WorkOrderNote]
):
    """
    Repository for work-order note operations.
    """

    def __init__(
        self,
        db: Session,
    ):
        super().__init__(
            db,
            WorkOrderNote,
        )

    @staticmethod
    def _response_options():
        """
        Return eager-loading options for note responses.
        """

        return (
            joinedload(
                WorkOrderNote.author
            ),
            selectinload(
                WorkOrderNote.attachments
            ),
        )

    def get_for_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        note_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrderNote | None:
        """
        Retrieve one organization-scoped work-order note.
        """

        query = (
            self.db.query(WorkOrderNote)
            .options(
                *self._response_options()
            )
            .populate_existing()
            .join(
                WorkOrder,
                WorkOrder.id
                == WorkOrderNote.work_order_id,
            )
            .filter(
                WorkOrder.organization_id
                == organization_id,
                WorkOrder.id == work_order_id,
                WorkOrderNote.id == note_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkOrder.is_active.is_(True),
                WorkOrderNote.is_active.is_(True),
            )

        return query.first()

    def list_for_work_order(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        note_type: str | None = None,
        visibility: str | None = None,
        is_pinned: bool | None = None,
        include_inactive: bool = False,
    ) -> list[WorkOrderNote]:
        """
        List work-order notes with pinned notes first.
        """

        query = (
            self.db.query(WorkOrderNote)
            .options(
                *self._response_options()
            )
            .populate_existing()
            .join(
                WorkOrder,
                WorkOrder.id
                == WorkOrderNote.work_order_id,
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
                WorkOrderNote.is_active.is_(True),
            )

        if note_type is not None:
            query = query.filter(
                WorkOrderNote.note_type
                == note_type
            )

        if visibility is not None:
            query = query.filter(
                WorkOrderNote.visibility
                == visibility
            )

        if is_pinned is not None:
            query = query.filter(
                WorkOrderNote.is_pinned
                == is_pinned
            )

        return (
            query.order_by(
                WorkOrderNote.is_pinned.desc(),
                WorkOrderNote.created_at.desc(),
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
        note_type: str | None = None,
        visibility: str | None = None,
        is_pinned: bool | None = None,
        include_inactive: bool = False,
    ) -> int:
        """
        Count notes belonging to one work order.
        """

        query = (
            self.db.query(
                func.count(
                    WorkOrderNote.id
                )
            )
            .join(
                WorkOrder,
                WorkOrder.id
                == WorkOrderNote.work_order_id,
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
                WorkOrderNote.is_active.is_(True),
            )

        if note_type is not None:
            query = query.filter(
                WorkOrderNote.note_type
                == note_type
            )

        if visibility is not None:
            query = query.filter(
                WorkOrderNote.visibility
                == visibility
            )

        if is_pinned is not None:
            query = query.filter(
                WorkOrderNote.is_pinned
                == is_pinned
            )

        return query.scalar() or 0

    def create_note(
        self,
        note: WorkOrderNote,
    ) -> WorkOrderNote:
        """
        Persist a work-order note and its attachments.
        """

        note.body = note.body.strip()

        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)

        return note

    def update_note(
        self,
        note: WorkOrderNote,
    ) -> WorkOrderNote:
        """
        Persist work-order note changes.
        """

        note.body = note.body.strip()

        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)

        return note

    def deactivate_note(
        self,
        note: WorkOrderNote,
    ) -> WorkOrderNote:
        """
        Soft-delete a work-order note.
        """

        note.is_active = False

        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)

        return note

    def reactivate_note(
        self,
        note: WorkOrderNote,
    ) -> WorkOrderNote:
        """
        Reactivate a soft-deleted work-order note.
        """

        note.is_active = True

        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)

        return note

    def storage_key_exists(
        self,
        storage_key: str,
        *,
        exclude_attachment_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Check attachment storage-key uniqueness.
        """

        query = (
            self.db.query(
                WorkOrderNoteAttachment.id
            )
            .filter(
                WorkOrderNoteAttachment.storage_key
                == storage_key.strip()
            )
        )

        if exclude_attachment_id is not None:
            query = query.filter(
                WorkOrderNoteAttachment.id
                != exclude_attachment_id
            )

        return query.first() is not None

    def get_next_attachment_position(
        self,
        note_id: uuid.UUID,
    ) -> int:
        """
        Return the next attachment position for a note.
        """

        highest_position = (
            self.db.query(
                func.max(
                    WorkOrderNoteAttachment.position
                )
            )
            .filter(
                WorkOrderNoteAttachment.note_id
                == note_id
            )
            .scalar()
        )

        if highest_position is None:
            return 0

        return highest_position + 1

    def get_attachment_for_note(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        note_id: uuid.UUID,
        attachment_id: uuid.UUID,
    ) -> WorkOrderNoteAttachment | None:
        """
        Retrieve one organization-scoped note attachment.
        """

        return (
            self.db.query(
                WorkOrderNoteAttachment
            )
            .join(
                WorkOrderNote,
                WorkOrderNote.id
                == WorkOrderNoteAttachment.note_id,
            )
            .join(
                WorkOrder,
                WorkOrder.id
                == WorkOrderNote.work_order_id,
            )
            .filter(
                WorkOrder.organization_id
                == organization_id,
                WorkOrder.id == work_order_id,
                WorkOrderNote.id == note_id,
                WorkOrderNoteAttachment.id
                == attachment_id,
            )
            .first()
        )

    def add_attachment(
        self,
        attachment: WorkOrderNoteAttachment,
    ) -> WorkOrderNoteAttachment:
        """
        Persist attachment metadata.
        """

        attachment.file_name = (
            attachment.file_name.strip()
        )

        attachment.storage_key = (
            attachment.storage_key.strip()
        )

        attachment.content_type = (
            attachment.content_type.strip()
        )

        self.db.add(attachment)
        self.db.commit()
        self.db.refresh(attachment)

        return attachment

    def remove_attachment(
        self,
        attachment: WorkOrderNoteAttachment,
    ) -> None:
        """
        Delete attachment metadata.
        """

        self.db.delete(attachment)
        self.db.commit()