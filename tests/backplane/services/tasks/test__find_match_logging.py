"""Tests for fuzzy-match diagnostic logging."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from backplane.services.tasks import Capture, _find_match

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test__find_match_logs_rejection_for_weak_match(
    sample_captures: list[Capture],
    mocker: MockerFixture,
) -> None:
    """Weak matches log rejection details at INFO."""
    mock_info = mocker.patch("backplane.services.tasks.logger.info")
    mocker.patch("backplane.services.tasks.logger.debug")

    assert _find_match("xyzzy plugh unrelated qwerty", sample_captures) is None

    assert any(
        "Fuzzy match rejected" in str(call.args[0]) for call in mock_info.call_args_list
    )


def test__find_match_logs_warning_before_ambiguous_raise(
    sample_captures: list[Capture],
    mocker: MockerFixture,
) -> None:
    """Ambiguous matches log a warning before raising ValueError."""
    mocker.patch("backplane.services.tasks._fuzzy_score", side_effect=[60.0, 60.0])
    mocker.patch("backplane.services.tasks.logger.debug")
    mock_warning = mocker.patch("backplane.services.tasks.logger.warning")

    with pytest.raises(ValueError, match="Ambiguous match"):
        _ = _find_match("something vague about calendars", sample_captures)

    mock_warning.assert_called_once()
    assert "ambiguous" in str(mock_warning.call_args.args[0]).casefold()


def test__find_match_logs_acceptance_with_runner_up_gap(
    sample_captures: list[Capture],
    mocker: MockerFixture,
) -> None:
    """Accepted matches log score and runner-up gap at INFO."""
    mock_info = mocker.patch("backplane.services.tasks.logger.info")
    mocker.patch("backplane.services.tasks.logger.debug")

    match = _find_match("weekly backup verification database", sample_captures)

    assert match is not None
    assert any(
        "Fuzzy match accepted" in str(call.args[0]) for call in mock_info.call_args_list
    )
