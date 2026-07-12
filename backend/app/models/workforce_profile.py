"""
Workforce profile model.

Extends an organization membership with operational
employment and availability information.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
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
    Organization-scoped operational profile for a member.
    """

    __tablename__ = "workforce_profiles"

    __table_args__ = (
        UniqueConstraint(
            "membership_id",
            name="uq_workforce_profiles_membership",
        ),
        UniqueConstraint(
            "organization_id",
            "employee_code",
            name="uq_workforce_profiles_organization_employee_code",
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

    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "memberships.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    employee_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
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

    joined_on: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
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

    membership: Mapped["Membership"] = relationship(
        "Membership",
        lazy="joined",
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
    )

    def __repr__(self) -> str:
        """
        Return a developer-friendly representation.
        """

        return (
            f"<WorkforceProfile "
            f"id={self.id} "
            f"membership_id={self.membership_id} "
            f"organization_id={self.organization_id}>"
        )