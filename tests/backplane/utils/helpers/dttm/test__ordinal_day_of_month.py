"""Tests for ordinal day-of-month formatting."""

from __future__ import annotations

import pytest

from backplane.utils.helpers.dttm import ordinal_day_of_month


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (1, "1st"),
        (2, "2nd"),
        (3, "3rd"),
        (11, "11th"),
        (22, "22nd"),
    ],
)
def test__ordinal_day_of_month(day: int, expected: str) -> None:
    """Day number is combined with its ordinal suffix."""
    assert ordinal_day_of_month(day) == expected
