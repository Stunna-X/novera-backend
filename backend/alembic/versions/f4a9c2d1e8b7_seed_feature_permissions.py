"""
Seed feature-specific permissions.

Revision ID: f4a9c2d1e8b7
Revises: e7c9a1b2d4f6
Create Date: 2026-07-17
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa


revision = "f4a9c2d1e8b7"
down_revision = "e7c9a1b2d4f6"
branch_labels = None
depends_on = None


PERMISSIONS = {
    "quotes.read": "Read quotes and quote activity.",
    "quotes.create": "Create quotes.",
    "quotes.update": "Update quote drafts and quote line items.",
    "quotes.respond": "Accept, reject, or expire quotes.",
    "quotes.convert": "Convert accepted quotes into work orders.",

    "scheduling.read": "Read scheduling calendar and conflicts.",
    "scheduling.update": "Schedule work orders.",
    "scheduling.dispatch": "Dispatch scheduled work orders.",

    "finance.invoices.read": "Read invoices and invoice summaries.",
    "finance.invoices.create": "Create invoices.",
    "finance.invoices.update": "Update draft invoices and invoice lines.",
    "finance.invoices.issue": "Issue invoices.",
    "finance.invoices.void": "Void invoices.",
    "finance.payments.record": "Record invoice payments.",
    "finance.payments.reverse": "Reverse invoice payments.",

    "dashboard.read": "Read dashboard analytics.",
    "reports.read": "Read business reports.",

    "notifications.read": "Read personal notifications.",
    "notifications.create": "Create notifications.",
    "notifications.update": "Mark notifications as read or archived.",

    "closeouts.read": "Read work-order closeouts.",
    "closeouts.create": "Submit work-order closeouts.",
    "closeouts.update": "Update work-order closeouts.",
    "closeouts.approve": "Approve work-order closeouts.",
    "closeouts.reject": "Reject work-order closeouts.",
    "closeouts.invoice_ready": "Mark closeouts invoice-ready.",

    "expenses.read": "Read work-order expenses.",
    "expenses.create": "Create work-order expenses.",
    "expenses.update": "Update work-order expenses.",
    "expenses.review": "Submit, approve, reject, or reopen expenses.",
    "expenses.delete": "Deactivate work-order expenses.",
}


ALL = set(PERMISSIONS)


ROLE_PERMISSIONS = {
    "owner": ALL,
    "admin": ALL,
    "operations manager": ALL,
    "supervisor": {
        "quotes.read",
        "scheduling.read",
        "scheduling.update",
        "scheduling.dispatch",
        "dashboard.read",
        "reports.read",
        "notifications.read",
        "notifications.update",
        "closeouts.read",
        "closeouts.create",
        "closeouts.update",
        "closeouts.approve",
        "closeouts.reject",
        "closeouts.invoice_ready",
        "expenses.read",
        "expenses.create",
        "expenses.update",
        "expenses.review",
        "expenses.delete",
    },
    "technician": {
        "scheduling.read",
        "dashboard.read",
        "notifications.read",
        "notifications.update",
        "closeouts.read",
        "closeouts.create",
        "closeouts.update",
        "expenses.read",
        "expenses.create",
        "expenses.update",
    },
    "viewer": {
        "quotes.read",
        "scheduling.read",
        "finance.invoices.read",
        "dashboard.read",
        "reports.read",
        "notifications.read",
        "notifications.update",
        "closeouts.read",
        "expenses.read",
    },
}


def upgrade() -> None:
    bind = op.get_bind()

    for name, description in PERMISSIONS.items():
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
                "name": name,
                "description": description,
            },
        )

    for role_name, permission_names in ROLE_PERMISSIONS.items():
        for permission_name in sorted(permission_names):
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
                    "permission_name": permission_name,
                },
            )


def downgrade() -> None:
    bind = op.get_bind()

    permission_names = list(PERMISSIONS)

    bind.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            USING permissions
            WHERE role_permissions.permission_id = permissions.id
            AND permissions.name = ANY(:permission_names)
            """
        ),
        {
            "permission_names": permission_names,
        },
    )

    bind.execute(
        sa.text(
            """
            DELETE FROM permissions
            WHERE name = ANY(:permission_names)
            """
        ),
        {
            "permission_names": permission_names,
        },
    )
