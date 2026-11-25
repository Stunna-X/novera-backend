"""remove obsolete workforce profile fields

Revision ID: 623f1aee9c5f
Revises: 28854ceb52aa
Create Date: 2026-11-19 00:30:07.779656

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# Revision identifiers used by Alembic.
revision: str = "623f1aee9c5f"
down_revision: Union[str, Sequence[str], None] = "28854ceb52aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove fields no longer required by standalone workforce profiles."""

    # Remove indexes before dropping their referenced columns.
    op.drop_index(
        "ix_workforce_profiles_is_available",
        table_name="workforce_profiles",
    )
    op.drop_index(
        "ix_workforce_profiles_organization_available",
        table_name="workforce_profiles",
    )
    op.drop_index(
        "ix_workforce_profiles_membership_id",
        table_name="workforce_profiles",
    )

    # Remove membership constraints before dropping membership_id.
    op.drop_constraint(
        "uq_workforce_profiles_membership",
        "workforce_profiles",
        type_="unique",
    )
    op.drop_constraint(
        "fk_workforce_profiles_membership_id_memberships",
        "workforce_profiles",
        type_="foreignkey",
    )

    # Remove obsolete employee fields.
    op.drop_column("workforce_profiles", "membership_id")
    op.drop_column("workforce_profiles", "emergency_contact_name")
    op.drop_column("workforce_profiles", "emergency_contact_phone")
    op.drop_column("workforce_profiles", "skills")
    op.drop_column("workforce_profiles", "is_available")
    op.drop_column("workforce_profiles", "notes")


def downgrade() -> None:
    """Restore the legacy columns and constraints structurally.

    Values removed by upgrade cannot be recovered. Restored JSONB and
    availability fields receive safe defaults for existing profiles.
    """

    # Restore nullable legacy fields.
    op.add_column(
        "workforce_profiles",
        sa.Column("membership_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "workforce_profiles",
        sa.Column(
            "emergency_contact_name",
            sa.String(length=160),
            nullable=True,
        ),
    )
    op.add_column(
        "workforce_profiles",
        sa.Column(
            "emergency_contact_phone",
            sa.String(length=50),
            nullable=True,
        ),
    )
    op.add_column(
        "workforce_profiles",
        sa.Column(
            "skills",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "workforce_profiles",
        sa.Column(
            "is_available",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "workforce_profiles",
        sa.Column("notes", sa.Text(), nullable=True),
    )

    # Remove temporary defaults after existing rows have been populated.
    op.alter_column(
        "workforce_profiles",
        "skills",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        server_default=None,
    )
    op.alter_column(
        "workforce_profiles",
        "is_available",
        existing_type=sa.Boolean(),
        server_default=None,
    )

    # Restore the optional membership relationship as it existed
    # immediately before this migration.
    op.create_foreign_key(
        "fk_workforce_profiles_membership_id_memberships",
        "workforce_profiles",
        "memberships",
        ["membership_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_workforce_profiles_membership",
        "workforce_profiles",
        ["membership_id"],
    )

    # Restore legacy indexes.
    op.create_index(
        "ix_workforce_profiles_membership_id",
        "workforce_profiles",
        ["membership_id"],
        unique=False,
    )
    op.create_index(
        "ix_workforce_profiles_is_available",
        "workforce_profiles",
        ["is_available"],
        unique=False,
    )
    op.create_index(
        "ix_workforce_profiles_organization_available",
        "workforce_profiles",
        ["organization_id", "is_available"],
        unique=False,
    )
