"""
SQLAlchemy model registry.

Importing models here ensures that all database tables are
registered in SQLAlchemy metadata and detected by Alembic.
"""

from app.models.asset import Asset
from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.customer_site import CustomerSite
from app.models.invoice import (
    Invoice,
    InvoiceLineItem,
    InvoicePayment,
)
from app.models.membership import Membership
from app.models.notification import Notification
from app.models.organization import Organization
from app.models.permission import Permission
from app.models.quote import (
    Quote,
    QuoteActivity,
    QuoteLineItem,
)
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User
from app.models.work_order import (
    WorkOrder,
    WorkOrderAssetAssignment,
    WorkOrderWorkforceAssignment,
)
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_checklist import (
    WorkOrderChecklistItem,
)
from app.models.work_order_closeout import WorkOrderCloseout
from app.models.work_order_expense import WorkOrderExpense
from app.models.work_order_note import (
    WorkOrderNote,
    WorkOrderNoteAttachment,
)
from app.models.workforce_profile import WorkforceProfile


__all__ = [
    "Asset",
    "AuditLog",
    "Customer",
    "CustomerSite",
    "Invoice",
    "InvoiceLineItem",
    "InvoicePayment",
    "Membership",
    "Notification",
    "Organization",
    "Permission",
    "Quote",
    "QuoteActivity",
    "QuoteLineItem",
    "RefreshToken",
    "Role",
    "RolePermission",
    "User",
    "WorkOrder",
    "WorkOrderActivity",
    "WorkOrderAssetAssignment",
    "WorkOrderChecklistItem",
    "WorkOrderCloseout",
    "WorkOrderExpense",
    "WorkOrderNote",
    "WorkOrderNoteAttachment",
    "WorkOrderWorkforceAssignment",
    "WorkforceProfile",
]
from app.models.document_delivery import DocumentDelivery
