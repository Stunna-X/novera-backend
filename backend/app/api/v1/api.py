"""
API Router Aggregator.

Every Version 1 endpoint is registered here.
"""

from fastapi import APIRouter

from app.api.v1.auth.router import router as auth_router
from app.api.v1.customer_sites.router import router as customer_site_router
from app.api.v1.customers.router import router as customer_router
from app.api.v1.health.router import router as health_router
from app.api.v1.memberships.router import router as membership_router
from app.api.v1.organizations.router import router as organization_router
from app.api.v1.roles.router import router as role_router


api_router = APIRouter()


# -----------------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------------

api_router.include_router(
    health_router,
)


# -----------------------------------------------------------------------------
# Authentication
# -----------------------------------------------------------------------------

api_router.include_router(
    auth_router,
)


# -----------------------------------------------------------------------------
# Organizations
# -----------------------------------------------------------------------------

api_router.include_router(
    organization_router,
)


# -----------------------------------------------------------------------------
# Organization Access and Roles
# -----------------------------------------------------------------------------

api_router.include_router(
    role_router,
)


# -----------------------------------------------------------------------------
# Organization Memberships
# -----------------------------------------------------------------------------

api_router.include_router(
    membership_router,
)


# -----------------------------------------------------------------------------
# Customers
# -----------------------------------------------------------------------------

api_router.include_router(
    customer_router,
)


# -----------------------------------------------------------------------------
# Customer Sites
# -----------------------------------------------------------------------------

api_router.include_router(
    customer_site_router,
)


# -----------------------------------------------------------------------------
# Future routers
# -----------------------------------------------------------------------------

# from app.api.v1.work_orders.router import router as work_order_router
# from app.api.v1.assets.router import router as asset_router
# from app.api.v1.projects.router import router as project_router
# from app.api.v1.workforce.router import router as workforce_router
# from app.api.v1.dashboard.router import router as dashboard_router
# from app.api.v1.reports.router import router as report_router

# api_router.include_router(work_order_router)
# api_router.include_router(asset_router)
# api_router.include_router(project_router)
# api_router.include_router(workforce_router)
# api_router.include_router(dashboard_router)
# api_router.include_router(report_router)