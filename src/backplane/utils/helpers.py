"""Helper functions for Backplane."""

from __future__ import annotations

import datetime as dt
from typing import Final


def today() -> dt.date:
    """Return the current date in the UTC timezone."""
    return dt.datetime.now(tz=dt.UTC).date()


_ORDINAL_SUFFIXES: Final = {1: "st", 2: "nd", 3: "rd"}  # codespell:ignore nd
_TEEN_RANGE: Final = range(11, 14)


def format_human_date(date: dt.date) -> str:
    """Format a date as e.g. ``Saturday, May 9th 2026``.

    Args:
        date: The date to format.

    Returns:
        The formatted date.
    """
    day = date.day
    suffix = "th" if day % 100 in _TEEN_RANGE else _ORDINAL_SUFFIXES.get(day % 10, "th")
    return date.strftime(f"%A, %B {day}{suffix} %Y")


__all__ = ["format_human_date", "today"]
