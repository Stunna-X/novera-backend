"""
Work-order models.

Stores field-service work orders and their assigned
workforce members and operational assets.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
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
    from app.models.asset import Asset
    from app.models.customer import Customer
    from app.models.customer_site import CustomerSite
    from app.models.organization import Organization
    from app.models.workforce_profile import WorkforceProfile


class WorkOrder(BaseModel):
    """
    Organization-scoped field-service work order.
    """

    __tablename__ = "work_orders"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "work_order_number",
            name="uq_work_orders_organization_number",
        ),
        Index(
            "ix_work_orders_organization_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_work_orders_organization_priority",
            "organization_id",
            "priority",
        ),
        Index(
            "ix_work_orders_organization_customer",
            "organization_id",
            "customer_id",
        ),
        Index(
            "ix_work_orders_organization_site",
            "organization_id",
            "customer_site_id",
        ),
        Index(
            "ix_work_orders_organization_active",
            "organization_id",
            "is_active",
        ),
        Index(
            "ix_work_orders_scheduled_start",
            "scheduled_start",
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

    work_order_number: Mapped[str] = mapped_column(
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

    job_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    customer_reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="normal",
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",
        index=True,
    )

    scheduled_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    scheduled_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    actual_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    actual_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    estimated_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=True,
    )

    actual_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=True,
    )

    instructions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    completion_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    cancellation_reason: Mapped[str | None] = mapped_column(
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

    customer: Mapped["Customer"] = relationship(
        "Customer",
    )

    customer_site: Mapped["CustomerSite | None"] = relationship(
        "CustomerSite",
    )

    workforce_assignments: Mapped[
        list["WorkOrderWorkforceAssignment"]
    ] = relationship(
        "WorkOrderWorkforceAssignment",
        back_populates="work_order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    asset_assignments: Mapped[
        list["WorkOrderAssetAssignment"]
    ] = relationship(
        "WorkOrderAssetAssignment",
        back_populates="work_order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<WorkOrder "
            f"id={self.id} "
            f"number={self.work_order_number!r} "
            f"status={self.status!r}>"
        )


class WorkOrderWorkforceAssignment(BaseModel):
    """
    Connects workforce profiles to work orders.
    """

    __tablename__ = "work_order_workforce_assignments"

    __table_args__ = (
        UniqueConstraint(
            "work_order_id",
            "workforce_profile_id",
            name="uq_work_order_workforce_assignment",
        ),
        Index(
            "ix_work_order_workforce_work_order",
            "work_order_id",
        ),
        Index(
            "ix_work_order_workforce_profile",
            "workforce_profile_id",
        ),
    )

    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "work_orders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    workforce_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "workforce_profiles.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    work_order: Mapped["WorkOrder"] = relationship(
        "WorkOrder",
        back_populates="workforce_assignments",
    )

    workforce_profile: Mapped["WorkforceProfile"] = relationship(
        "WorkforceProfile",
    )


class WorkOrderAssetAssignment(BaseModel):
    """
    Connects operational assets to work orders.
    """

    __tablename__ = "work_order_asset_assignments"

    __table_args__ = (
        UniqueConstraint(
            "work_order_id",
            "asset_id",
            name="uq_work_order_asset_assignment",
        ),
        Index(
            "ix_work_order_asset_work_order",
            "work_order_id",
        ),
        Index(
            "ix_work_order_asset_asset",
            "asset_id",
        ),
    )

    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "work_orders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "assets.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    work_order: Mapped["WorkOrder"] = relationship(
        "WorkOrder",
        back_populates="asset_assignments",
    )

    asset: Mapped["Asset"] = relationship(
        "Asset",
    )