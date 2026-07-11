"""
Role model.

Roles define what a user can do within an organization.
Permissions are assigned to roles.
Users receive roles through memberships.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel

if TYPE_CHECKING:
    from app.models.membership import Membership
    from app.models.permission import Permission


class Role(BaseModel):
    """
    Represents a platform role assignable through memberships.
    """

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        secondary="role_permissions",
        back_populates="roles",
        lazy="selectin",
    )

    memberships: Mapped[list["Membership"]] = relationship(
        "Membership",
        back_populates="role",
    )

    def __repr__(self) -> str:
        return f"<Role(name='{self.name}')>"