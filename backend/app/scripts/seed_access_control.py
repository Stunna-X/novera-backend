"""
Seed Novera's default roles, permissions, and role assignments.

Run from the backend directory with:

    python -m app.scripts.seed_access_control

The script is idempotent:
- Existing roles are reused.
- Existing permissions are reused.
- Existing role-permission links are not duplicated.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission


PERMISSIONS: dict[str, str] = {
    # Organizations
    "organizations.read": "View organization details.",
    "organizations.update": "Update organization details.",
    "organizations.deactivate": "Deactivate an organization.",

    # Memberships
    "memberships.read": "View organization members.",
    "memberships.create": "Add members to an organization.",
    "memberships.update": "Change member roles.",
    "memberships.delete": "Remove organization members.",

    # Roles
    "roles.read": "View available roles.",
    "roles.assign": "Assign roles to organization members.",

    # Customers
    "customers.read": "View customers.",
    "customers.create": "Create customers.",
    "customers.update": "Update customers.",
    "customers.delete": "Delete customers.",

    # Workforce
    "workforce.read": "View workforce members and teams.",
    "workforce.create": "Create workforce records.",
    "workforce.update": "Update workforce records.",
    "workforce.delete": "Delete workforce records.",

    # Assets
    "assets.read": "View equipment and assets.",
    "assets.create": "Create equipment and asset records.",
    "assets.update": "Update equipment and asset records.",
    "assets.delete": "Delete equipment and asset records.",

    # Projects
    "projects.read": "View projects.",
    "projects.create": "Create projects.",
    "projects.update": "Update projects.",
    "projects.delete": "Delete projects.",

    # Work orders
    "work_orders.read": "View work orders.",
    "work_orders.create": "Create work orders.",
    "work_orders.update": "Update work orders.",
    "work_orders.delete": "Delete work orders.",
    "work_orders.assign": "Assign work orders to field personnel.",
    "work_orders.update_status": "Update work-order status.",

    # Dashboard and reports
    "dashboard.read": "View the operations dashboard.",
    "reports.read": "View operational reports.",
    "reports.export": "Export operational reports.",
}


ROLE_DEFINITIONS: dict[str, dict[str, object]] = {
    "Owner": {
        "description": (
            "Full administrative control over an organization."
        ),
        "permissions": set(PERMISSIONS),
    },
    "Admin": {
        "description": (
            "Administrative access to organization settings, "
            "members, and operations."
        ),
        "permissions": set(PERMISSIONS),
    },
    "Operations Manager": {
        "description": (
            "Manages customers, teams, assets, projects, "
            "work orders, and operational reporting."
        ),
        "permissions": {
            "organizations.read",
            "organizations.update",
            "memberships.read",
            "memberships.create",
            "memberships.update",
            "roles.read",
            "roles.assign",
            "customers.read",
            "customers.create",
            "customers.update",
            "customers.delete",
            "workforce.read",
            "workforce.create",
            "workforce.update",
            "workforce.delete",
            "assets.read",
            "assets.create",
            "assets.update",
            "assets.delete",
            "projects.read",
            "projects.create",
            "projects.update",
            "projects.delete",
            "work_orders.read",
            "work_orders.create",
            "work_orders.update",
            "work_orders.delete",
            "work_orders.assign",
            "work_orders.update_status",
            "dashboard.read",
            "reports.read",
            "reports.export",
        },
    },
    "Supervisor": {
        "description": (
            "Supervises field operations and assigned work."
        ),
        "permissions": {
            "organizations.read",
            "memberships.read",
            "roles.read",
            "customers.read",
            "workforce.read",
            "assets.read",
            "projects.read",
            "work_orders.read",
            "work_orders.create",
            "work_orders.update",
            "work_orders.assign",
            "work_orders.update_status",
            "dashboard.read",
            "reports.read",
        },
    },
    "Technician": {
        "description": (
            "Views assigned field work and records job progress."
        ),
        "permissions": {
            "organizations.read",
            "assets.read",
            "projects.read",
            "work_orders.read",
            "work_orders.update_status",
        },
    },
    "Viewer": {
        "description": (
            "Read-only access to organization operations."
        ),
        "permissions": {
            "organizations.read",
            "memberships.read",
            "roles.read",
            "customers.read",
            "workforce.read",
            "assets.read",
            "projects.read",
            "work_orders.read",
            "dashboard.read",
            "reports.read",
        },
    },
}


def get_or_create_permission(
    db: Session,
    name: str,
    description: str,
) -> tuple[Permission, bool]:
    """
    Retrieve an existing permission or create it.
    """

    normalized_name = name.strip().lower()

    permission = (
        db.query(Permission)
        .filter(
            func.lower(Permission.name) == normalized_name
        )
        .first()
    )

    if permission is not None:
        if permission.description != description:
            permission.description = description

        return permission, False

    permission = Permission(
        name=normalized_name,
        description=description,
    )

    db.add(permission)
    db.flush()

    return permission, True


def get_or_create_role(
    db: Session,
    name: str,
    description: str,
) -> tuple[Role, bool]:
    """
    Retrieve an existing role or create it.
    """

    normalized_name = name.strip().lower()

    role = (
        db.query(Role)
        .filter(
            func.lower(Role.name) == normalized_name
        )
        .first()
    )

    if role is not None:
        role.description = description
        role.is_system = True

        return role, False

    role = Role(
        name=name.strip(),
        description=description,
        is_system=True,
    )

    db.add(role)
    db.flush()

    return role, True


def role_permission_exists(
    db: Session,
    role_id,
    permission_id,
) -> bool:
    """
    Check whether a role-permission assignment already exists.
    """

    return (
        db.query(RolePermission.id)
        .filter(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
        .first()
        is not None
    )


def seed_access_control() -> None:
    """
    Seed all standard roles, permissions, and assignments.
    """

    db = SessionLocal()

    created_permissions = 0
    created_roles = 0
    created_assignments = 0

    try:
        permission_records: dict[str, Permission] = {}

        for permission_name, description in PERMISSIONS.items():
            permission, created = get_or_create_permission(
                db=db,
                name=permission_name,
                description=description,
            )

            permission_records[permission_name] = permission

            if created:
                created_permissions += 1

        for role_name, definition in ROLE_DEFINITIONS.items():
            role, created = get_or_create_role(
                db=db,
                name=role_name,
                description=str(definition["description"]),
            )

            if created:
                created_roles += 1

            permission_names = definition["permissions"]

            if not isinstance(permission_names, set):
                raise TypeError(
                    f"Permissions for role '{role_name}' "
                    "must be stored as a set."
                )

            for permission_name in permission_names:
                permission = permission_records[
                    permission_name
                ]

                if role_permission_exists(
                    db=db,
                    role_id=role.id,
                    permission_id=permission.id,
                ):
                    continue

                assignment = RolePermission(
                    role_id=role.id,
                    permission_id=permission.id,
                )

                db.add(assignment)
                created_assignments += 1

        db.commit()

        print("Novera access-control seed completed.")
        print(f"Created permissions: {created_permissions}")
        print(f"Created roles: {created_roles}")
        print(
            "Created role-permission assignments: "
            f"{created_assignments}"
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_access_control()