"""
Create quotes, quote line items, and quote activities.

Revision ID: b7a4d2e91c63
Revises: 82f6d9e4a1b2
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "b7a4d2e91c63"
down_revision: str | None = "82f6d9e4a1b2"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """
    Create quote and estimate tables.
    """

    op.create_table(
        "quotes",
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "customer_site_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "converted_work_order_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "sent_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "responded_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "converted_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "quote_number",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=200),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default="NGN",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "quote_date",
            sa.Date(),
            nullable=False,
        ),
        sa.Column(
            "valid_until",
            sa.Date(),
            nullable=True,
        ),
        sa.Column(
            "subtotal",
            sa.Numeric(precision=14, scale=2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column(
            "discount_amount",
            sa.Numeric(precision=14, scale=2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column(
            "tax_amount",
            sa.Numeric(precision=14, scale=2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column(
            "total_amount",
            sa.Numeric(precision=14, scale=2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column(
            "customer_name",
            sa.String(length=200),
            nullable=False,
        ),
        sa.Column(
            "customer_email",
            sa.String(length=320),
            nullable=True,
        ),
        sa.Column(
            "customer_phone",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "billing_address",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "service_address",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "terms",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "rejected_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "expired_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "converted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "response_note",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
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
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            """
            status IN (
                'draft',
                'sent',
                'accepted',
                'rejected',
                'expired',
                'converted'
            )
            """,
            name="ck_quotes_status_valid",
        ),
        sa.CheckConstraint(
            "char_length(currency) = 3",
            name="ck_quotes_currency_length",
        ),
        sa.CheckConstraint(
            "subtotal >= 0",
            name="ck_quotes_subtotal_non_negative",
        ),
        sa.CheckConstraint(
            "discount_amount >= 0",
            name="ck_quotes_discount_non_negative",
        ),
        sa.CheckConstraint(
            "tax_amount >= 0",
            name="ck_quotes_tax_non_negative",
        ),
        sa.CheckConstraint(
            "total_amount >= 0",
            name="ck_quotes_total_non_negative",
        ),
        sa.CheckConstraint(
            """
            valid_until IS NULL
            OR valid_until >= quote_date
            """,
            name="ck_quotes_valid_until_valid",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_site_id"],
            ["customer_sites.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["converted_work_order_id"],
            ["work_orders.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["sent_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["responded_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["converted_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_quotes",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "quote_number",
            name="uq_quotes_organization_number",
        ),
        sa.UniqueConstraint(
            "converted_work_order_id",
            name="uq_quotes_converted_work_order_id",
        ),
    )

    quote_indexes = [
        ("ix_quotes_organization_status", ["organization_id", "status"]),
        ("ix_quotes_organization_customer", ["organization_id", "customer_id"]),
        ("ix_quotes_organization_site", ["organization_id", "customer_site_id"]),
        ("ix_quotes_organization_currency", ["organization_id", "currency"]),
        ("ix_quotes_organization_valid_until", ["organization_id", "valid_until"]),
        ("ix_quotes_organization_active", ["organization_id", "is_active"]),
        ("ix_quotes_organization_id", ["organization_id"]),
        ("ix_quotes_customer_id", ["customer_id"]),
        ("ix_quotes_customer_site_id", ["customer_site_id"]),
        ("ix_quotes_converted_work_order_id", ["converted_work_order_id"]),
        ("ix_quotes_created_by_user_id", ["created_by_user_id"]),
        ("ix_quotes_sent_by_user_id", ["sent_by_user_id"]),
        ("ix_quotes_responded_by_user_id", ["responded_by_user_id"]),
        ("ix_quotes_converted_by_user_id", ["converted_by_user_id"]),
        ("ix_quotes_currency", ["currency"]),
        ("ix_quotes_status", ["status"]),
        ("ix_quotes_quote_date", ["quote_date"]),
        ("ix_quotes_valid_until", ["valid_until"]),
        ("ix_quotes_is_active", ["is_active"]),
    ]

    for index_name, columns in quote_indexes:
        op.create_index(
            index_name,
            "quotes",
            columns,
            unique=False,
        )

    op.create_table(
        "quote_line_items",
        sa.Column(
            "quote_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column(
            "quantity",
            sa.Numeric(precision=14, scale=3),
            server_default="1.000",
            nullable=False,
        ),
        sa.Column(
            "unit_price",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
        ),
        sa.Column(
            "line_total",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.Integer(),
            server_default="0",
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
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_quote_line_items_quantity_positive",
        ),
        sa.CheckConstraint(
            "unit_price >= 0",
            name="ck_quote_line_items_unit_price_non_negative",
        ),
        sa.CheckConstraint(
            "line_total >= 0",
            name="ck_quote_line_items_total_non_negative",
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_quote_line_items_position_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["quote_id"],
            ["quotes.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_quote_line_items",
        ),
        sa.UniqueConstraint(
            "quote_id",
            "position",
            name="uq_quote_line_items_quote_position",
        ),
    )

    line_indexes = [
        ("ix_quote_line_items_quote_active", ["quote_id", "is_active"]),
        ("ix_quote_line_items_quote_id", ["quote_id"]),
        ("ix_quote_line_items_is_active", ["is_active"]),
    ]

    for index_name, columns in line_indexes:
        op.create_index(
            index_name,
            "quote_line_items",
            columns,
            unique=False,
        )

    op.create_table(
        "quote_activities",
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "quote_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "activity_type",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "summary",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "from_status",
            sa.String(length=30),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            sa.String(length=30),
            nullable=True,
        ),
        sa.Column(
            "note",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
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
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["quote_id"],
            ["quotes.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_quote_activities",
        ),
    )

    activity_indexes = [
        ("ix_quote_activities_organization_quote", ["organization_id", "quote_id"]),
        ("ix_quote_activities_quote_created", ["quote_id", "created_at"]),
        ("ix_quote_activities_organization_type", ["organization_id", "activity_type"]),
        ("ix_quote_activities_organization_id", ["organization_id"]),
        ("ix_quote_activities_quote_id", ["quote_id"]),
        ("ix_quote_activities_actor_user_id", ["actor_user_id"]),
        ("ix_quote_activities_activity_type", ["activity_type"]),
    ]

    for index_name, columns in activity_indexes:
        op.create_index(
            index_name,
            "quote_activities",
            columns,
            unique=False,
        )


def downgrade() -> None:
    """
    Remove quote and estimate tables.
    """

    activity_indexes = [
        "ix_quote_activities_activity_type",
        "ix_quote_activities_actor_user_id",
        "ix_quote_activities_quote_id",
        "ix_quote_activities_organization_id",
        "ix_quote_activities_organization_type",
        "ix_quote_activities_quote_created",
        "ix_quote_activities_organization_quote",
    ]

    for index_name in activity_indexes:
        op.drop_index(
            index_name,
            table_name="quote_activities",
        )

    op.drop_table("quote_activities")

    line_indexes = [
        "ix_quote_line_items_is_active",
        "ix_quote_line_items_quote_id",
        "ix_quote_line_items_quote_active",
    ]

    for index_name in line_indexes:
        op.drop_index(
            index_name,
            table_name="quote_line_items",
        )

    op.drop_table("quote_line_items")

    quote_indexes = [
        "ix_quotes_is_active",
        "ix_quotes_valid_until",
        "ix_quotes_quote_date",
        "ix_quotes_status",
        "ix_quotes_currency",
        "ix_quotes_converted_by_user_id",
        "ix_quotes_responded_by_user_id",
        "ix_quotes_sent_by_user_id",
        "ix_quotes_created_by_user_id",
        "ix_quotes_converted_work_order_id",
        "ix_quotes_customer_site_id",
        "ix_quotes_customer_id",
        "ix_quotes_organization_id",
        "ix_quotes_organization_active",
        "ix_quotes_organization_valid_until",
        "ix_quotes_organization_currency",
        "ix_quotes_organization_site",
        "ix_quotes_organization_customer",
        "ix_quotes_organization_status",
    ]

    for index_name in quote_indexes:
        op.drop_index(
            index_name,
            table_name="quotes",
        )

    op.drop_table("quotes")