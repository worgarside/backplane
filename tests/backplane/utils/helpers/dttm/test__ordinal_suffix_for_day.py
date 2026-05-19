"""Tests for day-of-month ordinal suffixes."""

from __future__ import annotations

import pytest

from backplane.utils.helpers.dttm import ordinal_suffix_for_day


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (1, "st"),
        (2, "nd"),
        (3, "rd"),
        (4, "th"),
        (11, "th"),
        (12, "th"),
        (13, "th"),
        (21, "st"),
        (22, "nd"),
        (23, "rd"),
    ],
)
def test__ordinal_suffix_for_day(day: int, expected: str) -> None:
    """Ordinal suffix follows English day-of-month rules including teens."""
    assert ordinal_suffix_for_day(day) == expected
