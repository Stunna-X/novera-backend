"""
Common enums shared across the application.
"""

from enum import Enum


class Status(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"