"""
System role enums.
"""

from enum import Enum


class SystemRole(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    DISPATCHER = "DISPATCHER"
    TECHNICIAN = "TECHNICIAN"
    VIEWER = "VIEWER"