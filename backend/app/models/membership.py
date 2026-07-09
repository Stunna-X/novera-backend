"""
Membership model.

Links a user to an organization with a role.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class Membership(BaseModel):
    __tablename__ = "memberships"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_membership_org_user",
        ),
    )

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    role_id: Mapped[str] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
    )

    organization = relationship(
        "Organization",
        back_populates="memberships",
    )

    user = relationship(
        "User",
        back_populates="memberships",
    )

    role = relationship(
        "Role",
        back_populates="memberships",
    )