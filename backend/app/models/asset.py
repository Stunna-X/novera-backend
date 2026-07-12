"""
Asset model.

Stores organization-scoped equipment, vehicles, machinery,
tools, and other operational assets.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
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


class Asset(BaseModel):
    """
    Operational asset belonging to one organization.

    Each asset is isolated by organization and identified using
    an organization-specific asset code.
    """

    __tablename__ = "assets"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "asset_code",
            name="uq_assets_organization_asset_code",
        ),
        UniqueConstraint(
            "organization_id",
            "serial_number",
            name="uq_assets_organization_serial_number",
        ),
        Index(
            "ix_assets_organization_name",
            "organization_id",
            "name",
        ),
        Index(
            "ix_assets_organization_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_assets_organization_type",
            "organization_id",
            "asset_type",
        ),
        Index(
            "ix_assets_organization_active",
            "organization_id",
            "is_active",
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

    asset_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    asset_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="equipment",
    )

    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    manufacturer: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    model_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    serial_number: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    registration_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    year_of_manufacture: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    purchase_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    purchase_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="available",
        index=True,
    )

    condition: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="good",
    )

    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    last_service_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    next_service_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
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

    organization: Mapped["Organization"] = relationship(
        "Organization",
    )

    def __repr__(self) -> str:
        """
        Return a developer-friendly representation.
        """

        return (
            f"<Asset "
            f"id={self.id} "
            f"asset_code={self.asset_code!r} "
            f"name={self.name!r} "
            f"organization_id={self.organization_id}>"
        )