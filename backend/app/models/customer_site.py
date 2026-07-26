"""
Customer site model.

Stores physical service and operational locations belonging
to organization customers.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
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
    from app.models.customer import Customer
    from app.models.organization import Organization


class CustomerSite(BaseModel):
    """
    Physical operational location belonging to a customer.

    Customer sites are scoped to an organization and customer
    to preserve tenant isolation.
    """

    __tablename__ = "customer_sites"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "site_code",
            name="uq_customer_sites_organization_site_code",
        ),
        Index(
            "ix_customer_sites_customer_name",
            "customer_id",
            "name",
        ),
        Index(
            "ix_customer_sites_organization_active",
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

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "customers.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    site_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    site_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    contact_name: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    address_line_1: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
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

    latitude: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=9,
            scale=6,
        ),
        nullable=True,
    )

    longitude: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=10,
            scale=6,
        ),
        nullable=True,
    )

    access_instructions: Mapped[str | None] = mapped_column(
        Text,
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

    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="sites",
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
    )

    def __repr__(self) -> str:
        """
        Return a developer-friendly customer-site representation.
        """

        return (
            f"<CustomerSite "
            f"id={self.id} "
            f"name={self.name!r} "
            f"customer_id={self.customer_id} "
            f"organization_id={self.organization_id}>"
        )