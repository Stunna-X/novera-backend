"""
Invoice enumerations.

Defines invoice workflow states, line-item sources,
and supported payment methods.
"""

from enum import Enum


class InvoiceStatus(str, Enum):
    """
    Lifecycle states for an invoice.
    """

    DRAFT = "draft"
    ISSUED = "issued"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    VOID = "void"


class InvoiceLineSource(str, Enum):
    """
    Origin of an invoice line item.
    """

    MANUAL = "manual"
    EXPENSE = "expense"


class InvoicePaymentMethod(str, Enum):
    """
    Supported invoice payment methods.
    """

    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    CARD = "card"
    MOBILE_MONEY = "mobile_money"
    CHEQUE = "cheque"
    OTHER = "other"