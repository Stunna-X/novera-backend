"""Add organization document settings.

Revision ID: b1c7d9e2f4a6
Revises: a8c5e7d9f2b4
Create Date: 2026-07-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b1c7d9e2f4a6"
down_revision = "a8c5e7d9f2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("business_address", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("tax_identification_number", sa.String(length=100), nullable=True))
    op.add_column("organizations", sa.Column("vat_number", sa.String(length=100), nullable=True))
    op.add_column("organizations", sa.Column("bank_name", sa.String(length=200), nullable=True))
    op.add_column("organizations", sa.Column("bank_account_name", sa.String(length=200), nullable=True))
    op.add_column("organizations", sa.Column("bank_account_number", sa.String(length=100), nullable=True))
    op.add_column("organizations", sa.Column("bank_routing_number", sa.String(length=100), nullable=True))
    op.add_column("organizations", sa.Column("payment_instructions", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("default_invoice_terms", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("default_quote_terms", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("invoice_footer", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("quote_footer", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "quote_footer")
    op.drop_column("organizations", "invoice_footer")
    op.drop_column("organizations", "default_quote_terms")
    op.drop_column("organizations", "default_invoice_terms")
    op.drop_column("organizations", "payment_instructions")
    op.drop_column("organizations", "bank_routing_number")
    op.drop_column("organizations", "bank_account_number")
    op.drop_column("organizations", "bank_account_name")
    op.drop_column("organizations", "bank_name")
    op.drop_column("organizations", "vat_number")
    op.drop_column("organizations", "tax_identification_number")
    op.drop_column("organizations", "business_address")
