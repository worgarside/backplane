"""Helper functions for Backplane."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable


def today() -> dt.date:
    """Return the current date in the local timezone."""
    return dt.datetime.now(tz=dt.UTC).astimezone().date()


_ORDINAL_SUFFIXES: Final = {1: "st", 2: "nd", 3: "rd"}  # codespell:ignore nd
_TEEN_RANGE: Final = range(11, 14)


def ordinal_suffix_for_day(day: int) -> str:
    """Return the ordinal suffix for a day-of-month (``st``, ``nd``, ``rd``, ``th``)."""  # codespell:ignore nd
    if day % 100 in _TEEN_RANGE:
        return "th"
    return _ORDINAL_SUFFIXES.get(day % 10, "th")


def ordinal_day_of_month(day: int) -> str:
    """Return the day number with ordinal suffix, e.g. ``9`` -> ``9th``."""
    return f"{day}{ordinal_suffix_for_day(day)}"


def format_obsidian_moment_date(date: dt.date, fmt: str) -> str:
    """Format a date using a subset of Obsidian / moment.js display tokens.

    Supported tokens (longest match wins): ``YYYY``, ``YY``, ``MMMM``, ``MMM``,
    ``MM``, ``M``, ``DD``, ``D``, ``Do``, ``dddd``, ``ddd``. Any other characters
    are copied through unchanged.

    Args:
        date: The calendar date to format.
        fmt: The moment-style format string.

    Returns:
        The formatted string.
    """
    token_handlers: list[tuple[str, Callable[[dt.date], str]]] = [
        ("YYYY", lambda d: d.strftime("%Y")),
        ("MMMM", lambda d: d.strftime("%B")),
        ("dddd", lambda d: d.strftime("%A")),
        ("MMM", lambda d: d.strftime("%b")),
        ("ddd", lambda d: d.strftime("%a")),
        ("MM", lambda d: d.strftime("%m")),
        ("DD", lambda d: d.strftime("%d")),
        ("Do", lambda d: ordinal_day_of_month(d.day)),
        ("YY", lambda d: d.strftime("%y")),
        ("M", lambda d: str(d.month)),
        ("D", lambda d: str(d.day)),
    ]
    token_handlers.sort(key=lambda item: len(item[0]), reverse=True)

    parts: list[str] = []
    i = 0
    n = len(fmt)
    while i < n:
        for token, handler in token_handlers:
            if fmt.startswith(token, i):
                parts.append(handler(date))
                i += len(token)
                break
        else:
            parts.append(fmt[i])
            i += 1
    return "".join(parts)


def format_human_date(date: dt.date) -> str:
    """Format a date as e.g. ``Saturday, May 9th 2026``.

    Args:
        date: The date to format.

    Returns:
        The formatted date.
    """
    return format_obsidian_moment_date(date, "dddd, MMMM Do YYYY")


__all__ = [
    "format_human_date",
    "format_obsidian_moment_date",
    "ordinal_day_of_month",
    "ordinal_suffix_for_day",
    "today",
]
