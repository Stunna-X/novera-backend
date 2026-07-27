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
    "memberships.update": "Change organization memberships.",
    "memberships.delete": "Remove organization members.",

    # Roles
    "roles.read": "View available roles.",
    "roles.assign": "Assign roles to organization members.",

    # Customers
    "customers.read": "View customers and customer sites.",
    "customers.create": "Create customers and customer sites.",
    "customers.update": "Update customers and customer sites.",
    "customers.delete": "Delete customers and customer sites.",

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

    # Inventory
    "inventory.read": (
        "View inventory locations, items, balances, and stock alerts."
    ),
    "inventory.create": (
        "Create inventory locations and catalogue items."
    ),
    "inventory.update": (
        "Update inventory locations and catalogue items."
    ),
    "inventory.delete": (
        "Deactivate inventory locations and catalogue items."
    ),

    # Suppliers
    "suppliers.read": "View organization suppliers.",
    "suppliers.create": "Create organization suppliers.",
    "suppliers.update": "Update organization suppliers.",
    "suppliers.delete": "Deactivate organization suppliers.",

    # Purchase requisitions
    "purchase_requisitions.read": (
        "View organization purchase requisitions."
    ),
    "purchase_requisitions.create": (
        "Create organization purchase requisitions."
    ),
    "purchase_requisitions.update": (
        "Update draft or rejected purchase requisitions."
    ),
    "purchase_requisitions.submit": (
        "Submit purchase requisitions for approval."
    ),
    "purchase_requisitions.approve": (
        "Approve or reject submitted purchase requisitions."
    ),
    "purchase_requisitions.cancel": (
        "Cancel eligible purchase requisitions."
    ),

    # Purchase orders
    "purchase_orders.read": (
        "View organization purchase orders."
    ),
    "purchase_orders.create": (
        "Create purchase orders manually or from approved requisitions."
    ),
    "purchase_orders.update": (
        "Update draft purchase orders and line items."
    ),
    "purchase_orders.issue": (
        "Issue purchase orders to suppliers."
    ),
    "purchase_orders.acknowledge": (
        "Record supplier acknowledgement of issued purchase orders."
    ),
    "purchase_orders.cancel": (
        "Cancel eligible purchase orders."
    ),
    "purchase_orders.close": (
        "Close fully received purchase orders."
    ),

    # Goods receipts
    "goods_receipts.read": (
        "View organization goods receipts."
    ),
    "goods_receipts.create": (
        "Create draft goods receipts against purchase orders."
    ),
    "goods_receipts.update": (
        "Update draft goods receipts and line items."
    ),
    "goods_receipts.post": (
        "Post goods receipts and accepted stock atomically."
    ),
    "goods_receipts.cancel": (
        "Cancel draft goods receipts."
    ),

    # Supplier bills and three-way matching
    "supplier_bills.read": (
        "View supplier bills and persisted match results."
    ),
    "supplier_bills.create": (
        "Create draft supplier bills against purchase orders."
    ),
    "supplier_bills.update": (
        "Update draft supplier bills and line items."
    ),
    "supplier_bills.submit": (
        "Submit supplier bills for three-way matching."
    ),
    "supplier_bills.match": (
        "Run purchase-order and goods-receipt matching."
    ),
    "supplier_bills.approve": (
        "Approve matched bills or documented exceptions."
    ),
    "supplier_bills.void": (
        "Void supplier bills while retaining audit history."
    ),

    # Supplier payments and accounts payable
    "supplier_payments.read": (
        "View supplier payments and approved bill balances."
    ),
    "supplier_payments.create": (
        "Post and allocate payments to approved supplier bills."
    ),
    "supplier_payments.reverse": (
        "Reverse supplier payments while retaining audit history."
    ),

    # Procurement analytics
    "procurement_analytics.read": (
        "View tenant-scoped procurement, spend, and payable analytics."
    ),

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
    "work_orders.status": "Update work-order status.",

    # Scheduling
    "scheduling.read": "View schedules and dispatch information.",
    "scheduling.update": "Update work-order schedules.",
    "scheduling.dispatch": "Dispatch scheduled field work.",

    # Work-order closeouts
    "closeouts.read": "View work-order closeout records.",
    "closeouts.create": "Create work-order closeout records.",
    "closeouts.update": "Update work-order closeout records.",
    "closeouts.approve": "Approve work-order closeouts.",
    "closeouts.reject": "Reject work-order closeouts.",
    "closeouts.invoice_ready": (
        "Mark approved closeouts as ready for invoicing."
    ),

    # Expenses
    "expenses.read": "View work-order expenses.",
    "expenses.create": "Create work-order expenses.",
    "expenses.update": "Update work-order expenses.",
    "expenses.delete": "Delete work-order expenses.",
    "expenses.review": "Approve or reject work-order expenses.",

    # Notifications
    "notifications.read": "View organization notifications.",
    "notifications.create": "Create organization notifications.",
    "notifications.update": (
        "Update, read, archive, or dismiss notifications."
    ),

    # Quotes
    "quotes.read": "View quotes and quote activity.",
    "quotes.create": "Create quotes.",
    "quotes.update": "Update quote records and line items.",
    "quotes.respond": (
        "Send, accept, reject, or expire quotes."
    ),

    # Finance
    "finance.invoices.read": "View invoices and payments.",
    "finance.invoices.create": "Create invoices.",
    "finance.invoices.update": (
        "Update invoice records and line items."
    ),
    "finance.invoices.issue": "Issue invoices to customers.",
    "finance.invoices.void": "Void issued invoices.",
    "finance.payments.record": (
        "Record payments against invoices."
    ),
    "finance.payments.reverse": (
        "Reverse previously recorded invoice payments."
    ),

    # Document delivery
    "document_deliveries.read": (
        "View document-delivery history and status."
    ),
    "document_deliveries.send": (
        "Queue invoices and quotes for customer delivery."
    ),

    # Email outbox
    "email_outbox.read": (
        "View queued and processed outbound email records."
    ),
    "email_outbox.manage": (
        "Retry or manually reconcile outbound email records."
    ),

    # Dashboard, reports, and audit
    "dashboard.read": "View the operations dashboard.",
    "reports.read": "View operational reports.",
    "reports.export": "Export operational reports.",
    "audit_logs.read": "View and export organization audit logs.",
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
            "members, finance, and operations."
        ),
        "permissions": set(PERMISSIONS),
    },
    "Operations Manager": {
        "description": (
            "Manages customers, field teams, assets, work orders, "
            "scheduling, closeouts, finance, and reporting."
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
            "inventory.read",
            "inventory.create",
            "inventory.update",
            "inventory.delete",
            "suppliers.read",
            "suppliers.create",
            "suppliers.update",
            "suppliers.delete",
            "purchase_requisitions.read",
            "purchase_requisitions.create",
            "purchase_requisitions.update",
            "purchase_requisitions.submit",
            "purchase_requisitions.approve",
            "purchase_requisitions.cancel",
            "purchase_orders.read",
            "purchase_orders.create",
            "purchase_orders.update",
            "purchase_orders.issue",
            "purchase_orders.acknowledge",
            "purchase_orders.cancel",
            "purchase_orders.close",
            "goods_receipts.read",
            "goods_receipts.create",
            "goods_receipts.update",
            "goods_receipts.post",
            "goods_receipts.cancel",
            "supplier_bills.read",
            "supplier_bills.create",
            "supplier_bills.update",
            "supplier_bills.submit",
            "supplier_bills.match",
            "supplier_bills.approve",
            "supplier_bills.void",
            "supplier_payments.read",
            "supplier_payments.create",
            "supplier_payments.reverse",
            "procurement_analytics.read",
            "projects.read",
            "projects.create",
            "projects.update",
            "projects.delete",
            "work_orders.read",
            "work_orders.create",
            "work_orders.update",
            "work_orders.delete",
            "work_orders.assign",
            "work_orders.status",
            "scheduling.read",
            "scheduling.update",
            "scheduling.dispatch",
            "closeouts.read",
            "closeouts.create",
            "closeouts.update",
            "closeouts.approve",
            "closeouts.reject",
            "closeouts.invoice_ready",
            "expenses.read",
            "expenses.create",
            "expenses.update",
            "expenses.delete",
            "expenses.review",
            "notifications.read",
            "notifications.create",
            "notifications.update",
            "quotes.read",
            "quotes.create",
            "quotes.update",
            "quotes.respond",
            "finance.invoices.read",
            "finance.invoices.create",
            "finance.invoices.update",
            "finance.invoices.issue",
            "finance.invoices.void",
            "finance.payments.record",
            "finance.payments.reverse",
            "document_deliveries.read",
            "document_deliveries.send",
            "email_outbox.read",
            "email_outbox.manage",
            "dashboard.read",
            "reports.read",
            "reports.export",
            "audit_logs.read",
        },
    },
    "Supervisor": {
        "description": (
            "Supervises field operations, dispatch, closeouts, "
            "expenses, quotes, and assigned work."
        ),
        "permissions": {
            "organizations.read",
            "memberships.read",
            "roles.read",
            "customers.read",
            "workforce.read",
            "assets.read",
            "inventory.read",
            "inventory.create",
            "inventory.update",
            "suppliers.read",
            "purchase_requisitions.read",
            "purchase_requisitions.create",
            "purchase_requisitions.update",
            "purchase_requisitions.submit",
            "purchase_requisitions.cancel",
            "purchase_orders.read",
            "purchase_orders.create",
            "purchase_orders.update",
            "purchase_orders.acknowledge",
            "goods_receipts.read",
            "goods_receipts.create",
            "goods_receipts.update",
            "goods_receipts.post",
            "supplier_bills.read",
            "supplier_bills.create",
            "supplier_bills.update",
            "supplier_bills.submit",
            "supplier_bills.match",
            "supplier_payments.read",
            "supplier_payments.create",
            "procurement_analytics.read",
            "projects.read",
            "work_orders.read",
            "work_orders.create",
            "work_orders.update",
            "work_orders.assign",
            "work_orders.status",
            "scheduling.read",
            "scheduling.update",
            "scheduling.dispatch",
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
            "notifications.read",
            "notifications.create",
            "notifications.update",
            "quotes.read",
            "quotes.create",
            "quotes.update",
            "quotes.respond",
            "finance.invoices.read",
            "document_deliveries.read",
            "document_deliveries.send",
            "email_outbox.read",
            "dashboard.read",
            "reports.read",
            "audit_logs.read",
        },
    },
    "Technician": {
        "description": (
            "Views assigned field work and records job progress, "
            "closeout information, and field expenses."
        ),
        "permissions": {
            "organizations.read",
            "assets.read",
            "inventory.read",
            "projects.read",
            "work_orders.read",
            "work_orders.status",
            "scheduling.read",
            "closeouts.read",
            "closeouts.create",
            "closeouts.update",
            "expenses.read",
            "expenses.create",
            "expenses.update",
            "notifications.read",
            "notifications.update",
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
            "inventory.read",
            "suppliers.read",
            "purchase_requisitions.read",
            "purchase_orders.read",
            "goods_receipts.read",
            "supplier_bills.read",
            "supplier_payments.read",
            "procurement_analytics.read",
            "projects.read",
            "work_orders.read",
            "scheduling.read",
            "closeouts.read",
            "expenses.read",
            "notifications.read",
            "quotes.read",
            "finance.invoices.read",
            "document_deliveries.read",
            "dashboard.read",
            "reports.read",
        },
    },
}


