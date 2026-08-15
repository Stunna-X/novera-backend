"""
Supplier model.

Stores organization-scoped supplier records used by procurement,
purchase orders, goods receipts, inventory, and reporting.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


if TYPE_CHECKING:
    from app.models.organization import Organization


class Supplier(BaseModel):
    """
    Supplier belonging to one Novera organization.

    Every unique identifier is tenant-scoped so separate
    organizations can safely use the same supplier references.
    """

    __tablename__ = "suppliers"

    __table_args__ = (
        CheckConstraint(
            "supplier_type IN ('company', 'individual')",
            name="type_valid",
        ),
        CheckConstraint(
            "payment_terms_days >= 0 AND payment_terms_days <= 3650",
            name="payment_terms_days_valid",
        ),
        CheckConstraint(
            "char_length(currency) = 3",
            name="currency_length_valid",
        ),
        UniqueConstraint(
            "organization_id",
            "code",
            name="uq_suppliers_organization_code",
        ),
        UniqueConstraint(
            "organization_id",
            "tax_id",
            name="uq_suppliers_organization_tax_id",
        ),
        UniqueConstraint(
            "organization_id",
            "registration_number",
            name="uq_suppliers_organization_registration_number",
        ),
        Index(
            "ix_suppliers_organization_name",
            "organization_id",
            "name",
        ),
        Index(
            "ix_suppliers_organization_active",
            "organization_id",
            "is_active",
        ),
        Index(
            "ix_suppliers_organization_type",
            "organization_id",
            "supplier_type",
        ),
        Index(
            "ix_suppliers_organization_category",
            "organization_id",
            "category",
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

    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
    )

    supplier_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="company",
        server_default=text("'company'"),
        index=True,
    )

    category: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
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

    tax_id: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )

    registration_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    payment_terms_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="NGN",
        server_default=text("'NGN'"),
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

    details: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
        index=True,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        lazy="joined",
    )

    def __repr__(self) -> str:
        """Return a developer-friendly supplier representation."""

        return (
            f"<Supplier id={self.id} code={self.code!r} "
            f"name={self.name!r} "
            f"organization_id={self.organization_id}>"
        )
