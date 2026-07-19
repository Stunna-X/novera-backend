"""
API Router Aggregator.

Every Version 1 endpoint is registered here.
"""

from fastapi import APIRouter

from app.api.v1.assets.router import router as asset_router
from app.api.v1.audit_logs.router import (
    router as audit_log_router,
)
from app.api.v1.auth.router import router as auth_router
from app.api.v1.customer_sites.router import (
    router as customer_site_router,
)
from app.api.v1.customers.router import router as customer_router
from app.api.v1.dashboard.router import (
    router as dashboard_router,
)
from app.api.v1.health.router import router as health_router
from app.api.v1.invoices.router import router as invoice_router
from app.api.v1.document_deliveries.router import (
    router as document_delivery_router,
)
from app.api.v1.email_outbox.router import (
    router as email_outbox_router,
)
from app.api.v1.memberships.router import (
    router as membership_router,
)
from app.api.v1.notifications.router import (
    router as notification_router,
)
from app.api.v1.organizations.router import (
    router as organization_router,
)
from app.api.v1.quotes.router import router as quote_router
from app.api.v1.reports.router import router as reports_router
from app.api.v1.roles.router import router as role_router
from app.api.v1.scheduling.router import (
    router as scheduling_router,
)
from app.api.v1.work_order_checklists.router import (
    router as work_order_checklist_router,
)
from app.api.v1.work_order_closeouts.router import (
    router as work_order_closeout_router,
)
from app.api.v1.work_order_expenses.router import (
    router as work_order_expense_router,
)
from app.api.v1.work_order_notes.router import (
    router as work_order_note_router,
)
from app.api.v1.work_orders.router import (
    router as work_order_router,
)
from app.api.v1.workforce.router import router as workforce_router


api_router = APIRouter()


api_router.include_router(
    health_router,
)

api_router.include_router(
    auth_router,
)

api_router.include_router(
    organization_router,
)

api_router.include_router(
    role_router,
)

api_router.include_router(
    membership_router,
)

api_router.include_router(
    customer_router,
)

api_router.include_router(
    customer_site_router,
)

api_router.include_router(
    workforce_router,
)

api_router.include_router(
    asset_router,
)

api_router.include_router(
    audit_log_router,
)

api_router.include_router(
    work_order_router,
)

api_router.include_router(
    work_order_closeout_router,
)

api_router.include_router(
    scheduling_router,
)

api_router.include_router(
    dashboard_router,
)

api_router.include_router(
    reports_router,
)

api_router.include_router(
    notification_router,
)

api_router.include_router(
    work_order_checklist_router,
)

api_router.include_router(
    work_order_note_router,
)

api_router.include_router(
    work_order_expense_router,
)

api_router.include_router(
    invoice_router,
)

api_router.include_router(
    quote_router,
)

api_router.include_router(
    document_delivery_router,
)

api_router.include_router(
    email_outbox_router,
)
