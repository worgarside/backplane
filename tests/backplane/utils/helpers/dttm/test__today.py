"""Tests for local-today date helper."""

from __future__ import annotations

import datetime as dt
import zoneinfo
from typing import TYPE_CHECKING

from backplane.utils.helpers.dttm import today
from backplane.utils.settings import SETTINGS

if TYPE_CHECKING:
    import pytest
    from pytest_mock import MockerFixture


def test__today_returns_date_in_configured_timezone(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Today is derived from now() in SETTINGS.local_timezone."""
    tz = zoneinfo.ZoneInfo("Europe/London")
    monkeypatch.setattr(SETTINGS, "local_timezone", tz)
    fixed = dt.datetime(2026, 5, 9, 23, 30, tzinfo=tz)
    mock_datetime = mocker.patch("backplane.utils.helpers.dttm.dt.datetime")
    mock_datetime.now.return_value = fixed  # pyright: ignore[reportAny]

    assert today() == dt.date(2026, 5, 9)
    mock_datetime.now.assert_called_once_with(tz=tz)  # pyright: ignore[reportAny]
