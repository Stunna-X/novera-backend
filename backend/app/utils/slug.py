"""
Slug generation utilities.
"""

from __future__ import annotations

import re


def slugify(value: str) -> str:
    """
    Convert a string into a URL-safe slug.

    Example:
        Novera Technologies Ltd
        ->
        novera-technologies-ltd
    """

    value = value.lower().strip()

    value = re.sub(r"[^a-z0-9\s-]", "", value)

    value = re.sub(r"\s+", "-", value)

    value = re.sub(r"-+", "-", value)

    return value.strip("-")