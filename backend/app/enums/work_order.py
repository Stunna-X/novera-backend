"""
Work order enums.
"""

from enum import Enum


class WorkOrderStatus(str, Enum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    APPROVED = "APPROVED"
    INVOICED = "INVOICED"
    CLOSED = "CLOSED"