"""Tests for inbox capture fuzzy matching."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backplane.services.tasks import Capture, _find_match
from backplane.utils import VAULT_PATHS

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test__find_match_accepts_high_confidence(sample_captures: list[Capture]) -> None:
    """A strong match returns the best capture automatically."""
    outcome = _find_match(
        "weekly backup verification database",
        sample_captures,
    )
    assert outcome.matched is not None
    assert outcome.matched.id == "2026-01-10T09:00"
    assert outcome.candidates == []


def test__find_match_returns_none_without_candidates() -> None:
    """No captures means there is nothing to match."""
    assert _find_match("weekly backup verification database", []).matched is None


def test__find_match_returns_none_for_weak_match(sample_captures: list[Capture]) -> None:
    """Unrelated descriptions do not match any capture."""
    outcome = _find_match("xyzzy plugh unrelated qwerty", sample_captures)
    assert outcome.matched is None
    assert outcome.candidates == []


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
        path=VAULT_PATHS.inbox_dir / "Ideas.md",
    )

    outcome = _find_match(
        "sort that plant database thing, then log all my plants and care routines",
        [capture],
    )

    assert outcome.matched is None
    assert outcome.candidates == []


def test__find_match_returns_candidates_for_ambiguous_scores(
    sample_captures: list[Capture],
    mocker: MockerFixture,
) -> None:
    """Borderline scores surface candidates without blocking task creation."""
    _ = mocker.patch(
        "backplane.services.tasks._fuzzy_score",
        side_effect=[60.0, 60.0],
    )
    outcome = _find_match("something vague about calendars", sample_captures)

    assert outcome.matched is None
    assert outcome.candidates
    assert outcome.candidates == sample_captures


def test__find_match_requires_runner_up_gap_for_auto_link(
    sample_captures: list[Capture],
    mocker: MockerFixture,
) -> None:
    """High scores with a close runner-up are offered instead of auto-linked."""
    _ = mocker.patch(
        "backplane.services.tasks._fuzzy_score",
        side_effect=[72.0, 68.0],
    )
    outcome = _find_match("something vague about calendars", sample_captures)

    assert outcome.matched is None
    assert outcome.candidates == sample_captures


def test__find_match_regression_rain_alert_does_not_raise(
    rain_alert_unrelated_captures: list[Capture],
) -> None:
    """The rain-alert wording returns candidates instead of blocking creation."""
    outcome = _find_match(
        "Update rain + roof door open alert notification",
        rain_alert_unrelated_captures,
    )

    assert outcome.matched is None
