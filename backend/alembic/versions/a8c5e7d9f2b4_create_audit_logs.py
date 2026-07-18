"""
Create audit logs.

Revision ID: a8c5e7d9f2b4
Revises: f4a9c2d1e8b7
Create Date: 2026-07-18
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a8c5e7d9f2b4"
down_revision = "f4a9c2d1e8b7"
branch_labels = None
depends_on = None


AUDIT_PERMISSION = "audit_logs.read"


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "actor_membership_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "action",
            sa.String(length=120),
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
            "summary",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="success",
            nullable=False,
        ),
        sa.Column(
            "request_method",
            sa.String(length=12),
            nullable=True,
        ),
        sa.Column(
            "request_path",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column(
            "ip_address",
            sa.String(length=80),
            nullable=True,
        ),
        sa.Column(
            "user_agent",
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
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_membership_id"],
            ["memberships.id"],
            ondelete="SET NULL",
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
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_audit_logs_actor_membership_id",
        "audit_logs",
        ["actor_membership_id"],
    )
    op.create_index(
        "ix_audit_logs_actor_user_id",
        "audit_logs",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_audit_logs_action",
        "audit_logs",
        ["action"],
    )
    op.create_index(
        "ix_audit_logs_entity_id",
        "audit_logs",
        ["entity_id"],
    )
    op.create_index(
        "ix_audit_logs_entity_type",
        "audit_logs",
        ["entity_type"],
    )
    op.create_index(
        "ix_audit_logs_organization_id",
        "audit_logs",
        ["organization_id"],
    )
    op.create_index(
        "ix_audit_logs_status",
        "audit_logs",
        ["status"],
    )
    op.create_index(
        "ix_audit_logs_actor_user",
        "audit_logs",
        ["organization_id", "actor_user_id"],
    )
    op.create_index(
        "ix_audit_logs_entity",
        "audit_logs",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_audit_logs_organization_action",
        "audit_logs",
        ["organization_id", "action"],
    )
    op.create_index(
        "ix_audit_logs_organization_created",
        "audit_logs",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_audit_logs_status_composite",
        "audit_logs",
        ["organization_id", "status"],
    )

    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            INSERT INTO permissions (
                id,
                name,
                description,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :name,
                :description,
                now(),
                now()
            )
            ON CONFLICT (name)
            DO UPDATE SET
                description = EXCLUDED.description,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "name": AUDIT_PERMISSION,
            "description": "Read organization audit logs.",
        },
    )

    for role_name in ("owner", "admin"):
        bind.execute(
            sa.text(
                """
                INSERT INTO role_permissions (
                    id,
                    role_id,
                    permission_id,
                    created_at,
                    updated_at
                )
                SELECT
                    :id,
                    roles.id,
                    permissions.id,
                    now(),
                    now()
                FROM roles
                JOIN permissions
                    ON permissions.name = :permission_name
                WHERE lower(roles.name) = :role_name
                ON CONFLICT (role_id, permission_id)
                DO NOTHING
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "role_name": role_name,
                "permission_name": AUDIT_PERMISSION,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            USING permissions
            WHERE role_permissions.permission_id = permissions.id
            AND permissions.name = :permission_name
            """
        ),
        {
            "permission_name": AUDIT_PERMISSION,
        },
    )

    bind.execute(
        sa.text(
            """
            DELETE FROM permissions
            WHERE name = :permission_name
            """
        ),
        {
            "permission_name": AUDIT_PERMISSION,
        },
    )

    op.drop_index(
        "ix_audit_logs_status_composite",
        table_name="audit_logs",
    )
    op.drop_index(
        "ix_audit_logs_organization_created",
        table_name="audit_logs",
    )
    op.drop_index(
        "ix_audit_logs_organization_action",
        table_name="audit_logs",
    )
    op.drop_index(
        "ix_audit_logs_entity",
        table_name="audit_logs",
    )
    op.drop_index(
        "ix_audit_logs_actor_user",
        table_name="audit_logs",
    )
    op.drop_index(
        "ix_audit_logs_status",
        table_name="audit_logs",
    )
    op.drop_index(
        "ix_audit_logs_organization_id",
        table_name="audit_logs",
    )
    op.drop_index(
        "ix_audit_logs_entity_type",
        table_name="audit_logs",
    )
    op.drop_index(
        "ix_audit_logs_entity_id",
        table_name="audit_logs",
    )
    op.drop_index(
        "ix_audit_logs_action",
        table_name="audit_logs",
    )
    op.drop_index(
        "ix_audit_logs_actor_user_id",
        table_name="audit_logs",
    )
    op.drop_index(
        "ix_audit_logs_actor_membership_id",
        table_name="audit_logs",
    )

    op.drop_table("audit_logs")
