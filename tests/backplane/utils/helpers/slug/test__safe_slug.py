"""Tests for slug generation."""

from __future__ import annotations

import pytest

from backplane.utils.helpers.slug import safe_slug


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Open Banking Vic Amex", "open-banking-vic-amex"),
        ("  Mood Tracker Reminders!  ", "mood-tracker-reminders"),
        ("", "task"),
        ("!!!", "task"),
        ("café résumé", "cafe-resume"),
        ("foo---bar   baz", "foo-bar-baz"),
    ],
)
def test__safe_slug(text: str, expected: str) -> None:
    """Slugify titles into filesystem-safe names."""
    assert safe_slug(text) == expected


def test__safe_slug_truncates_to_max_len() -> None:
    """Slugs longer than max_len are truncated."""
    assert safe_slug("a" * 80, max_len=10) == "a" * 10
