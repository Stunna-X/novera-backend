"""
Quote enumerations.

Defines the lifecycle states used by customer quotes and estimates.
"""

from enum import Enum


class QuoteStatus(str, Enum):
    """
    Lifecycle states for a customer quote.
    """

    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CONVERTED = "converted"