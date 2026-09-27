"""remove redundant shortage allowance indexes

Revision ID: 9ede11974082
Revises: c23e4a2568e2
Create Date: 2026-09-27
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "9ede11974082"
down_revision = "c23e4a2568e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(
        "ix_shortage_allowance_org",
        table_name="work_order_material_shortage_allowances",
    )
    op.drop_index(
        "ix_shortage_allowance_requirement",
        table_name="work_order_material_shortage_allowances",
    )
    op.drop_index(
        "ix_shortage_allowance_status",
        table_name="work_order_material_shortage_allowances",
    )
    op.drop_index(
        "ix_shortage_allowance_active",
        table_name="work_order_material_shortage_allowances",
    )


def downgrade() -> None:
    op.create_index(
        "ix_shortage_allowance_org",
        "work_order_material_shortage_allowances",
        ["organization_id"],
    )
    op.create_index(
        "ix_shortage_allowance_requirement",
        "work_order_material_shortage_allowances",
        ["work_order_material_requirement_id"],
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
