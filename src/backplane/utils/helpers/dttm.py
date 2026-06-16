"""Date and time formatting helpers."""

from __future__ import annotations

import datetime as dt
import re
from typing import TYPE_CHECKING, Final

from backplane.utils.settings import SETTINGS

if TYPE_CHECKING:
    from collections.abc import Callable

_ORDINAL_SUFFIXES: Final = {1: "st", 2: "nd", 3: "rd"}  # codespell:ignore nd
_TEEN_RANGE: Final = range(11, 14)
_DATE_TEMPLATE: Final = re.compile(r"\{\{\s*date\s*(?::([^}]*))?\s*\}\}", re.IGNORECASE)
_TITLE_TEMPLATE: Final = re.compile(r"\{\{\s*title\s*\}\}", re.IGNORECASE)
_CORE_DATETIME_TEMPLATE: Final = re.compile(
    r"\{\s*date\s*:\s*([^}]+)\s*\}",
    re.IGNORECASE,
)


def today() -> dt.date:
    """Return the current date in the configured local timezone."""
    return dt.datetime.now(tz=SETTINGS.local_timezone).date()


def ordinal_suffix_for_day(day: int) -> str:
    """Return the ordinal suffix for a day-of-month (``st``, ``nd``, ``rd``, ``th``)."""  # codespell:ignore nd
    if day % 100 in _TEEN_RANGE:
        return "th"
    return _ORDINAL_SUFFIXES.get(day % 10, "th")


def ordinal_day_of_month(day: int) -> str:
    """Return the day number with ordinal suffix, e.g. ``9`` -> ``9th``."""
    return f"{day}{ordinal_suffix_for_day(day)}"


_OBSIDIAN_FORMAT_HANDLERS: Final[list[tuple[str, Callable[[dt.datetime], str]]]] = [
    ("YYYY", lambda t: t.strftime("%Y")),
    ("MMMM", lambda t: t.strftime("%B")),
    ("dddd", lambda t: t.strftime("%A")),
    ("MMM", lambda t: t.strftime("%b")),
    ("ddd", lambda t: t.strftime("%a")),
    ("MM", lambda t: t.strftime("%m")),
    ("DD", lambda t: t.strftime("%d")),
    ("Do", lambda t: ordinal_day_of_month(t.day)),
    ("HH", lambda t: t.strftime("%H")),
    ("mm", lambda t: t.strftime("%M")),
    ("ss", lambda t: t.strftime("%S")),
    ("YY", lambda t: t.strftime("%y")),
    ("M", lambda t: str(t.month)),
    ("D", lambda t: str(t.day)),
]


def _expand_obsidian_format(fmt: str, moment: dt.datetime) -> str:
    """Replace Obsidian format tokens with their formatted values.

    Replaces recognized tokens (such as YYYY, MM, Do, HH, mm, ss) in the format string with their corresponding formatted values from the provided datetime.

    Returns:
        The format string with all matched tokens substituted.
    """
    sorted_handlers = sorted(
        _OBSIDIAN_FORMAT_HANDLERS,
        key=lambda item: len(item[0]),
        reverse=True,
    )
    parts: list[str] = []
    i = 0
    n = len(fmt)
    while i < n:
        for token, handler in sorted_handlers:
            if fmt.startswith(token, i):
                parts.append(handler(moment))
                i += len(token)
                break
        else:
            parts.append(fmt[i])
            i += 1
    return "".join(parts)


def _obsidian_format_moment(value: dt.date | dt.datetime) -> dt.datetime:
    """Convert a date or datetime to a timezone-aware datetime.

    Returns:
        A timezone-aware datetime. If the input is a date, it is set to midnight in the local timezone.
    """
    if isinstance(value, dt.datetime):
        return value
    return dt.datetime.combine(value, dt.time.min, tzinfo=SETTINGS.local_timezone)


def format_obsidian_moment_date(date: dt.date, fmt: str) -> str:
    """Format a value for Obsidian ``{{date}}`` / ``{{date:...}}`` placeholders.

    Intended for double-brace core-template variables in note bodies and titles.
    Formats are usually date-focused and may use human-readable moment.js tokens
    such as ``MMMM``, ``dddd``, and ``Do``. A plain :class:`~datetime.date` is
    treated as midnight in the configured local timezone; time tokens (``HH``,
    ``mm``, ``ss``) expand against that instant when present.

    Supported tokens (longest match wins): ``YYYY``, ``YY``, ``MMMM``, ``MMM``,
    ``MM``, ``M``, ``DD``, ``D``, ``Do``, ``dddd``, ``ddd``, ``HH``, ``mm``,
    ``ss``. Unrecognized characters are copied through unchanged.

    Args:
        date: The calendar date to format.
        fmt: The format string from inside ``{{date:...}}``.

    Returns:
        The formatted string.
    """
    return _expand_obsidian_format(fmt, _obsidian_format_moment(date))


def format_human_date(date: dt.date) -> str:
    """Format a date as a human-readable string, for example "Saturday, May 9th 2026".

    Returns:
        str: The formatted date string.
    """
    return format_obsidian_moment_date(date, "dddd, MMMM Do YYYY")


def substitute_obsidian_core_date_variables(template: str, date: dt.date) -> str:
    """Replace ``{{date}}`` and ``{{date:...}}`` placeholders (Obsidian core template syntax).

    Args:
        template: Raw template file contents.
        date: Calendar date used for substitution.

    Returns:
        Template text with date placeholders expanded.
    """

    def _replace(match: re.Match[str]) -> str:
        inner = match.group(1)
        if inner is None or not inner.strip():
            return date.isoformat()
        return format_obsidian_moment_date(date, inner.strip())

    return _DATE_TEMPLATE.sub(_replace, template)


def format_obsidian_datetime(now: dt.datetime, fmt: str) -> str:
    """Formats a datetime according to Obsidian template token syntax.

    Args:
        now: The local datetime to format.
        fmt: The format string with Obsidian tokens.

    Returns:
        The formatted string.
    """
    return _expand_obsidian_format(fmt, _obsidian_format_moment(now))


def substitute_vault_entity_template(
    template: str,
    *,
    title: str,
    now: dt.datetime | None = None,
) -> str:
    """Expand Obsidian template placeholders used for vault entity notes.

    Handles ``{{title}}``, ``{ date:... }`` (datetime), and ``{{date}}`` /
    ``{{date:...}}`` (date-only) placeholders.

    Args:
        template: Raw template file contents.
        title: Display title substituted for ``{{title}}``.
        now: Timestamp used for date/datetime placeholders. Defaults to now in
            the configured local timezone.

    Returns:
        Template text with placeholders expanded.
    """
    timestamp = now or dt.datetime.now(tz=SETTINGS.local_timezone)
    text = _TITLE_TEMPLATE.sub(lambda _match: title, template)
    text = substitute_obsidian_core_date_variables(text, timestamp.date())

    def _replace_datetime(match: re.Match[str]) -> str:
        return format_obsidian_datetime(timestamp, match.group(1).strip())

    return _CORE_DATETIME_TEMPLATE.sub(_replace_datetime, text)
