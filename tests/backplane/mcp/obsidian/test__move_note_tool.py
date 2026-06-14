"""Tests for the move_note MCP tool."""

from __future__ import annotations

from typing import TYPE_CHECKING

import anyio

from backplane.mcp.obsidian import move_note
from backplane.utils.helpers.files import atomic_write_text

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


async def test__move_note__returns_confirmation(mocker: MockerFixture) -> None:
    """The move tool returns a concise confirmation with the destination path."""
    mock_move = mocker.patch(
        "backplane.mcp.obsidian.ObsidianService.move_note",
        new=mocker.AsyncMock(return_value=anyio.Path("Projects/plan.md")),
    )

    result = await move_note(
        source_path="Tasks/plan.md",
        destination_path="Projects/plan.md",
    )

    assert result == "Moved note to Projects/plan.md."
    _ = mock_move.assert_awaited_once()


async def test__move_note__integration(obsidian_vault: anyio.Path) -> None:
    """The move tool relocates a note on disk and confirms the destination."""
    source = "Inbox/capture.md"
    destination = "Projects/Home/capture.md"
    await atomic_write_text(obsidian_vault / source, "# Capture\n")

    result = await move_note(
        source_path=source,
        destination_path=destination,
    )

    assert result == f"Moved note to {destination}."
    assert not await (obsidian_vault / source).exists()
    assert await (obsidian_vault / destination).is_file()
