"""redesign workforce profiles and job assignments

Revision ID: 28854ceb52aa
Revises: 59bdf8b84d80
Create Date: 2026-11-09 03:35:16.874558

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers used by Alembic.
revision: str = "28854ceb52aa"
down_revision: Union[str, Sequence[str], None] = "59bdf8b84d80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


WORKFORCE_MEMBERSHIP_FK = (
    "fk_workforce_profiles_membership_id_memberships"
)


def upgrade() -> None:
    """Convert workforce profiles into standalone organization employees."""

    # Add the new required name field as nullable so existing records
    # can be populated before the NOT NULL constraint is applied.
    op.add_column(
        "workforce_profiles",
        sa.Column("full_name", sa.String(length=200), nullable=True),
    )

    # Backfill names only from a membership belonging to the same
    # organization as the workforce profile.
    op.execute(
        sa.text(
            """
            UPDATE workforce_profiles AS workforce
            SET full_name = NULLIF(
                BTRIM(
                    CONCAT_WS(
                        ' ',
                        NULLIF(BTRIM(users.first_name), ''),
                        NULLIF(BTRIM(users.last_name), '')
                    )
                ),
                ''
            )
            FROM memberships
            JOIN users
                ON users.id = memberships.user_id
            WHERE memberships.id = workforce.membership_id
              AND memberships.organization_id = workforce.organization_id
            """
        )
    )

    # Never invent employee names or silently discard unresolved records.
    unresolved_count = op.get_bind().execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM workforce_profiles
            WHERE full_name IS NULL
               OR BTRIM(full_name) = ''
            """
        )
    ).scalar_one()

    if unresolved_count:
        raise RuntimeError(
            "Workforce migration stopped: "
            f"{unresolved_count} existing workforce profile(s) "
            "could not be assigned a name from their linked user account. "
            "Resolve these records before retrying the migration."
        )

    op.alter_column(
        "workforce_profiles",
        "full_name",
        existing_type=sa.String(length=200),
        nullable=False,
    )

    # Membership is now an optional account link, not the employee identity.
    op.drop_constraint(
        WORKFORCE_MEMBERSHIP_FK,
        "workforce_profiles",
        type_="foreignkey",
    )

    op.alter_column(
        "workforce_profiles",
        "membership_id",
        existing_type=sa.UUID(),
        nullable=True,
    )

    op.create_foreign_key(
        WORKFORCE_MEMBERSHIP_FK,
        "workforce_profiles",
        "memberships",
        ["membership_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Remove constraints and fields that belonged to the old
    # membership-dependent employee model.

    op.drop_constraint(
        "uq_workforce_profiles_organization_employee_code",
        "workforce_profiles",
        type_="unique",
    )

    op.drop_column("workforce_profiles", "employee_code")
    op.drop_column("workforce_profiles", "joined_on")

    # Responsibility belongs to an employee's assignment to a particular
    # work order, not to the employee's organization-level profile.
    op.add_column(
        "work_order_workforce_assignments",
        sa.Column(
            "responsibility",
            sa.String(length=50),
            nullable=True,
        ),
    )

    op.add_column(
        "work_order_workforce_assignments",
        sa.Column(
            "custom_responsibility",
            sa.String(length=120),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Restore the previous membership-dependent workforce schema."""

    # A standalone employee cannot be represented by the old schema.
    # Stop before making any changes if such profiles exist.
    unlinked_count = op.get_bind().execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM workforce_profiles
            WHERE membership_id IS NULL
            """
        )
    ).scalar_one()

    if unlinked_count:
        raise RuntimeError(
            "Workforce migration downgrade stopped: "
            f"{unlinked_count} workforce profile(s) have no membership. "
            "Link or otherwise resolve these profiles before downgrading."
        )

    op.drop_column(
        "work_order_workforce_assignments",
        "custom_responsibility",
    )

    op.drop_column(
        "work_order_workforce_assignments",
        "responsibility",
    )

    # Reintroduce legacy fields. Their former values cannot be recovered.
    op.add_column(
        "workforce_profiles",
        sa.Column(
            "employee_code",
            sa.String(length=50),
            nullable=True,
        ),
    )

    op.add_column(
        "workforce_profiles",
        sa.Column(
            "joined_on",
            sa.Date(),
            nullable=True,
        ),
    )

    op.drop_constraint(
        WORKFORCE_MEMBERSHIP_FK,
        "workforce_profiles",
        type_="foreignkey",
    )

    op.alter_column(
        "workforce_profiles",
        "membership_id",
        existing_type=sa.UUID(),
        nullable=False,
    )

    op.create_foreign_key(
        WORKFORCE_MEMBERSHIP_FK,
        "workforce_profiles",
        "memberships",
        ["membership_id"],
        ["id"],
        ondelete="CASCADE",
    )


    op.create_unique_constraint(
        "uq_workforce_profiles_organization_employee_code",
        "workforce_profiles",
        ["organization_id", "employee_code"],
    )

    op.drop_column("workforce_profiles", "full_name")
