"""
Work-order note service.

Contains validation, author attribution, visibility filtering,
attachment metadata management, soft deletion, restoration,
and activity-timeline recording for work-order notes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.enums.work_order_note import (
    WorkOrderNoteType,
    WorkOrderNoteVisibility,
)
from app.models.work_order import WorkOrder
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_note import (
    WorkOrderNote,
    WorkOrderNoteAttachment,
)
from app.repositories.work_order import WorkOrderRepository
from app.repositories.work_order_activity import (
    WorkOrderActivityRepository,
)
from app.repositories.work_order_note import (
    WorkOrderNoteRepository,
)
from app.schemas.work_order_note import (
    WorkOrderNoteAttachmentCreate,
    WorkOrderNoteAttachmentResponse,
    WorkOrderNoteCreate,
    WorkOrderNoteListResponse,
    WorkOrderNoteResponse,
    WorkOrderNoteUpdate,
)


class WorkOrderNoteService:
    """
    Handles work-order note and attachment business logic.
    """

    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.work_orders = WorkOrderRepository(db)
        self.notes = WorkOrderNoteRepository(db)
        self.activities = WorkOrderActivityRepository(db)

    @staticmethod
    def _build_attachment_response(
        attachment: WorkOrderNoteAttachment,
    ) -> WorkOrderNoteAttachmentResponse:
        """
        Convert attachment metadata into an API response.
        """

        return WorkOrderNoteAttachmentResponse(
            id=attachment.id,
            note_id=attachment.note_id,
            file_name=attachment.file_name,
            storage_key=attachment.storage_key,
            content_type=attachment.content_type,
            file_size_bytes=attachment.file_size_bytes,
            position=attachment.position,
            created_at=attachment.created_at,
            updated_at=attachment.updated_at,
        )

    @classmethod
    def _build_response(
        cls,
        note: WorkOrderNote,
    ) -> WorkOrderNoteResponse:
        """
        Convert a note model into an API response.
        """

        author = note.author

        return WorkOrderNoteResponse(
            id=note.id,
            work_order_id=note.work_order_id,
            author_user_id=note.author_user_id,
            author_first_name=(
                author.first_name
                if author is not None
                else None
            ),
            author_last_name=(
                author.last_name
                if author is not None
                else None
            ),
            author_email=(
                author.email
                if author is not None
                else None
            ),
            note_type=note.note_type,
            visibility=note.visibility,
            body=note.body,
            is_pinned=note.is_pinned,
            edited_at=note.edited_at,
            is_active=note.is_active,
            attachments=[
                cls._build_attachment_response(
                    attachment
                )
                for attachment in note.attachments
            ],
            created_at=note.created_at,
            updated_at=note.updated_at,
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
        Record one immutable note-related activity.
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
        Retrieve an organization-scoped work order.
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

    def _get_note_or_404(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        note_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrderNote:
        """
        Retrieve an organization-scoped work-order note.
        """

        note = self.notes.get_for_work_order(
            organization_id=organization_id,
            work_order_id=work_order_id,
            note_id=note_id,
            include_inactive=include_inactive,
        )

        if note is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work-order note not found.",
            )

        return note

    def _reload_note(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        note_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrderNote:
        """
        Reload a note with its author and attachments.
        """

        return self._get_note_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            note_id=note_id,
            include_inactive=include_inactive,
        )

    def _ensure_storage_keys_available(
        self,
        attachments: list[
            WorkOrderNoteAttachmentCreate
        ],
    ) -> None:
        """
        Ensure all attachment storage keys are available.
        """

        for attachment in attachments:
            if self.notes.storage_key_exists(
                attachment.storage_key
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "An attachment already uses "
                        f"storage key "
                        f"'{attachment.storage_key}'."
                    ),
                )

    @staticmethod
    def _build_attachments(
        attachments: list[
            WorkOrderNoteAttachmentCreate
        ],
    ) -> list[WorkOrderNoteAttachment]:
        """
        Build attachment models with unique positions.
        """

        used_positions = {
            attachment.position
            for attachment in attachments
            if attachment.position is not None
        }

        next_position = 0
        attachment_models: list[
            WorkOrderNoteAttachment
        ] = []

        for attachment in attachments:
            position = attachment.position

            if position is None:
                while next_position in used_positions:
                    next_position += 1

                position = next_position
                used_positions.add(position)
                next_position += 1

            attachment_models.append(
                WorkOrderNoteAttachment(
                    file_name=attachment.file_name,
                    storage_key=attachment.storage_key,
                    content_type=attachment.content_type,
                    file_size_bytes=(
                        attachment.file_size_bytes
                    ),
                    position=position,
                )
            )

        return attachment_models

    def _attachment_position_exists(
        self,
        note_id: uuid.UUID,
        position: int,
    ) -> bool:
        """
        Check whether a note attachment position is occupied.
        """

        return (
            self.db.query(
                WorkOrderNoteAttachment.id
            )
            .filter(
                WorkOrderNoteAttachment.note_id
                == note_id,
                WorkOrderNoteAttachment.position
                == position,
            )
            .first()
            is not None
        )

    def create_note(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        payload: WorkOrderNoteCreate,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderNoteResponse:
        """
        Create a work-order note and attachment metadata.
        """

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        self._ensure_storage_keys_available(
            payload.attachments
        )

        note = WorkOrderNote(
            work_order_id=work_order_id,
            author_user_id=actor_user_id,
            note_type=payload.note_type.value,
            visibility=payload.visibility.value,
            body=payload.body,
            is_pinned=payload.is_pinned,
        )

        note.attachments = self._build_attachments(
            payload.attachments
        )

        try:
            created = self.notes.create_note(
                note
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                activity_type="work_order_note_created",
                summary=(
                    "Work-order note created."
                    if created.note_type == "note"
                    else "Work-order field update created."
                ),
                details={
                    "note_id": str(created.id),
                    "note_type": created.note_type,
                    "visibility": created.visibility,
                    "is_pinned": created.is_pinned,
                    "attachment_count": len(
                        payload.attachments
                    ),
                    "body_preview": (
                        created.body[:120]
                    ),
                },
            )

            loaded = self._reload_note(
                organization_id=organization_id,
                work_order_id=work_order_id,
                note_id=created.id,
            )

            return self._build_response(
                loaded
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The work-order note or one of its "
                    "attachments conflicts with an "
                    "existing record."
                ),
            ) from exc

    def list_notes(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        note_type: WorkOrderNoteType | None = None,
        visibility: WorkOrderNoteVisibility | None = None,
        is_pinned: bool | None = None,
        include_inactive: bool = False,
    ) -> WorkOrderNoteListResponse:
        """
        List work-order notes with optional filters.
        """

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            include_inactive=include_inactive,
        )

        note_type_value = (
            note_type.value
            if note_type is not None
            else None
        )

        visibility_value = (
            visibility.value
            if visibility is not None
            else None
        )

        notes = self.notes.list_for_work_order(
            organization_id=organization_id,
            work_order_id=work_order_id,
            skip=skip,
            limit=limit,
            note_type=note_type_value,
            visibility=visibility_value,
            is_pinned=is_pinned,
            include_inactive=include_inactive,
        )

        total = self.notes.count_for_work_order(
            organization_id=organization_id,
            work_order_id=work_order_id,
            note_type=note_type_value,
            visibility=visibility_value,
            is_pinned=is_pinned,
            include_inactive=include_inactive,
        )

        return WorkOrderNoteListResponse(
            items=[
                self._build_response(note)
                for note in notes
            ],
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_note(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        note_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkOrderNoteResponse:
        """
        Return one work-order note.
        """

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            include_inactive=include_inactive,
        )

        note = self._get_note_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            note_id=note_id,
            include_inactive=include_inactive,
        )

        return self._build_response(
            note
        )

    def update_note(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        note_id: uuid.UUID,
        payload: WorkOrderNoteUpdate,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderNoteResponse:
        """
        Edit a work-order note.
        """

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        note = self._get_note_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            note_id=note_id,
        )

        update_data = payload.model_dump(
            exclude_unset=True
        )

        if not update_data:
            return self._build_response(
                note
            )

        non_nullable_fields = {
            "note_type",
            "visibility",
            "body",
            "is_pinned",
        }

        for field_name in non_nullable_fields:
            if (
                field_name in update_data
                and update_data[field_name] is None
            ):
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail=(
                        f"{field_name.replace('_', ' ').title()} "
                        "cannot be null."
                    ),
                )

        changed_fields = sorted(
            update_data.keys()
        )

        for field_name, field_value in update_data.items():
            if isinstance(
                field_value,
                (
                    WorkOrderNoteType,
                    WorkOrderNoteVisibility,
                ),
            ):
                field_value = field_value.value

            setattr(
                note,
                field_name,
                field_value,
            )

        note.edited_at = datetime.now(
            timezone.utc
        )

        try:
            updated = self.notes.update_note(
                note
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                activity_type="work_order_note_updated",
                summary="Work-order note updated.",
                details={
                    "note_id": str(updated.id),
                    "note_type": updated.note_type,
                    "visibility": updated.visibility,
                    "is_pinned": updated.is_pinned,
                    "changed_fields": changed_fields,
                },
            )

            loaded = self._reload_note(
                organization_id=organization_id,
                work_order_id=work_order_id,
                note_id=updated.id,
            )

            return self._build_response(
                loaded
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The work-order note update "
                    "could not be saved."
                ),
            ) from exc

    def deactivate_note(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        note_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
    ) -> None:
        """
        Soft-delete a work-order note.
        """

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        note = self._get_note_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            note_id=note_id,
        )

        self.notes.deactivate_note(
            note
        )

        self._record_activity(
            organization_id=organization_id,
            work_order_id=work_order_id,
            actor_user_id=actor_user_id,
            activity_type="work_order_note_deactivated",
            summary="Work-order note deactivated.",
            details={
                "note_id": str(note.id),
                "note_type": note.note_type,
                "visibility": note.visibility,
            },
        )

    def reactivate_note(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        note_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderNoteResponse:
        """
        Reactivate a soft-deleted work-order note.
        """

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        note = self._get_note_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            note_id=note_id,
            include_inactive=True,
        )

        if not note.is_active:
            note = self.notes.reactivate_note(
                note
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                activity_type=(
                    "work_order_note_reactivated"
                ),
                summary="Work-order note reactivated.",
                details={
                    "note_id": str(note.id),
                    "note_type": note.note_type,
                    "visibility": note.visibility,
                },
            )

        loaded = self._reload_note(
            organization_id=organization_id,
            work_order_id=work_order_id,
            note_id=note.id,
            include_inactive=True,
        )

        return self._build_response(
            loaded
        )

    def add_attachment(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        note_id: uuid.UUID,
        payload: WorkOrderNoteAttachmentCreate,
        *,
        actor_user_id: uuid.UUID,
    ) -> WorkOrderNoteResponse:
        """
        Add attachment metadata to an existing note.
        """

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        note = self._get_note_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            note_id=note_id,
        )

        if self.notes.storage_key_exists(
            payload.storage_key
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "An attachment already uses "
                    f"storage key "
                    f"'{payload.storage_key}'."
                ),
            )

        position = payload.position

        if position is None:
            position = (
                self.notes.get_next_attachment_position(
                    note.id
                )
            )

        elif self._attachment_position_exists(
            note_id=note.id,
            position=position,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another attachment already "
                    "occupies this position."
                ),
            )

        attachment = WorkOrderNoteAttachment(
            note_id=note.id,
            file_name=payload.file_name,
            storage_key=payload.storage_key,
            content_type=payload.content_type,
            file_size_bytes=payload.file_size_bytes,
            position=position,
        )

        try:
            created = self.notes.add_attachment(
                attachment
            )

            self._record_activity(
                organization_id=organization_id,
                work_order_id=work_order_id,
                actor_user_id=actor_user_id,
                activity_type=(
                    "work_order_note_attachment_added"
                ),
                summary=(
                    "Attachment added to work-order note."
                ),
                details={
                    "note_id": str(note.id),
                    "attachment_id": str(created.id),
                    "file_name": created.file_name,
                    "content_type": created.content_type,
                    "file_size_bytes": (
                        created.file_size_bytes
                    ),
                    "position": created.position,
                },
            )

            loaded = self._reload_note(
                organization_id=organization_id,
                work_order_id=work_order_id,
                note_id=note.id,
            )

            return self._build_response(
                loaded
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The attachment metadata conflicts "
                    "with an existing record."
                ),
            ) from exc

    def remove_attachment(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        note_id: uuid.UUID,
        attachment_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
    ) -> None:
        """
        Remove attachment metadata from a note.
        """

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
        )

        self._get_note_or_404(
            organization_id=organization_id,
            work_order_id=work_order_id,
            note_id=note_id,
        )

        attachment = (
            self.notes.get_attachment_for_note(
                organization_id=organization_id,
                work_order_id=work_order_id,
                note_id=note_id,
                attachment_id=attachment_id,
            )
        )

        if attachment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Note attachment not found.",
            )

        attachment_details = {
            "note_id": str(note_id),
            "attachment_id": str(attachment.id),
            "file_name": attachment.file_name,
            "storage_key": attachment.storage_key,
            "content_type": attachment.content_type,
            "file_size_bytes": (
                attachment.file_size_bytes
            ),
            "position": attachment.position,
        }

        self.notes.remove_attachment(
            attachment
        )

        self._record_activity(
            organization_id=organization_id,
            work_order_id=work_order_id,
            actor_user_id=actor_user_id,
            activity_type=(
                "work_order_note_attachment_removed"
            ),
            summary=(
                "Attachment removed from work-order note."
            ),
            details=attachment_details,
        )