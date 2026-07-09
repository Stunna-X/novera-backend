"""
Organization model.

An organization represents a company (tenant) using Novera.
Every business resource in the platform belongs to an organization.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel
from app.enums.industry import Industry


class Organization(BaseModel):
    """
    Represents a tenant (company) within the Novera platform.
    """

    __tablename__ = "organizations"

    __table_args__ = (
        Index("ix_organizations_name", "name"),
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    industry: Mapped[Industry | None] = mapped_column(
        Enum(Industry, name="industry_enum"),
        nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    country: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    timezone: Mapped[str] = mapped_column(
        String(100),
        default="UTC",
        nullable=False,
    )

    logo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    memberships = relationship(
        "Membership",
        back_populates="organization",
        cascade="all, delete-orphan",
    )