"""
Procurement alert preference and delivery models.

Preferences are scoped to one organization member. Delivery rows form an
immutable deduplication and operational history layer around the existing
notification inbox.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


if TYPE_CHECKING:
    from app.models.notification import Notification
    from app.models.organization import Organization
    from app.models.user import User


class ProcurementAlertPreference(BaseModel):
    """One user's procurement alert settings inside an organization."""

    __tablename__ = "procurement_alert_preferences"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_procurement_alert_preferences_organization_user",
        ),
        CheckConstraint(
            "delivery_lead_days >= 0 AND delivery_lead_days <= 30",
            name="delivery_lead_days_valid",
        ),
        CheckConstraint(
            "payment_lead_days >= 0 AND payment_lead_days <= 30",
            name="payment_lead_days_valid",
        ),
        Index(
            "ix_procurement_alert_preferences_organization_active",
            "organization_id",
            "is_active",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    requisition_approval_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    purchase_order_delivery_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    supplier_bill_overdue_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    match_exception_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    payment_action_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    delivery_lead_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default=text("3"),
    )

    payment_lead_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default=text("3"),
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

    user: Mapped["User"] = relationship(
        "User",
        lazy="joined",
    )


class ProcurementAlertDelivery(BaseModel):
    """One deduplicated procurement alert delivered to one user."""

    __tablename__ = "procurement_alert_deliveries"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "recipient_user_id",
            "deduplication_key",
            name="uq_procurement_alert_deliveries_dedupe",
        ),
        CheckConstraint(
            """
            alert_type IN (
                'requisition_approval_required',
                'purchase_order_delivery_due',
                'purchase_order_delivery_overdue',
                'supplier_bill_overdue',
                'supplier_bill_match_exception',
                'supplier_payment_action_required'
            )
            """,
            name="alert_type_valid",
        ),
        CheckConstraint(
            "status IN ('delivered', 'suppressed', 'failed')",
            name="status_valid",
        ),
        Index(
            "ix_procurement_alert_deliveries_organization_recipient",
            "organization_id",
            "recipient_user_id",
        ),
        Index(
            "ix_procurement_alert_deliveries_organization_type_date",
            "organization_id",
            "alert_type",
            "alert_date",
        ),
        Index(
            "ix_procurement_alert_deliveries_entity",
            "entity_type",
            "entity_id",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    notification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    alert_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        index=True,
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    alert_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    deduplication_key: Mapped[str] = mapped_column(
        String(240),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="delivered",
        server_default=text("'delivered'"),
        index=True,
    )

    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        lazy="joined",
    )

    recipient: Mapped["User"] = relationship(
        "User",
        lazy="joined",
    )

    notification: Mapped["Notification | None"] = relationship(
        "Notification",
        lazy="joined",
    )
