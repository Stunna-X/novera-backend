"""
Workforce profile model.

Represents a standalone, organization-level employee.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import BaseModel


if TYPE_CHECKING:
    from app.models.organization import Organization


class WorkforceProfile(BaseModel):
    """
    Organization-scoped operational employee profile.
    """

    __tablename__ = "workforce_profiles"

    __table_args__ = (
        Index(
            "ix_workforce_profiles_organization_status",
            "organization_id",
            "status",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    job_title: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    employment_type: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
    )

    def __repr__(self) -> str:
        return (
            f"<WorkforceProfile "
            f"id={self.id} "
            f"full_name={self.full_name!r} "
            f"organization_id={self.organization_id}>"
        )
