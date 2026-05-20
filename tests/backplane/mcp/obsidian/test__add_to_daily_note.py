"""Tests for the add_to_daily_note MCP tool."""

from __future__ import annotations

import datetime as dt
import pathlib
from typing import TYPE_CHECKING

import pytest

from backplane.mcp.obsidian import add_to_daily_note
from backplane.utils import exc, format_human_date
from backplane.utils.settings import SETTINGS

if TYPE_CHECKING:
    import anyio


@pytest.fixture
def obsidian_vault(
    vault_path: anyio.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> anyio.Path:
    """Point application settings at a temporary vault root."""
    monkeypatch.setattr(SETTINGS, "obsidian_vault_path", vault_path)
    return vault_path


async def test__add_to_daily_note__wraps_missing_section_as_information_required(
    obsidian_vault: anyio.Path,
) -> None:
    """Missing sections surface retry guidance instead of a raw not-found error."""
    date = dt.date(2026, 5, 20)
    rel = pathlib.PurePath("Daily Notes/2026-05-20.md")
    top_heading = format_human_date(date)
    target = obsidian_vault / rel
    await (obsidian_vault / "Daily Notes").mkdir(parents=True, exist_ok=True)
    _ = await target.write_text(
        f"# {top_heading}\n\n## Tasks\n\nexisting\n",
        encoding="utf-8",
    )

    with pytest.raises(exc.InformationRequiredError) as exc_info:
        _ = await add_to_daily_note(
            heading_path=("Ideas",),
            content="new idea",
            date=date,
            create_section_if_not_exists=False,
        )

    message = str(exc_info.value)
    assert "Ideas" in message
    assert "create_section_if_not_exists=true" in message
    assert exc_info.value.__cause__ is not None
    assert isinstance(exc_info.value.__cause__, exc.SectionNotFoundError)


async def test__add_to_daily_note__appends_to_existing_section(
    obsidian_vault: anyio.Path,
) -> None:
    """Content is appended when the target section already exists."""
    date = dt.date(2026, 5, 20)
    rel = pathlib.PurePath("Daily Notes/2026-05-20.md")
    top_heading = format_human_date(date)
    target = obsidian_vault / rel
    await (obsidian_vault / "Daily Notes").mkdir(parents=True, exist_ok=True)
    _ = await target.write_text(
        f"# {top_heading}\n\n## Tasks\n\nfirst\n",
        encoding="utf-8",
    )

    rendered = await add_to_daily_note(
        heading_path=("Tasks",),
        content="second",
        date=date,
        mode="append",
    )

    assert "second" in rendered
    persisted = await target.read_text(encoding="utf-8")
    assert "second" in persisted
