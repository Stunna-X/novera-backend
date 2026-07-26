"""create work order closeouts

Revision ID: d2f8a7c9e4b1
Revises: b7a4d2e91c63
Create Date: 2026-07-17 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d2f8a7c9e4b1"
down_revision: str | None = "b7a4d2e91c63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create work-order closeout table."""

    op.create_table(
        "work_order_closeouts",
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
            "invoice_ready_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="submitted",
        ),
        sa.Column(
            "completion_summary",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "work_performed",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "materials_used",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "customer_notes",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "internal_notes",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "customer_name",
            sa.String(length=160),
            nullable=True,
        ),
        sa.Column(
            "customer_email",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "customer_phone",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "customer_title",
            sa.String(length=120),
            nullable=True,
        ),
        sa.Column(
            "customer_signature_url",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "customer_rating",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "customer_feedback",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "rejection_reason",
            sa.Text(),
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
            "invoice_ready_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "is_invoice_ready",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
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
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"],
            ["users.id"],
            name=op.f(
                "fk_work_order_closeouts_approved_by_user_id_users"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f(
                "fk_work_order_closeouts_created_by_user_id_users"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_ready_by_user_id"],
            ["users.id"],
            name=op.f(
                "fk_work_order_closeouts_invoice_ready_by_user_id_users"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f(
                "fk_work_order_closeouts_organization_id_organizations"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rejected_by_user_id"],
            ["users.id"],
            name=op.f(
                "fk_work_order_closeouts_rejected_by_user_id_users"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["users.id"],
            name=op.f(
                "fk_work_order_closeouts_submitted_by_user_id_users"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["work_orders.id"],
            name=op.f(
                "fk_work_order_closeouts_work_order_id_work_orders"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_work_order_closeouts"),
        ),
        sa.UniqueConstraint(
            "work_order_id",
            name="uq_work_order_closeouts_work_order_id",
        ),
    )

    op.create_index(
        "ix_work_order_closeouts_organization_id",
        "work_order_closeouts",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_closeouts_work_order_id",
        "work_order_closeouts",
        ["work_order_id"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_closeouts_created_by_user_id",
        "work_order_closeouts",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_closeouts_submitted_by_user_id",
        "work_order_closeouts",
        ["submitted_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_closeouts_approved_by_user_id",
        "work_order_closeouts",
        ["approved_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_closeouts_rejected_by_user_id",
        "work_order_closeouts",
        ["rejected_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_closeouts_invoice_ready_by_user_id",
        "work_order_closeouts",
        ["invoice_ready_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_closeouts_status",
        "work_order_closeouts",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_closeouts_is_invoice_ready",
        "work_order_closeouts",
        ["is_invoice_ready"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_closeouts_organization_status",
        "work_order_closeouts",
        ["organization_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_closeouts_invoice_ready",
        "work_order_closeouts",
        ["organization_id", "is_invoice_ready"],
        unique=False,
    )


def downgrade() -> None:
    """Drop work-order closeout table."""

    op.drop_index(
        "ix_work_order_closeouts_invoice_ready",
        table_name="work_order_closeouts",
    )
    op.drop_index(
        "ix_work_order_closeouts_organization_status",
        table_name="work_order_closeouts",
    )
    op.drop_index(
        "ix_work_order_closeouts_is_invoice_ready",
        table_name="work_order_closeouts",
    )
    op.drop_index(
        "ix_work_order_closeouts_status",
        table_name="work_order_closeouts",
    )
    op.drop_index(
        "ix_work_order_closeouts_invoice_ready_by_user_id",
        table_name="work_order_closeouts",
    )
    op.drop_index(
        "ix_work_order_closeouts_rejected_by_user_id",
        table_name="work_order_closeouts",
    )
    op.drop_index(
        "ix_work_order_closeouts_approved_by_user_id",
        table_name="work_order_closeouts",
    )
    op.drop_index(
        "ix_work_order_closeouts_submitted_by_user_id",
        table_name="work_order_closeouts",
    )
    op.drop_index(
        "ix_work_order_closeouts_created_by_user_id",
        table_name="work_order_closeouts",
    )
    op.drop_index(
        "ix_work_order_closeouts_work_order_id",
        table_name="work_order_closeouts",
    )
    op.drop_index(
        "ix_work_order_closeouts_organization_id",
        table_name="work_order_closeouts",
    )
    op.drop_table("work_order_closeouts")
