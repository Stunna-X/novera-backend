"""
Organization model.

An organization represents a company (tenant) using Novera.
Every business resource in the platform belongs to an organization.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Enum, Index, String, Text
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

    business_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    tax_identification_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    vat_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    bank_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    bank_account_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    bank_account_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    bank_routing_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    payment_instructions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    default_invoice_terms: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    default_quote_terms: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    invoice_footer: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    quote_footer: Mapped[str | None] = mapped_column(
        Text,
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