"""
SQLAlchemy model registry.

Importing models here ensures that all database tables are
registered in SQLAlchemy metadata and detected by Alembic.
"""

from app.models.asset import Asset
from app.models.customer import Customer
from app.models.customer_site import CustomerSite
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.permission import Permission
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User
from app.models.workforce_profile import WorkforceProfile


__all__ = [
    "Asset",
    "Customer",
    "CustomerSite",
    "Membership",
    "Organization",
    "Permission",
    "RefreshToken",
    "Role",
    "RolePermission",
    "User",
    "WorkforceProfile",
]