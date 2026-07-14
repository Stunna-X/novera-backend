"""
Work-order note schemas.

Defines request and response payloads for operational notes,
field updates, and attachment metadata.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.enums.work_order_note import (
    WorkOrderNoteType,
    WorkOrderNoteVisibility,
)


class WorkOrderNoteAttachmentCreate(BaseModel):
    """
    Metadata for an attachment added to a work-order note.
    """

    file_name: str = Field(
        min_length=1,
        max_length=255,
    )

    storage_key: str = Field(
        min_length=1,
        max_length=500,
    )

    content_type: str = Field(
        min_length=1,
        max_length=150,
    )

    file_size_bytes: int = Field(
        ge=0,
    )

    position: int | None = Field(
        default=None,
        ge=0,
    )

    @field_validator(
        "file_name",
        "storage_key",
        "content_type",
    )
    @classmethod
    def normalize_required_text(
        cls,
        value: str,
    ) -> str:
        """
        Strip required attachment text fields.
        """

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Attachment values cannot be empty."
            )

        return normalized


class WorkOrderNoteCreate(BaseModel):
    """
    Payload for creating a work-order note.
    """

    note_type: WorkOrderNoteType = (
        WorkOrderNoteType.NOTE
    )

    visibility: WorkOrderNoteVisibility = (
        WorkOrderNoteVisibility.INTERNAL
    )

    body: str = Field(
        min_length=1,
        max_length=20_000,
    )

    is_pinned: bool = False

    attachments: list[
        WorkOrderNoteAttachmentCreate
    ] = Field(
        default_factory=list,
        max_length=20,
    )

    @field_validator("body")
    @classmethod
    def normalize_body(
        cls,
        value: str,
    ) -> str:
        """
        Strip surrounding whitespace from the note body.
        """

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Note body cannot be empty."
            )

        return normalized

    @model_validator(mode="after")
    def validate_attachments(
        self,
    ) -> "WorkOrderNoteCreate":
        """
        Reject duplicate storage keys and explicit positions.
        """

        storage_keys = [
            attachment.storage_key
            for attachment in self.attachments
        ]

        if len(storage_keys) != len(
            set(storage_keys)
        ):
            raise ValueError(
                "Attachment storage keys must be unique."
            )

        explicit_positions = [
            attachment.position
            for attachment in self.attachments
            if attachment.position is not None
        ]

        if len(explicit_positions) != len(
            set(explicit_positions)
        ):
            raise ValueError(
                "Explicit attachment positions must be unique."
            )

        return self


class WorkOrderNoteUpdate(BaseModel):
    """
    Payload for editing a work-order note.
    """

    note_type: WorkOrderNoteType | None = None

    visibility: WorkOrderNoteVisibility | None = None

    body: str | None = Field(
        default=None,
        min_length=1,
        max_length=20_000,
    )

    is_pinned: bool | None = None

    @field_validator("body")
    @classmethod
    def normalize_body(
        cls,
        value: str | None,
    ) -> str | None:
        """
        Normalize an optional note body.
        """

        if value is None:
            return None

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Note body cannot be empty."
            )

        return normalized


class WorkOrderNoteAttachmentResponse(BaseModel):
    """
    Attachment metadata returned by the API.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    note_id: uuid.UUID

    file_name: str
    storage_key: str
    content_type: str
    file_size_bytes: int
    position: int

    created_at: datetime
    updated_at: datetime


class WorkOrderNoteResponse(BaseModel):
    """
    One work-order note returned by the API.
    """

    id: uuid.UUID
    work_order_id: uuid.UUID

    author_user_id: uuid.UUID | None
    author_first_name: str | None
    author_last_name: str | None
    author_email: str | None

    note_type: WorkOrderNoteType
    visibility: WorkOrderNoteVisibility

    body: str
    is_pinned: bool
    edited_at: datetime | None
    is_active: bool

    attachments: list[
        WorkOrderNoteAttachmentResponse
    ] = Field(
        default_factory=list,
    )

    created_at: datetime
    updated_at: datetime


class WorkOrderNoteListResponse(BaseModel):
    """
    Paginated work-order note collection.
    """

    items: list[WorkOrderNoteResponse] = Field(
        default_factory=list,
    )

    total: int = Field(
        ge=0,
    )

    skip: int = Field(
        ge=0,
    )

    limit: int = Field(
        ge=1,
    )