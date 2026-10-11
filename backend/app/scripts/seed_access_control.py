"""
Seed Novera's default roles, permissions, and role assignments.

Run from the backend directory with:

    python -m app.scripts.seed_access_control

The operation is idempotent.

System roles are synchronized to their canonical permission
definitions. Missing assignments are created and obsolete
assignments are removed.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.permission import Permission
from app.security.access_control import (
    PERMISSIONS,
    ROLE_DEFINITIONS,
    get_or_create_permission,
    get_or_create_role,
    synchronize_role_permissions,
)

def validate_definitions() -> None:
    """
    Validate the in-code permission and role catalogue.
    """

    normalized_permissions = {
        name.strip().lower()
        for name in PERMISSIONS
    }

    if len(normalized_permissions) != len(PERMISSIONS):
        raise ValueError(
            "Permission names must be unique after normalization."
        )

    for permission_name in PERMISSIONS:
        if permission_name != permission_name.strip().lower():
            raise ValueError(
                "Permission names must be lowercase and trimmed: "
                f"{permission_name!r}"
            )

    for role_name, definition in ROLE_DEFINITIONS.items():
        permission_names = definition.get("permissions")

        if not isinstance(permission_names, set):
            raise TypeError(
                f"Permissions for role {role_name!r} "
                "must be stored as a set."
            )

        unknown_permissions = (
            permission_names - set(PERMISSIONS)
        )

        if unknown_permissions:
            raise ValueError(
                f"Role {role_name!r} references undefined "
                "permissions: "
                + ", ".join(sorted(unknown_permissions))
            )


def seed_access_control() -> None:
    """
    Seed permissions and synchronize standard system roles.
    """

    validate_definitions()

    db = SessionLocal()

    created_permissions = 0
    updated_permissions = 0
    created_roles = 0
    updated_roles = 0
    created_assignments = 0
    removed_assignments = 0

    try:
        permission_records: dict[str, Permission] = {}

        for permission_name, description in PERMISSIONS.items():
            permission, created, updated = (
                get_or_create_permission(
                    db=db,
                    name=permission_name,
                    description=description,
                )
            )

            permission_records[permission_name] = permission

            if created:
                created_permissions += 1

            if updated:
                updated_permissions += 1

        for role_name, definition in ROLE_DEFINITIONS.items():
            role, created, updated = get_or_create_role(
                db=db,
                name=role_name,
                description=str(definition["description"]),
            )

            if created:
                created_roles += 1

            if updated:
                updated_roles += 1

            permission_names = definition["permissions"]

            if not isinstance(permission_names, set):
                raise TypeError(
                    f"Permissions for role {role_name!r} "
                    "must be stored as a set."
                )

            created_count, removed_count = (
                synchronize_role_permissions(
                    db=db,
                    role=role,
                    permission_names=permission_names,
                    permission_records=permission_records,
                )
            )

            created_assignments += created_count
            removed_assignments += removed_count

        db.commit()

        print("Novera access-control seed completed.")
        print(f"Created permissions: {created_permissions}")
        print(f"Updated permissions: {updated_permissions}")
        print(f"Created roles: {created_roles}")
        print(f"Updated roles: {updated_roles}")
        print(
            "Created role-permission assignments: "
            f"{created_assignments}"
        )
        print(
            "Removed obsolete role-permission assignments: "
            f"{removed_assignments}"
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_access_control()
