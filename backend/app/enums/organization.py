"""
Membership-related enums.
"""

from enum import Enum


class MembershipStatus(str, Enum):
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"