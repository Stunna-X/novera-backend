"""repair role permission assignments

Revision ID: 245083dcf1b7
Revises: a7f4c2d9e1b6
Create Date: 2026-08-13 00:05:04.547577
"""

from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = "245083dcf1b7"
down_revision: Union[str, Sequence[str], None] = "a7f4c2d9e1b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Repair missing Owner role permission assignments."""

    bind = op.get_bind()

    owner_role_id = bind.execute(
        sa.text(
            """
            SELECT id
            FROM roles
            WHERE lower(name) = 'owner'
            """
        )
    ).scalar_one_or_none()

    if owner_role_id is None:
        return

    permission_ids = bind.execute(
        sa.text(
            """
            SELECT id
            FROM permissions
            ORDER BY id
            """
        )
    ).scalars().all()

    for permission_id in permission_ids:
        exists = bind.execute(
            sa.text(
                """
                SELECT 1
                FROM role_permissions
                WHERE role_id = :role_id
                  AND permission_id = :permission_id
                """
            ),
            {
                "role_id": owner_role_id,
                "permission_id": permission_id,
            },
        ).scalar_one_or_none()

        if exists is not None:
            continue

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
                VALUES (
                    :id,
                    :role_id,
                    :permission_id,
                    now(),
                    now()
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "role_id": owner_role_id,
                "permission_id": permission_id,
            },
        )


def downgrade() -> None:
    """Preserve repaired Owner permissions during downgrade."""

    pass
