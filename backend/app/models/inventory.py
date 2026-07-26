"""
Inventory models.

Tracks organization-scoped consumables, materials, spare parts,
stock locations, balances, work-order reservations, and the
immutable stock-movement ledger.

Reusable equipment remains in the Asset model.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
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


if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.work_order import WorkOrder


class InventoryLocation(BaseModel):
    """
    Physical or mobile location where stock is held.
    """

    __tablename__ = "inventory_locations"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "code",
            name="uq_inventory_locations_organization_code",
        ),
        CheckConstraint(
            """
            location_type IN (
                'warehouse',
                'store',
                'vehicle',
                'job_site',
                'technician',
                'other'
            )
            """,
            name="type_valid",
        ),
        Index(
            "ix_inventory_locations_organization_name",
            "organization_id",
            "name",
        ),
        Index(
            "ix_inventory_locations_organization_type",
            "organization_id",
            "location_type",
        ),
        Index(
            "ix_inventory_locations_organization_active",
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

    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    location_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="warehouse",
        server_default="warehouse",
        index=True,
    )

    address: Mapped[str | None] = mapped_column(
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
        server_default="true",
        index=True,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        lazy="joined",
    )

    balances: Mapped[list["InventoryBalance"]] = relationship(
        "InventoryBalance",
        back_populates="location",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    reservations: Mapped[
        list["InventoryReservation"]
    ] = relationship(
        "InventoryReservation",
        back_populates="location",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<InventoryLocation "
            f"id={self.id} "
            f"code={self.code!r} "
            f"name={self.name!r}>"
        )


class InventoryItem(BaseModel):
    """
    Organization inventory catalogue item.
    """

    __tablename__ = "inventory_items"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "sku",
            name="uq_inventory_items_organization_sku",
        ),
        UniqueConstraint(
            "organization_id",
            "barcode",
            name="uq_inventory_items_organization_barcode",
        ),
        CheckConstraint(
            """
            item_type IN (
                'material',
                'consumable',
                'spare_part',
                'supply',
                'fuel',
                'other'
            )
            """,
            name="type_valid",
        ),
        CheckConstraint(
            "default_unit_cost >= 0",
            name="default_cost_non_negative",
        ),
        CheckConstraint(
            "reorder_level >= 0",
            name="reorder_level_non_negative",
        ),
        CheckConstraint(
            """
            reorder_quantity IS NULL
            OR reorder_quantity > 0
            """,
            name="reorder_quantity_positive",
        ),
        Index(
            "ix_inventory_items_organization_name",
            "organization_id",
            "name",
        ),
        Index(
            "ix_inventory_items_organization_type",
            "organization_id",
            "item_type",
        ),
        Index(
            "ix_inventory_items_organization_category",
            "organization_id",
            "category",
        ),
        Index(
            "ix_inventory_items_organization_active",
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

    sku: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    barcode: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
    )

    item_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="material",
        server_default="material",
        index=True,
    )

    category: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    unit_of_measure: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="each",
        server_default="each",
    )

    default_unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=4,
        ),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="NGN",
        server_default="NGN",
    )

    reorder_level: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=16,
            scale=3,
        ),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )

    reorder_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=16,
            scale=3,
        ),
        nullable=True,
    )

    preferred_supplier: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
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

    balances: Mapped[list["InventoryBalance"]] = relationship(
        "InventoryBalance",
        back_populates="item",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    reservations: Mapped[
        list["InventoryReservation"]
    ] = relationship(
        "InventoryReservation",
        back_populates="item",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<InventoryItem "
            f"id={self.id} "
            f"sku={self.sku!r} "
            f"name={self.name!r}>"
        )


class InventoryBalance(BaseModel):
    """
    Current stock balance for one item at one location.

    All balance-changing operations must lock this row before
    updating quantities.
    """

    __tablename__ = "inventory_balances"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "item_id",
            "location_id",
            name="uq_inventory_balances_item_location",
        ),
        CheckConstraint(
            "quantity_on_hand >= 0",
            name="on_hand_non_negative",
        ),
        CheckConstraint(
            "quantity_reserved >= 0",
            name="reserved_non_negative",
        ),
        CheckConstraint(
            "quantity_reserved <= quantity_on_hand",
            name="reserved_within_stock",
        ),
        CheckConstraint(
            "average_unit_cost >= 0",
            name="average_cost_non_negative",
        ),
        Index(
            "ix_inventory_balances_organization_item",
            "organization_id",
            "item_id",
        ),
        Index(
            "ix_inventory_balances_organization_location",
            "organization_id",
            "location_id",
        ),
        Index(
            "ix_inventory_balances_location_item",
            "location_id",
            "item_id",
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

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "inventory_items.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "inventory_locations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    quantity_on_hand: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=16,
            scale=3,
        ),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )

    quantity_reserved: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=16,
            scale=3,
        ),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )

    average_unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=4,
        ),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )

    last_movement_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        lazy="joined",
    )

    item: Mapped["InventoryItem"] = relationship(
        "InventoryItem",
        back_populates="balances",
        lazy="joined",
    )

    location: Mapped["InventoryLocation"] = relationship(
        "InventoryLocation",
        back_populates="balances",
        lazy="joined",
    )

    @property
    def available_quantity(self) -> Decimal:
        """
        Quantity available after active reservations.
        """

        return (
            Decimal(self.quantity_on_hand)
            - Decimal(self.quantity_reserved)
        )

    def __repr__(self) -> str:
        return (
            f"<InventoryBalance "
            f"item_id={self.item_id} "
            f"location_id={self.location_id} "
            f"on_hand={self.quantity_on_hand}>"
        )


class InventoryReservation(BaseModel):
    """
    Stock reserved for one work order.
    """

    __tablename__ = "inventory_reservations"

    __table_args__ = (
        CheckConstraint(
            """
            status IN (
                'active',
                'partially_consumed',
                'consumed',
                'released',
                'cancelled'
            )
            """,
            name="status_valid",
        ),
        CheckConstraint(
            "quantity_reserved > 0",
            name="quantity_positive",
        ),
        CheckConstraint(
            "quantity_consumed >= 0",
            name="consumed_non_negative",
        ),
        CheckConstraint(
            "quantity_consumed <= quantity_reserved",
            name="consumed_within_reserved",
        ),
        Index(
            "ix_inventory_reservations_organization_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_inventory_reservations_work_order",
            "work_order_id",
        ),
        Index(
            "ix_inventory_reservations_item_location",
            "item_id",
            "location_id",
        ),
        Index(
            "ix_inventory_reservations_organization_created",
            "organization_id",
            "created_at",
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

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "inventory_items.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "inventory_locations.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "work_orders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    quantity_reserved: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=16,
            scale=3,
        ),
        nullable=False,
    )

    quantity_consumed: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=16,
            scale=3,
        ),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        server_default="active",
        index=True,
    )

    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
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

    item: Mapped["InventoryItem"] = relationship(
        "InventoryItem",
        back_populates="reservations",
        lazy="joined",
    )

    location: Mapped["InventoryLocation"] = relationship(
        "InventoryLocation",
        back_populates="reservations",
        lazy="joined",
    )

    work_order: Mapped["WorkOrder"] = relationship(
        "WorkOrder",
        lazy="joined",
    )

    created_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by_user_id],
        lazy="joined",
    )

    updated_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[updated_by_user_id],
        lazy="joined",
    )

    @property
    def remaining_quantity(self) -> Decimal:
        """
        Reserved quantity that has not yet been consumed.
        """

        return (
            Decimal(self.quantity_reserved)
            - Decimal(self.quantity_consumed)
        )

    def __repr__(self) -> str:
        return (
            f"<InventoryReservation "
            f"id={self.id} "
            f"work_order_id={self.work_order_id} "
            f"status={self.status!r}>"
        )


class InventoryMovement(BaseModel):
    """
    Immutable inventory stock-movement ledger entry.

    Transfers create two correlated rows: transfer_out from the
    source location and transfer_in at the destination location.
    """

    __tablename__ = "inventory_movements"

    __table_args__ = (
        CheckConstraint(
            """
            movement_type IN (
                'opening_balance',
                'receipt',
                'issue',
                'return',
                'adjustment_in',
                'adjustment_out',
                'transfer_in',
                'transfer_out'
            )
            """,
            name="type_valid",
        ),
        CheckConstraint(
            "quantity > 0",
            name="quantity_positive",
        ),
        CheckConstraint(
            "quantity_delta <> 0",
            name="delta_non_zero",
        ),
        CheckConstraint(
            "quantity_before >= 0",
            name="before_non_negative",
        ),
        CheckConstraint(
            "quantity_after >= 0",
            name="after_non_negative",
        ),
        CheckConstraint(
            """
            quantity_after
            = quantity_before + quantity_delta
            """,
            name="balance_consistent",
        ),
        CheckConstraint(
            """
            unit_cost IS NULL
            OR unit_cost >= 0
            """,
            name="unit_cost_non_negative",
        ),
        Index(
            "ix_inventory_movements_organization_item_time",
            "organization_id",
            "item_id",
            "occurred_at",
        ),
        Index(
            "ix_inventory_movements_location_time",
            "location_id",
            "occurred_at",
        ),
        Index(
            "ix_inventory_movements_work_order",
            "work_order_id",
        ),
        Index(
            "ix_inventory_movements_reservation",
            "reservation_id",
        ),
        Index(
            "ix_inventory_movements_transfer_group",
            "transfer_group_id",
        ),
        Index(
            "ix_inventory_movements_reference",
            "reference_type",
            "reference_id",
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

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "inventory_items.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "inventory_locations.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    work_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "work_orders.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "inventory_reservations.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    movement_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=16,
            scale=3,
        ),
        nullable=False,
    )

    quantity_delta: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=16,
            scale=3,
        ),
        nullable=False,
    )

    quantity_before: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=16,
            scale=3,
        ),
        nullable=False,
    )

    quantity_after: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=16,
            scale=3,
        ),
        nullable=False,
    )

    unit_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=14,
            scale=4,
        ),
        nullable=True,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="NGN",
        server_default="NGN",
    )

    reference_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    reference_id: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    transfer_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        lazy="joined",
    )

    item: Mapped["InventoryItem"] = relationship(
        "InventoryItem",
        lazy="joined",
    )

    location: Mapped["InventoryLocation"] = relationship(
        "InventoryLocation",
        lazy="joined",
    )

    work_order: Mapped["WorkOrder | None"] = relationship(
        "WorkOrder",
        lazy="joined",
    )

    reservation: Mapped[
        "InventoryReservation | None"
    ] = relationship(
        "InventoryReservation",
        lazy="joined",
    )

    created_by: Mapped["User | None"] = relationship(
        "User",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<InventoryMovement "
            f"id={self.id} "
            f"type={self.movement_type!r} "
            f"delta={self.quantity_delta}>"
        )