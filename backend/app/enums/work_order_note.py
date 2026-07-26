"""
Work-order note enumerations.

Defines note categories and visibility levels used for
operational communication inside work orders.
"""

from enum import StrEnum


class WorkOrderNoteType(StrEnum):
    """
    Purpose of a work-order note.
    """

    NOTE = "note"
    FIELD_UPDATE = "field_update"


class WorkOrderNoteVisibility(StrEnum):
    """
    Audience allowed to see a work-order note.
    """

    INTERNAL = "internal"
    CUSTOMER = "customer"