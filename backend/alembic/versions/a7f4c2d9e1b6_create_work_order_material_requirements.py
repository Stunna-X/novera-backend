"""create work order material requirements

Revision ID: a7f4c2d9e1b6
Revises: 9904ee90efde
Create Date: 2026-08-03 15:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a7f4c2d9e1b6"
down_revision: Union[str, Sequence[str], None] = (
    "9904ee90efde"
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "work_order_material_requirements",
        sa.Column(
            "organization_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "work_order_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "inventory_item_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "required_quantity",
            sa.Numeric(precision=16, scale=3),
            nullable=False,
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "position",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "updated_by_user_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.UUID(),
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
        sa.CheckConstraint(
            "position >= 0",
            name=op.f(
                "ck_work_order_material_requirements_position_non_negative"
            ),
        ),
        sa.CheckConstraint(
            "required_quantity > 0",
            name=op.f(
                "ck_work_order_material_requirements_required_quantity_positive"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f(
                "fk_work_order_material_requirements_created_by_user_id_users"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["inventory_item_id"],
            ["inventory_items.id"],
            name=op.f(
                "fk_work_order_material_requirements_inventory_item_id_inventory_items"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f(
                "fk_work_order_material_requirements_organization_id_organizations"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f(
                "fk_work_order_material_requirements_updated_by_user_id_users"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["work_orders.id"],
            name=op.f(
                "fk_work_order_material_requirements_work_order_id_work_orders"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f(
                "pk_work_order_material_requirements"
            ),
        ),
        sa.UniqueConstraint(
            "work_order_id",
            "inventory_item_id",
            name=(
                "uq_work_order_material_requirements_item"
            ),
        ),
    )

    op.create_index(
        op.f(
            "ix_work_order_material_requirements_created_by_user_id"
        ),
        "work_order_material_requirements",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f(
            "ix_work_order_material_requirements_inventory_item_id"
        ),
        "work_order_material_requirements",
        ["inventory_item_id"],
        unique=False,
    )
    op.create_index(
        op.f(
            "ix_work_order_material_requirements_is_active"
        ),
        "work_order_material_requirements",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f(
            "ix_work_order_material_requirements_organization_id"
        ),
        "work_order_material_requirements",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f(
            "ix_work_order_material_requirements_updated_by_user_id"
        ),
        "work_order_material_requirements",
        ["updated_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f(
            "ix_work_order_material_requirements_work_order_id"
        ),
        "work_order_material_requirements",
        ["work_order_id"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_material_requirements_org_work_order",
        "work_order_material_requirements",
        ["organization_id", "work_order_id"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_material_requirements_organization_item",
        "work_order_material_requirements",
        ["organization_id", "inventory_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_material_requirements_work_order_active",
        "work_order_material_requirements",
        ["work_order_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_work_order_material_requirements_work_order_position",
        "work_order_material_requirements",
        ["work_order_id", "position"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_work_order_material_requirements_work_order_position",
        table_name="work_order_material_requirements",
    )
    op.drop_index(
        "ix_work_order_material_requirements_work_order_active",
        table_name="work_order_material_requirements",
    )
    op.drop_index(
        "ix_work_order_material_requirements_organization_item",
        table_name="work_order_material_requirements",
    )
    op.drop_index(
        "ix_work_order_material_requirements_org_work_order",
        table_name="work_order_material_requirements",
    )
    op.drop_index(
        op.f(
            "ix_work_order_material_requirements_work_order_id"
        ),
        table_name="work_order_material_requirements",
    )
    op.drop_index(
        op.f(
            "ix_work_order_material_requirements_updated_by_user_id"
        ),
        table_name="work_order_material_requirements",
    )
    op.drop_index(
        op.f(
            "ix_work_order_material_requirements_organization_id"
        ),
        table_name="work_order_material_requirements",
    )
    op.drop_index(
        op.f(
            "ix_work_order_material_requirements_is_active"
        ),
        table_name="work_order_material_requirements",
    )
    op.drop_index(
        op.f(
            "ix_work_order_material_requirements_inventory_item_id"
        ),
        table_name="work_order_material_requirements",
    )
    op.drop_index(
        op.f(
            "ix_work_order_material_requirements_created_by_user_id"
        ),
        table_name="work_order_material_requirements",
    )
    op.drop_table("work_order_material_requirements")
