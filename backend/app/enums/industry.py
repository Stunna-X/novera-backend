"""
Supported organization industries.
"""

from enum import Enum


class Industry(str, Enum):
    BOREHOLE = "Borehole Drilling"
    CONSTRUCTION = "Construction"
    ELECTRICAL = "Electrical"
    FACILITY_MANAGEMENT = "Facility Management"
    HVAC = "HVAC"
    PLUMBING = "Plumbing"
    SECURITY = "Security"
    SOLAR = "Solar"
    TELECOM = "Telecom"
    UTILITIES = "Utilities"
    OTHER = "Other"