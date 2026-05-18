"""Tests for human-readable date formatting."""

from __future__ import annotations

import datetime as dt

from backplane.utils.helpers.dttm import format_human_date


def test__format_human_date() -> None:
    """Human date uses weekday, month name, ordinal day, and year."""
    assert format_human_date(dt.date(2026, 5, 9)) == "Saturday, May 9th 2026"
