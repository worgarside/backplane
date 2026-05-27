"""Tests for log text truncation helpers."""

from __future__ import annotations

from backplane.services.tasks import _truncate_for_log


def test__truncate_for_log_returns_short_text_unchanged() -> None:
    """Short strings are not truncated."""
    assert _truncate_for_log("plant database") == "plant database"


def test__truncate_for_log_truncates_long_text() -> None:
    """Long strings are truncated with an ellipsis."""
    max_len = 20
    text = "a" * 120
    truncated = _truncate_for_log(text, max_len=max_len)
    assert len(truncated) == max_len
    assert truncated.endswith("…")
