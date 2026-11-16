"""
Workforce profile model.

Represents an organization-level employee who may optionally
be linked to a Novera organization membership.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import BaseModel


if TYPE_CHECKING:
    from app.models.membership import Membership
    from app.models.organization import Organization


class WorkforceProfile(BaseModel):
    """
    Organization-scoped operational employee profile.
    """

    __tablename__ = "workforce_profiles"

    __table_args__ = (
        UniqueConstraint(
            "membership_id",
            name="uq_workforce_profiles_membership",
        ),
        Index(
            "ix_workforce_profiles_organization_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_workforce_profiles_organization_available",
            "organization_id",
            "is_available",
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

    membership_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "memberships.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
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

    emergency_contact_name: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )

    emergency_contact_phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    skills: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        index=True,
    )

    is_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    membership: Mapped["Membership | None"] = relationship(
        "Membership",
        lazy="joined",
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
