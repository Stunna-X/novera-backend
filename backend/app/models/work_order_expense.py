"""
Work-order expense model.

Stores labour, material, transport, equipment, and other
operational costs recorded against work orders.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
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
from app.enums.work_order_expense import (
    WorkOrderExpenseCategory,
    WorkOrderExpenseStatus,
)


if TYPE_CHECKING:
    from app.models.user import User
    from app.models.work_order import WorkOrder


class WorkOrderExpense(BaseModel):
    """
    One operational expense belonging to a work order.
    """

    __tablename__ = "work_order_expenses"

    __table_args__ = (
        CheckConstraint(
            """
            category IN (
                'labour',
                'materials',
                'transport',
                'equipment',
                'subcontractor',
                'permit',
                'accommodation',
                'other'
            )
            """,
            name="ck_work_order_expenses_category_valid",
        ),
        CheckConstraint(
            """
            status IN (
                'draft',
                'submitted',
                'approved',
                'rejected'
            )
            """,
            name="ck_work_order_expenses_status_valid",
        ),
        CheckConstraint(
            "quantity > 0",
            name="ck_work_order_expenses_quantity_positive",
        ),
        CheckConstraint(
            "unit_cost >= 0",
            name="ck_work_order_expenses_unit_cost_non_negative",
        ),
        CheckConstraint(
            "total_amount >= 0",
            name="ck_work_order_expenses_total_non_negative",
        ),
        CheckConstraint(
            "char_length(currency) = 3",
            name="ck_work_order_expenses_currency_length",
        ),
        Index(
            "ix_work_order_expenses_work_order_status",
            "work_order_id",
            "status",
        ),
        Index(
            "ix_work_order_expenses_work_order_category",
            "work_order_id",
            "category",
        ),
        Index(
            "ix_work_order_expenses_work_order_date",
            "work_order_id",
            "expense_date",
        ),
        Index(
            "ix_work_order_expenses_work_order_active",
            "work_order_id",
            "is_active",
        ),
    )

    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "work_orders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
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

    reviewed_by_user_id: Mapped[
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

    category: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=WorkOrderExpenseCategory.OTHER.value,
        server_default=WorkOrderExpenseCategory.OTHER.value,
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

    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=False,
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="NGN",
        server_default="NGN",
        index=True,
    )

    expense_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    vendor_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    reference_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_billable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=WorkOrderExpenseStatus.DRAFT.value,
        server_default=WorkOrderExpenseStatus.DRAFT.value,
        index=True,
    )

    submitted_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    reviewed_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    review_note: Mapped[str | None] = mapped_column(
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

    work_order: Mapped["WorkOrder"] = relationship(
        "WorkOrder",
        back_populates="expenses",
    )

    created_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by_user_id],
        lazy="joined",
    )

    reviewed_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[reviewed_by_user_id],
        lazy="joined",
    )

    def __repr__(self) -> str:
        """
        Return a developer-friendly representation.
        """

        return (
            f"<WorkOrderExpense "
            f"id={self.id} "
            f"work_order_id={self.work_order_id} "
            f"category={self.category!r} "
            f"amount={self.total_amount} "
            f"currency={self.currency!r} "
            f"status={self.status!r}>"
        )