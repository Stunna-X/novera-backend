"""
Work-order expense enumerations.

Defines expense categories and approval states used for
tracking operational costs against work orders.
"""

from enum import StrEnum


class WorkOrderExpenseCategory(StrEnum):
    """
    Supported work-order expense categories.
    """

    LABOUR = "labour"
    MATERIALS = "materials"
    TRANSPORT = "transport"
    EQUIPMENT = "equipment"
    SUBCONTRACTOR = "subcontractor"
    PERMIT = "permit"
    ACCOMMODATION = "accommodation"
    OTHER = "other"


class WorkOrderExpenseStatus(StrEnum):
    """
    Approval lifecycle for a work-order expense.
    """

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"