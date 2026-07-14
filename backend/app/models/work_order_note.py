"""
Work-order note models.

Stores operational notes, field updates, and attachment
metadata belonging to work orders.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import BaseModel
from app.enums.work_order_note import (
    WorkOrderNoteType,
    WorkOrderNoteVisibility,
)


if TYPE_CHECKING:
    from app.models.user import User
    from app.models.work_order import WorkOrder


class WorkOrderNote(BaseModel):
    """
    One operational note or field update on a work order.
    """

    __tablename__ = "work_order_notes"

    __table_args__ = (
        CheckConstraint(
            "note_type IN ('note', 'field_update')",
            name="ck_work_order_notes_type_valid",
        ),
        CheckConstraint(
            "visibility IN ('internal', 'customer')",
            name="ck_work_order_notes_visibility_valid",
        ),
        Index(
            "ix_work_order_notes_work_order_created",
            "work_order_id",
            "created_at",
        ),
        Index(
            "ix_work_order_notes_work_order_active",
            "work_order_id",
            "is_active",
        ),
        Index(
            "ix_work_order_notes_work_order_visibility",
            "work_order_id",
            "visibility",
        ),
    )

    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "work_orders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    note_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=WorkOrderNoteType.NOTE.value,
        server_default=WorkOrderNoteType.NOTE.value,
        index=True,
    )

    visibility: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=WorkOrderNoteVisibility.INTERNAL.value,
        server_default=WorkOrderNoteVisibility.INTERNAL.value,
        index=True,
    )

    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )

    edited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    work_order: Mapped["WorkOrder"] = relationship(
        "WorkOrder",
        back_populates="notes",
    )

    author: Mapped["User | None"] = relationship(
        "User",
        lazy="joined",
    )

    attachments: Mapped[
        list["WorkOrderNoteAttachment"]
    ] = relationship(
        "WorkOrderNoteAttachment",
        back_populates="note",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="WorkOrderNoteAttachment.position",
    )


class WorkOrderNoteAttachment(BaseModel):
    """
    Metadata describing a file attached to a work-order note.

    Actual binary files will live in object storage. This table
    stores only the information required to locate and display
    them.
    """

    __tablename__ = "work_order_note_attachments"

    __table_args__ = (
        CheckConstraint(
            "file_size_bytes >= 0",
            name="ck_work_order_note_attachments_size_non_negative",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_work_order_note_attachments_position_non_negative",
        ),
        Index(
            "ix_work_order_note_attachments_note_position",
            "note_id",
            "position",
        ),
    )

    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "work_order_notes.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
        index=True,
    )

    content_type: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    note: Mapped["WorkOrderNote"] = relationship(
        "WorkOrderNote",
        back_populates="attachments",
    )