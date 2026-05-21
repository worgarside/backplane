"""Tests for inbox capture fuzzy matching."""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import pytest

from backplane.services.tasks import Capture, _find_match

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture
def sample_captures() -> list[Capture]:
    """Recent inbox captures used for matching tests."""
    path = pathlib.PurePath("Inbox/Ideas.md")
    return [
        Capture(
            id="2026-05-17T01:44",
            date="2026-05-17",
            time="01:44",
            text="I need to create reminder notifications for the mood tracker",
            path=path,
        ),
        Capture(
            id="2026-05-17T14:29",
            date="2026-05-17",
            time="14:29",
            text=(
                "Update the Open Banking integration in Home Assistant to include "
                "Vic's Amex card and send her notifications of how much she's spent."
            ),
            path=path,
        ),
    ]


def test__find_match_accepts_high_confidence(sample_captures: list[Capture]) -> None:
    """A strong match returns the best capture automatically."""
    match = _find_match(
        "create reminder notifications for the mood tracker",
        sample_captures,
    )
    assert match is not None
    assert match.id == "2026-05-17T01:44"


def test__find_match_returns_none_for_weak_match(sample_captures: list[Capture]) -> None:
    """Unrelated descriptions do not match any capture."""
    assert _find_match("xyzzy plugh unrelated qwerty", sample_captures) is None


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
        _ = _find_match("something vague about banking", sample_captures)
