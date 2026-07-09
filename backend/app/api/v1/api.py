"""
API Router Aggregator.

Every Version 1 endpoint is registered here.
"""

from fastapi import APIRouter

from app.api.v1.health.router import router as health_router

# Future routers
# from app.api.v1.auth.router import router as auth_router
# from app.api.v1.organizations.router import router as organization_router
# from app.api.v1.customers.router import router as customer_router
# from app.api.v1.work_orders.router import router as work_order_router
# from app.api.v1.assets.router import router as asset_router
# from app.api.v1.projects.router import router as project_router
# from app.api.v1.workforce.router import router as workforce_router
# from app.api.v1.dashboard.router import router as dashboard_router
# from app.api.v1.reports.router import router as report_router

api_router = APIRouter()

# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------

api_router.include_router(
    health_router,
    prefix="",
    tags=["Health"],
)

# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------

# api_router.include_router(
#     auth_router,
#     prefix="/auth",
#     tags=["Authentication"],
# )

# --------------------------------------------------------------------------
# Organizations
# --------------------------------------------------------------------------

# api_router.include_router(
#     organization_router,
#     prefix="/organizations",
#     tags=["Organizations"],
# )

# --------------------------------------------------------------------------
# Customers
# --------------------------------------------------------------------------

# api_router.include_router(
#     customer_router,
#     prefix="/customers",
#     tags=["Customers"],
# )

# --------------------------------------------------------------------------
# Workforce
# --------------------------------------------------------------------------

# api_router.include_router(
#     workforce_router,
#     prefix="/workforce",
#     tags=["Workforce"],
# )

# --------------------------------------------------------------------------
# Assets
# --------------------------------------------------------------------------

# api_router.include_router(
#     asset_router,
#     prefix="/assets",
#     tags=["Assets"],
# )

# --------------------------------------------------------------------------
# Projects
# --------------------------------------------------------------------------

# api_router.include_router(
#     project_router,
#     prefix="/projects",
#     tags=["Projects"],
# )

# --------------------------------------------------------------------------
# Work Orders
# --------------------------------------------------------------------------

# api_router.include_router(
#     work_order_router,
#     prefix="/work-orders",
#     tags=["Work Orders"],
# )

# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------

# api_router.include_router(
#     dashboard_router,
#     prefix="/dashboard",
#     tags=["Dashboard"],
# )

# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------

# api_router.include_router(
#     report_router,
#     prefix="/reports",
#     tags=["Reports"],
# )