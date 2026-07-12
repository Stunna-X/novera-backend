"""
Seed asset permissions.

Adds organization asset permissions and assigns them to
existing system roles without modifying earlier permissions.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import selectinload

import app.models  # noqa: F401
from app.database.session import SessionLocal
from app.models.permission import Permission
from app.models.role import Role


PERMISSIONS = {
    "assets.create": (
        "Create organization assets."
    ),
    "assets.read": (
        "View organization assets."
    ),
    "assets.update": (
        "Update organization assets."
    ),
    "assets.delete": (
        "Deactivate organization assets."
    ),
}


ROLE_PERMISSIONS = {
    "owner": set(PERMISSIONS),
    "admin": set(PERMISSIONS),
    "operations manager": set(PERMISSIONS),
    "supervisor": {
        "assets.read",
        "assets.update",
    },
    "technician": {
        "assets.read",
    },
    "viewer": {
        "assets.read",
    },
}


def seed_asset_access() -> None:
    """
    Create missing asset permissions and role assignments.
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
        "Asset access seeded successfully: "
        f"{created_permissions} permissions created, "
        f"{created_assignments} role assignments created."
    )


if __name__ == "__main__":
    seed_asset_access()