def get_or_create_permission(
    db: Session,
    name: str,
    description: str,
) -> tuple[Permission, bool, bool]:
    """
    Retrieve or create a permission.

    Returns the permission plus created and updated flags.
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
        updated = False

        if permission.name != normalized_name:
            permission.name = normalized_name
            updated = True

        if permission.description != description:
            permission.description = description
            updated = True

        return permission, False, updated

    permission = Permission(
        name=normalized_name,
        description=description,
    )

    db.add(permission)
    db.flush()

    return permission, True, False


def get_or_create_role(
    db: Session,
    name: str,
    description: str,
) -> tuple[Role, bool, bool]:
    """
    Retrieve or create a canonical system role.
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
        updated = False

        if role.name != name.strip():
            role.name = name.strip()
            updated = True

        if role.description != description:
            role.description = description
            updated = True

        if not role.is_system:
            role.is_system = True
            updated = True

        return role, False, updated

    role = Role(
        name=name.strip(),
        description=description,
        is_system=True,
    )

    db.add(role)
    db.flush()

    return role, True, False


def synchronize_role_permissions(
    *,
    db: Session,
    role: Role,
    permission_names: set[str],
    permission_records: dict[str, Permission],
) -> tuple[int, int]:
    """
    Synchronize one system role to its canonical permissions.

    Returns created and removed assignment counts.
    """

    unknown_permissions = (
        permission_names - set(permission_records)
    )

    if unknown_permissions:
        raise ValueError(
            "Role references undefined permissions: "
            + ", ".join(sorted(unknown_permissions))
        )

    desired_permission_ids = {
        permission_records[name].id
        for name in permission_names
    }

    existing_assignments = (
        db.query(RolePermission)
        .filter(
            RolePermission.role_id == role.id
        )
        .all()
    )

    existing_by_permission_id = {
        assignment.permission_id: assignment
        for assignment in existing_assignments
    }

    created_count = 0
    removed_count = 0

    for permission_id, assignment in (
        existing_by_permission_id.items()
    ):
        if permission_id in desired_permission_ids:
            continue

        db.delete(assignment)
        removed_count += 1

    for permission_id in desired_permission_ids:
        if permission_id in existing_by_permission_id:
            continue

        db.add(
            RolePermission(
                role_id=role.id,
                permission_id=permission_id,
            )
        )

        created_count += 1

    return created_count, removed_count


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
