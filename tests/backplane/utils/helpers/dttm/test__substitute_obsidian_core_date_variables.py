"""Tests for Obsidian core template date substitution."""

from __future__ import annotations

import datetime as dt

import pytest

from backplane.utils.helpers.dttm import substitute_obsidian_core_date_variables

_SAMPLE_DATE = dt.date(2026, 5, 9)


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("# {{date}}", "# 2026-05-09"),
        ("# {{ date:YYYY-MM-DD }}", "# 2026-05-09"),
        ("# {{date:dddd, MMMM Do YYYY}}", "# Saturday, May 9th 2026"),
        ("# {{DATE}}", "# 2026-05-09"),
        ("{{date}} and {{date:YYYY}}", "2026-05-09 and 2026"),
    ],
)
def test__substitute_obsidian_core_date_variables(template: str, expected: str) -> None:
    """Expand Obsidian ``{{date}}`` and ``{{date:FORMAT}}`` placeholders."""
    assert substitute_obsidian_core_date_variables(template, _SAMPLE_DATE) == expected


def test__substitute_obsidian_core_date_variables_leaves_text_without_placeholders() -> (
    None
):
    """Templates without date placeholders are returned unchanged."""
    template = "# Daily note\n\nNo dates here."
    assert substitute_obsidian_core_date_variables(template, _SAMPLE_DATE) == template
