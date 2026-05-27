"""Tests for inbox capture fuzzy matching."""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import pytest

from backplane.services.tasks import Capture, _find_match

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test__find_match_accepts_high_confidence(sample_captures: list[Capture]) -> None:
    """A strong match returns the best capture automatically."""
    match = _find_match(
        "weekly backup verification database",
        sample_captures,
    )
    assert match is not None
    assert match.id == "2026-01-10T09:00"


def test__find_match_returns_none_without_candidates() -> None:
    """No captures means there is nothing to match."""
    assert _find_match("weekly backup verification database", []) is None


def test__find_match_returns_none_for_weak_match(sample_captures: list[Capture]) -> None:
    """Unrelated descriptions do not match any capture."""
    assert _find_match("xyzzy plugh unrelated qwerty", sample_captures) is None


def test__find_match_rejects_loose_long_capture_match() -> None:
    """Loose long-text WRatio matches are not accepted automatically."""
    capture = Capture(
        id="2026-05-17T14:29",
        date="2026-05-17",
        time="14:29",
        text=(
            "Update the Open Banking integration in Home Assistant to include "
            "Vic's Amex card and send her notifications of how much she's spent."
        ),
        path=pathlib.PurePath("Inbox/Ideas.md"),
    )

    match = _find_match(
        "sort that plant database thing, then log all my plants and care routines",
        [capture],
    )

    assert match is None


def test__find_match_raises_for_ambiguous_scores(
    sample_captures: list[Capture],
    mocker: MockerFixture,
) -> None:
    """Borderline scores surface candidates for clarification."""
    _ = mocker.patch(
        "backplane.services.tasks._fuzzy_score",
        side_effect=[60.0, 60.0],
    )
    with pytest.raises(ValueError, match="Ambiguous match"):
        _ = _find_match("something vague about calendars", sample_captures)
