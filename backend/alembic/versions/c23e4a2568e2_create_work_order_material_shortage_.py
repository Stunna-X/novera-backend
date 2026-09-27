"""create work order material shortage allowances

Revision ID: c23e4a2568e2
Revises: e09636694673
Create Date: 2026-09-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c23e4a2568e2"
down_revision = "e09636694673"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_order_material_shortage_allowances",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "work_order_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "work_order_material_requirement_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "requested_quantity",
            sa.Numeric(precision=16, scale=3),
            nullable=False,
        ),
        sa.Column(
            "approved_quantity",
            sa.Numeric(precision=16, scale=3),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "submitted_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "approved_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "rejected_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "cancelled_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "rejected_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "cancelled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "rejection_reason",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "cancellation_reason",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_work_order_material_shortage_allowances",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_shortage_allowance_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["work_orders.id"],
            name="fk_shortage_allowance_work_order",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["work_order_material_requirement_id"],
            ["work_order_material_requirements.id"],
            name="fk_shortage_allowance_requirement",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_shortage_allowance_created_by",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["users.id"],
            name="fk_shortage_allowance_submitted_by",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"],
            ["users.id"],
            name="fk_shortage_allowance_approved_by",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["rejected_by_user_id"],
            ["users.id"],
            name="fk_shortage_allowance_rejected_by",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["cancelled_by_user_id"],
            ["users.id"],
            name="fk_shortage_allowance_cancelled_by",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "work_order_material_requirement_id",
            name="uq_work_order_material_shortage_allowances_requirement",
        ),
        sa.CheckConstraint(
            "requested_quantity > 0",
            name="requested_quantity_positive",
        ),
        sa.CheckConstraint(
            "approved_quantity >= 0",
            name="approved_quantity_non_negative",
        ),
        sa.CheckConstraint(
            "approved_quantity <= requested_quantity",
            name="approved_quantity_not_greater_than_requested",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'approved', 'rejected', 'cancelled')",
            name="valid_status",
        ),
    )

    op.create_index(
        "ix_shortage_allowance_org",
        "work_order_material_shortage_allowances",
        ["organization_id"],
    )
    op.create_index(
        "ix_shortage_allowance_work_order",
        "work_order_material_shortage_allowances",
        ["work_order_id"],
    )
    op.create_index(
        "ix_shortage_allowance_requirement",
        "work_order_material_shortage_allowances",
        ["work_order_material_requirement_id"],
    )
    op.create_index(
        "ix_shortage_allowance_created_by",
        "work_order_material_shortage_allowances",
        ["created_by_user_id"],
    )
    op.create_index(
        "ix_shortage_allowance_submitted_by",
        "work_order_material_shortage_allowances",
        ["submitted_by_user_id"],
    )
    op.create_index(
        "ix_shortage_allowance_approved_by",
        "work_order_material_shortage_allowances",
        ["approved_by_user_id"],
    )
    op.create_index(
        "ix_shortage_allowance_rejected_by",
        "work_order_material_shortage_allowances",
        ["rejected_by_user_id"],
    )
    op.create_index(
        "ix_shortage_allowance_cancelled_by",
        "work_order_material_shortage_allowances",
        ["cancelled_by_user_id"],
    )
    op.create_index(
        "ix_shortage_allowance_status",
        "work_order_material_shortage_allowances",
        ["status"],
    )
    op.create_index(
        "ix_shortage_allowance_active",
        "work_order_material_shortage_allowances",
        ["is_active"],
    )
    op.create_index(
        "ix_shortage_allowance_org_work_order",
        "work_order_material_shortage_allowances",
        ["organization_id", "work_order_id"],
    )
    op.create_index(
        "ix_shortage_allowance_work_order_status",
        "work_order_material_shortage_allowances",
        ["work_order_id", "status"],
    )
    op.create_index(
        "ix_shortage_allowance_requirement_status",
        "work_order_material_shortage_allowances",
        ["work_order_material_requirement_id", "status"],
    )
    op.create_index(
        "ix_shortage_allowance_org_active",
        "work_order_material_shortage_allowances",
        ["organization_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_shortage_allowance_org_active",
        table_name="work_order_material_shortage_allowances",
    )
    op.drop_index(
        "ix_shortage_allowance_requirement_status",
        table_name="work_order_material_shortage_allowances",
    )
    op.drop_index(
        "ix_shortage_allowance_work_order_status",
        table_name="work_order_material_shortage_allowances",
    )
    op.drop_index(
        "ix_shortage_allowance_org_work_order",
        table_name="work_order_material_shortage_allowances",
    )
    op.drop_index(
        "ix_shortage_allowance_active",
        table_name="work_order_material_shortage_allowances",
    )
    op.drop_index(
        "ix_shortage_allowance_status",
        table_name="work_order_material_shortage_allowances",
    )
    op.drop_index(
        "ix_shortage_allowance_cancelled_by",
        table_name="work_order_material_shortage_allowances",
    )
    op.drop_index(
        "ix_shortage_allowance_rejected_by",
        table_name="work_order_material_shortage_allowances",
    )
    op.drop_index(
        "ix_shortage_allowance_approved_by",
        table_name="work_order_material_shortage_allowances",
    )
    op.drop_index(
        "ix_shortage_allowance_submitted_by",
        table_name="work_order_material_shortage_allowances",
    )
    op.drop_index(
        "ix_shortage_allowance_created_by",
        table_name="work_order_material_shortage_allowances",
    )
    op.drop_index(
        "ix_shortage_allowance_requirement",
        table_name="work_order_material_shortage_allowances",
    )
    op.drop_index(
        "ix_shortage_allowance_work_order",
        table_name="work_order_material_shortage_allowances",
    )
    op.drop_index(
        "ix_shortage_allowance_org",
        table_name="work_order_material_shortage_allowances",
    )

    op.drop_table("work_order_material_shortage_allowances")