"""Create document deliveries.

Revision ID: c2e4f6a8b1d3
Revises: b1c7d9e2f4a6
Create Date: 2026-07-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c2e4f6a8b1d3"
down_revision = "b1c7d9e2f4a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_deliveries",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(length=30), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_number", sa.String(length=80), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("recipient_name", sa.String(length=200), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("delivery_channel", sa.String(length=30), server_default="email", nullable=False),
        sa.Column("delivery_status", sa.String(length=30), server_default="recorded", nullable=False),
        sa.Column("provider", sa.String(length=80), server_default="manual", nullable=False),
        sa.Column("pdf_filename", sa.String(length=255), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("document_type IN ('invoice', 'quote')", name="ck_document_deliveries_document_type_valid"),
        sa.CheckConstraint("delivery_channel IN ('email', 'manual')", name="ck_document_deliveries_channel_valid"),
        sa.CheckConstraint(
            "delivery_status IN ('recorded', 'queued', 'sent', 'failed')",
            name="ck_document_deliveries_status_valid",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sent_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_document_deliveries_organization_id", "document_deliveries", ["organization_id"])
    op.create_index("ix_document_deliveries_document_type", "document_deliveries", ["document_type"])
    op.create_index("ix_document_deliveries_document_id", "document_deliveries", ["document_id"])
    op.create_index("ix_document_deliveries_document_number", "document_deliveries", ["document_number"])
    op.create_index("ix_document_deliveries_recipient_email", "document_deliveries", ["recipient_email"])
    op.create_index("ix_document_deliveries_delivery_status", "document_deliveries", ["delivery_status"])
    op.create_index("ix_document_deliveries_delivery_channel", "document_deliveries", ["delivery_channel"])
    op.create_index("ix_document_deliveries_sent_at", "document_deliveries", ["sent_at"])
    op.create_index("ix_document_deliveries_sent_by_user_id", "document_deliveries", ["sent_by_user_id"])
    op.create_index("ix_document_deliveries_is_active", "document_deliveries", ["is_active"])
    op.create_index("ix_document_deliveries_organization_created", "document_deliveries", ["organization_id", "created_at"])
    op.create_index("ix_document_deliveries_organization_type", "document_deliveries", ["organization_id", "document_type"])
    op.create_index("ix_document_deliveries_document", "document_deliveries", ["document_type", "document_id"])
    op.create_index("ix_document_deliveries_status", "document_deliveries", ["organization_id", "delivery_status"])


def downgrade() -> None:
    op.drop_index("ix_document_deliveries_status", table_name="document_deliveries")
    op.drop_index("ix_document_deliveries_document", table_name="document_deliveries")
    op.drop_index("ix_document_deliveries_organization_type", table_name="document_deliveries")
    op.drop_index("ix_document_deliveries_organization_created", table_name="document_deliveries")
    op.drop_index("ix_document_deliveries_is_active", table_name="document_deliveries")
    op.drop_index("ix_document_deliveries_sent_by_user_id", table_name="document_deliveries")
    op.drop_index("ix_document_deliveries_sent_at", table_name="document_deliveries")
    op.drop_index("ix_document_deliveries_delivery_channel", table_name="document_deliveries")
    op.drop_index("ix_document_deliveries_delivery_status", table_name="document_deliveries")
    op.drop_index("ix_document_deliveries_recipient_email", table_name="document_deliveries")
    op.drop_index("ix_document_deliveries_document_number", table_name="document_deliveries")
    op.drop_index("ix_document_deliveries_document_id", table_name="document_deliveries")
    op.drop_index("ix_document_deliveries_document_type", table_name="document_deliveries")
    op.drop_index("ix_document_deliveries_organization_id", table_name="document_deliveries")
    op.drop_table("document_deliveries")
