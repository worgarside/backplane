"""Tests for Obsidian moment.js date token formatting."""

from __future__ import annotations

import datetime as dt

import pytest

from backplane.utils.helpers.dttm import format_obsidian_moment_date

_SAMPLE_DATE = dt.date(2026, 5, 9)


@pytest.mark.parametrize(
    ("fmt", "expected"),
    [
        ("YYYY", "2026"),
        ("YY", "26"),
        ("MMMM", "May"),
        ("MMM", "May"),
        ("MM", "05"),
        ("M", "5"),
        ("DD", "09"),
        ("D", "9"),
        ("Do", "9th"),
        ("dddd", "Saturday"),
        ("ddd", "Sat"),
        ("YYYY-MM-DD", "2026-05-09"),
        ("[YYYY]", "[2026]"),
    ],
)
def test__format_obsidian_moment_date(fmt: str, expected: str) -> None:
    """Moment-style tokens expand; other characters pass through unchanged."""
    assert format_obsidian_moment_date(_SAMPLE_DATE, fmt) == expected
