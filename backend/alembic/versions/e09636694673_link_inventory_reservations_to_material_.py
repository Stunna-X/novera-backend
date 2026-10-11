"""link inventory reservations to material requirements

Revision ID: e09636694673
Revises: 4a81a52cf50d
Create Date: 2026-09-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e09636694673"
down_revision: str | None = "4a81a52cf50d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "inventory_reservations",
        sa.Column(
            "work_order_material_requirement_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_inventory_reservations_material_requirement",
        "inventory_reservations",
        ["work_order_material_requirement_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_inventory_reservations_material_requirement",
        "inventory_reservations",
        "work_order_material_requirements",
        ["work_order_material_requirement_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_inventory_reservations_material_requirement",
        "inventory_reservations",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_inventory_reservations_material_requirement",
        table_name="inventory_reservations",
    )

    op.drop_column(
        "inventory_reservations",
        "work_order_material_requirement_id",
    )