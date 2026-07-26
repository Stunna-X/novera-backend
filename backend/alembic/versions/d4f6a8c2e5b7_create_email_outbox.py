"""Create email outbox.

Revision ID: d4f6a8c2e5b7
Revises: c2e4f6a8b1d3
Create Date: 2026-07-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d4f6a8c2e5b7"
down_revision = "c2e4f6a8b1d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_outbox",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_delivery_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("queued_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=80), server_default="development", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="queued", nullable=False),
        sa.Column("from_email", sa.String(length=320), nullable=False),
        sa.Column("from_name", sa.String(length=200), nullable=True),
        sa.Column("reply_to_email", sa.String(length=320), nullable=True),
        sa.Column("to_email", sa.String(length=320), nullable=False),
        sa.Column("to_name", sa.String(length=200), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("attachment_filename", sa.String(length=255), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "provider IN ('development', 'smtp', 'sendgrid', 'mailgun', 'manual')",
            name="ck_email_outbox_provider_valid",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'sending', 'sent', 'failed', 'cancelled')",
            name="ck_email_outbox_status_valid",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_email_outbox_attempts_non_negative"),
        sa.CheckConstraint("max_attempts > 0", name="ck_email_outbox_max_attempts_positive"),
        sa.ForeignKeyConstraint(["document_delivery_id"], ["document_deliveries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["queued_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_delivery_id", name="uq_email_outbox_document_delivery"),
    )

    op.create_index("ix_email_outbox_organization_id", "email_outbox", ["organization_id"])
    op.create_index("ix_email_outbox_document_delivery_id", "email_outbox", ["document_delivery_id"])
    op.create_index("ix_email_outbox_queued_by_user_id", "email_outbox", ["queued_by_user_id"])
    op.create_index("ix_email_outbox_provider", "email_outbox", ["provider"])
    op.create_index("ix_email_outbox_status", "email_outbox", ["status"])
    op.create_index("ix_email_outbox_to_email", "email_outbox", ["to_email"])
    op.create_index("ix_email_outbox_next_attempt_at", "email_outbox", ["next_attempt_at"])
    op.create_index("ix_email_outbox_sent_at", "email_outbox", ["sent_at"])
    op.create_index("ix_email_outbox_failed_at", "email_outbox", ["failed_at"])
    op.create_index("ix_email_outbox_provider_message_id", "email_outbox", ["provider_message_id"])
    op.create_index("ix_email_outbox_is_active", "email_outbox", ["is_active"])
    op.create_index("ix_email_outbox_organization_status", "email_outbox", ["organization_id", "status"])
    op.create_index("ix_email_outbox_organization_created", "email_outbox", ["organization_id", "created_at"])
    op.create_index("ix_email_outbox_delivery", "email_outbox", ["document_delivery_id"])
    op.create_index("ix_email_outbox_next_attempt", "email_outbox", ["status", "next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_email_outbox_next_attempt", table_name="email_outbox")
    op.drop_index("ix_email_outbox_delivery", table_name="email_outbox")
    op.drop_index("ix_email_outbox_organization_created", table_name="email_outbox")
    op.drop_index("ix_email_outbox_organization_status", table_name="email_outbox")
    op.drop_index("ix_email_outbox_is_active", table_name="email_outbox")
    op.drop_index("ix_email_outbox_provider_message_id", table_name="email_outbox")
    op.drop_index("ix_email_outbox_failed_at", table_name="email_outbox")
    op.drop_index("ix_email_outbox_sent_at", table_name="email_outbox")
    op.drop_index("ix_email_outbox_next_attempt_at", table_name="email_outbox")
    op.drop_index("ix_email_outbox_to_email", table_name="email_outbox")
    op.drop_index("ix_email_outbox_status", table_name="email_outbox")
    op.drop_index("ix_email_outbox_provider", table_name="email_outbox")
    op.drop_index("ix_email_outbox_queued_by_user_id", table_name="email_outbox")
    op.drop_index("ix_email_outbox_document_delivery_id", table_name="email_outbox")
    op.drop_index("ix_email_outbox_organization_id", table_name="email_outbox")
    op.drop_table("email_outbox")
