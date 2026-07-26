"""
Seed work-order permissions.

Adds work-order permissions and assigns them to existing
system roles.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import selectinload

import app.models  # noqa: F401
from app.database.session import SessionLocal
from app.models.permission import Permission
from app.models.role import Role


PERMISSIONS = {
    "work_orders.create": (
        "Create organization work orders."
    ),
    "work_orders.read": (
        "View organization work orders."
    ),
    "work_orders.update": (
        "Update work-order details."
    ),
    "work_orders.status": (
        "Change work-order operational status."
    ),
    "work_orders.assign": (
        "Assign workforce and assets to work orders."
    ),
    "work_orders.delete": (
        "Deactivate work orders."
    ),
}


ROLE_PERMISSIONS = {
    "owner": set(PERMISSIONS),
    "admin": set(PERMISSIONS),
    "operations manager": set(PERMISSIONS),
    "supervisor": {
        "work_orders.create",
        "work_orders.read",
        "work_orders.update",
        "work_orders.status",
        "work_orders.assign",
    },
    "technician": {
        "work_orders.read",
    },
    "viewer": {
        "work_orders.read",
    },
}


def seed_work_order_access() -> None:
    """
    Create missing work-order permissions and assignments.
    """

    created_permissions = 0
    created_assignments = 0

    with SessionLocal() as db:
        permissions_by_name: dict[str, Permission] = {}

        for permission_name, description in PERMISSIONS.items():
            permission = (
                db.query(Permission)
                .filter(
                    func.lower(Permission.name)
                    == permission_name.lower()
                )
                .first()
            )

            if permission is None:
                permission = Permission(
                    name=permission_name,
                    description=description,
                )

                db.add(permission)
                db.flush()

                created_permissions += 1

            permissions_by_name[
                permission_name
            ] = permission

        roles = (
            db.query(Role)
            .options(
                selectinload(Role.permissions)
            )
            .all()
        )

        roles_by_name = {
            role.name.strip().lower(): role
            for role in roles
        }

        for role_name, permission_names in ROLE_PERMISSIONS.items():
            role = roles_by_name.get(
                role_name
            )

            if role is None:
                continue

            existing_permission_names = {
                permission.name.strip().lower()
                for permission in role.permissions
            }

            for permission_name in permission_names:
                if (
                    permission_name.lower()
                    in existing_permission_names
                ):
                    continue

                role.permissions.append(
                    permissions_by_name[
                        permission_name
                    ]
                )

                existing_permission_names.add(
                    permission_name.lower()
                )

                created_assignments += 1

        db.commit()

    print(
        "Work-order access seeded successfully: "
        f"{created_permissions} permissions created, "
        f"{created_assignments} role assignments created."
    )


if __name__ == "__main__":
    seed_work_order_access()