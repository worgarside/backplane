"""Tests for the README MCP catalog CLI entrypoint."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test__main__returns_one_when_readme_changed(mocker: MockerFixture) -> None:
    """The CLI exits with code 1 when README content was updated."""
    mocker.patch(
        "backplane.docs.mcp_catalog.refresh_readme_catalog",
        return_value=True,
    )

    from backplane.docs.update_readme_mcp_catalog import main  # noqa: PLC0415

    assert main() == 1


def test__main__returns_zero_when_readme_is_current(mocker: MockerFixture) -> None:
    """The CLI exits with code 0 when README content is already up to date."""
    mocker.patch(
        "backplane.docs.mcp_catalog.refresh_readme_catalog",
        return_value=False,
    )

    from backplane.docs.update_readme_mcp_catalog import main  # noqa: PLC0415

    assert main() == 0


def test__main__defaults_local_timezone_when_unset(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI sets LOCAL_TIMEZONE when it is not already configured."""
    monkeypatch.delenv("LOCAL_TIMEZONE", raising=False)
    mocker.patch(
        "backplane.docs.mcp_catalog.refresh_readme_catalog",
        return_value=False,
    )

    from backplane.docs.update_readme_mcp_catalog import main  # noqa: PLC0415

    assert main() == 0
    assert os.environ["LOCAL_TIMEZONE"] == "UTC"
