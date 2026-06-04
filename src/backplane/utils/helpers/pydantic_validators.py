"""Reusable Pydantic ``BeforeValidator`` helpers."""

from __future__ import annotations

from pydantic import BeforeValidator

ParseCommaSeparatedList = BeforeValidator(
    lambda v: (
        [part.strip() for part in v.split(",") if part.strip()]
        if isinstance(v, str)
        else v
    ),
)
"""Split a comma-separated string into a list of trimmed, non-empty parts.

Non-string values pass through unchanged.
"""

__all__ = ["ParseCommaSeparatedList"]
