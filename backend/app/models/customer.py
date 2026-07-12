"""
Customer model.

Stores organization-scoped customer records used by
field operations, jobs, projects, invoices, and reporting.
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


class Customer(BaseModel):
    """
    Customer belonging to one Novera organization.

    Customers are isolated by organization so that records
    cannot be shared across separate company workspaces.
    """

    __tablename__ = "customers"

    __table_args__ = (
        Index(
            "ix_customers_organization_name",
            "organization_id",
            "name",
        ),
        Index(
            "ix_customers_organization_active",
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

    name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    customer_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="business",
    )

    contact_name: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
        index=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    alternate_phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    address_line_1: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    address_line_2: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    state: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    postal_code: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    country: Mapped[str | None] = mapped_column(
        String(100),
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
        lazy="joined",
    )

    def __repr__(self) -> str:
        """
        Return a developer-friendly customer representation.
        """

        return (
            f"<Customer "
            f"id={self.id} "
            f"name={self.name!r} "
            f"organization_id={self.organization_id}>"
        )