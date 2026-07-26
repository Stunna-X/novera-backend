"""
Work-order checklist enumerations.

Defines the lifecycle states available to checklist items.
"""

from enum import StrEnum


class WorkOrderChecklistStatus(StrEnum):
    """
    Current execution state of a checklist item.
    """

    PENDING = "pending"
    COMPLETED = "completed"
    SKIPPED = "skipped"