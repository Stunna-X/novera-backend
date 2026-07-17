"""
Quote models.

Stores organization-scoped customer quotes, estimate line items,
and an immutable quote activity trail.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
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
from app.enums.quote import QuoteStatus


if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.customer_site import CustomerSite
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.work_order import WorkOrder


class Quote(BaseModel):
    """
    Customer-facing quote or estimate.

    Customer identity and address fields are copied onto the quote
    so historical documents remain unchanged when customer records
    are edited later.
    """

    __tablename__ = "quotes"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "quote_number",
            name="uq_quotes_organization_number",
        ),
        UniqueConstraint(
            "converted_work_order_id",
            name="uq_quotes_converted_work_order_id",
        ),
        CheckConstraint(
            """
            status IN (
                'draft',
                'sent',
                'accepted',
                'rejected',
                'expired',
                'converted'
            )
            """,
            name="ck_quotes_status_valid",
        ),
        CheckConstraint(
            "char_length(currency) = 3",
            name="ck_quotes_currency_length",
        ),
        CheckConstraint(
            "subtotal >= 0",
            name="ck_quotes_subtotal_non_negative",
        ),
        CheckConstraint(
            "discount_amount >= 0",
            name="ck_quotes_discount_non_negative",
        ),
        CheckConstraint(
            "tax_amount >= 0",
            name="ck_quotes_tax_non_negative",
        ),
        CheckConstraint(
            "total_amount >= 0",
            name="ck_quotes_total_non_negative",
        ),
        CheckConstraint(
            """
            valid_until IS NULL
            OR valid_until >= quote_date
            """,
            name="ck_quotes_valid_until_valid",
        ),
        Index(
            "ix_quotes_organization_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_quotes_organization_customer",
            "organization_id",
            "customer_id",
        ),
        Index(
            "ix_quotes_organization_site",
            "organization_id",
            "customer_site_id",
        ),
        Index(
            "ix_quotes_organization_currency",
            "organization_id",
            "currency",
        ),
        Index(
            "ix_quotes_organization_valid_until",
            "organization_id",
            "valid_until",
        ),
        Index(
            "ix_quotes_organization_active",
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
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    customer_site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "customer_sites.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    converted_work_order_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "work_orders.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    created_by_user_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    sent_by_user_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    responded_by_user_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    converted_by_user_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    quote_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="NGN",
        server_default="NGN",
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=QuoteStatus.DRAFT.value,
        server_default=QuoteStatus.DRAFT.value,
        index=True,
    )

    quote_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    valid_until: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    customer_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    customer_email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )

    customer_phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    billing_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    service_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    terms: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    expired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    converted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    response_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        lazy="joined",
    )

    customer: Mapped["Customer"] = relationship(
        "Customer",
        lazy="joined",
    )

    customer_site: Mapped[
        "CustomerSite | None"
    ] = relationship(
        "CustomerSite",
        lazy="joined",
    )

    converted_work_order: Mapped[
        "WorkOrder | None"
    ] = relationship(
        "WorkOrder",
        foreign_keys=[converted_work_order_id],
        lazy="joined",
    )

    created_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by_user_id],
        lazy="joined",
    )

    sent_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[sent_by_user_id],
        lazy="joined",
    )

    responded_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[responded_by_user_id],
        lazy="joined",
    )

    converted_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[converted_by_user_id],
        lazy="joined",
    )

    line_items: Mapped[
        list["QuoteLineItem"]
    ] = relationship(
        "QuoteLineItem",
        back_populates="quote",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by=(
            "QuoteLineItem.position, "
            "QuoteLineItem.created_at"
        ),
    )

    activities: Mapped[
        list["QuoteActivity"]
    ] = relationship(
        "QuoteActivity",
        back_populates="quote",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="QuoteActivity.created_at",
    )

    def __repr__(self) -> str:
        """
        Return a developer-friendly representation.
        """

        return (
            f"<Quote "
            f"id={self.id} "
            f"number={self.quote_number!r} "
            f"currency={self.currency!r} "
            f"status={self.status!r} "
            f"total={self.total_amount}>"
        )


class QuoteLineItem(BaseModel):
    """
    One priced item or service on a quote.
    """

    __tablename__ = "quote_line_items"

    __table_args__ = (
        UniqueConstraint(
            "quote_id",
            "position",
            name="uq_quote_line_items_quote_position",
        ),
        CheckConstraint(
            "quantity > 0",
            name="ck_quote_line_items_quantity_positive",
        ),
        CheckConstraint(
            "unit_price >= 0",
            name="ck_quote_line_items_unit_price_non_negative",
        ),
        CheckConstraint(
            "line_total >= 0",
            name="ck_quote_line_items_total_non_negative",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_quote_line_items_position_non_negative",
        ),
        Index(
            "ix_quote_line_items_quote_active",
            "quote_id",
            "is_active",
        ),
    )

    quote_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "quotes.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=3,
        ),
        nullable=False,
        default=Decimal("1.000"),
        server_default="1.000",
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=False,
    )

    line_total: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    quote: Mapped["Quote"] = relationship(
        "Quote",
        back_populates="line_items",
    )

    def __repr__(self) -> str:
        """
        Return a developer-friendly representation.
        """

        return (
            f"<QuoteLineItem "
            f"id={self.id} "
            f"quote_id={self.quote_id} "
            f"total={self.line_total}>"
        )


class QuoteActivity(BaseModel):
    """
    Immutable quote lifecycle event.
    """

    __tablename__ = "quote_activities"

    __table_args__ = (
        Index(
            "ix_quote_activities_organization_quote",
            "organization_id",
            "quote_id",
        ),
        Index(
            "ix_quote_activities_quote_created",
            "quote_id",
            "created_at",
        ),
        Index(
            "ix_quote_activities_organization_type",
            "organization_id",
            "activity_type",
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

    quote_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "quotes.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    actor_user_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    activity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    summary: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    from_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    to_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    quote: Mapped["Quote"] = relationship(
        "Quote",
        back_populates="activities",
    )

    actor: Mapped["User | None"] = relationship(
        "User",
        lazy="joined",
    )

    def __repr__(self) -> str:
        """
        Return a developer-friendly representation.
        """

        return (
            f"<QuoteActivity "
            f"id={self.id} "
            f"quote_id={self.quote_id} "
            f"activity_type={self.activity_type!r}>"
        )