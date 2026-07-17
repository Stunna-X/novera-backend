"""create notifications

Revision ID: e7c9a1b2d4f6
Revises: d2f8a7c9e4b1
Create Date: 2026-07-17 15:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e7c9a1b2d4f6"
down_revision = "d2f8a7c9e4b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "recipient_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "notification_type",
            sa.String(length=80),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=180),
            nullable=False,
        ),
        sa.Column(
            "message",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.String(length=20),
            server_default="info",
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            sa.String(length=80),
            nullable=True,
        ),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "action_url",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_read",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=True,
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
            ["actor_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_notifications_actor_user_id",
        "notifications",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_entity",
        "notifications",
        ["entity_type", "entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_entity_id",
        "notifications",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_entity_type",
        "notifications",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_is_archived",
        "notifications",
        ["is_archived"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_is_read",
        "notifications",
        ["is_read"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_notification_type",
        "notifications",
        ["notification_type"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_organization_archived",
        "notifications",
        ["organization_id", "recipient_user_id", "is_archived"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_organization_id",
        "notifications",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_organization_recipient",
        "notifications",
        ["organization_id", "recipient_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_organization_type",
        "notifications",
        ["organization_id", "notification_type"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_organization_unread",
        "notifications",
        ["organization_id", "recipient_user_id", "is_read"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_priority",
        "notifications",
        ["priority"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_recipient_user_id",
        "notifications",
        ["recipient_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notifications_recipient_user_id",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_priority",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_organization_unread",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_organization_type",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_organization_recipient",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_organization_id",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_organization_archived",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_notification_type",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_is_read",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_is_archived",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_entity_type",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_entity_id",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_entity",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_actor_user_id",
        table_name="notifications",
    )
    op.drop_table("notifications")
