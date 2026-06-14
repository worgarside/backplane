"""Tests for ObsidianService.move_note."""

from __future__ import annotations

import pytest

from backplane.services.obsidian import ObsidianService
from backplane.utils import exc
from backplane.utils.async_path import AsyncPath
from backplane.utils.helpers.files import atomic_write_text

pytestmark = pytest.mark.usefixtures("obsidian_vault")


async def test__move_note__relocates_note(obsidian_vault: AsyncPath) -> None:
    """Moving a note writes it to the destination and removes the source file."""
    source = AsyncPath("Old/note.md")
    destination = AsyncPath("New/note.md")
    await atomic_write_text(obsidian_vault / source, "# Moved Note\n")

    result = await ObsidianService.move_note(source, destination)

    assert result == destination
    assert not await (obsidian_vault / source).exists()
    text = await (obsidian_vault / destination).read_text(encoding="utf-8")
    assert text == "# Moved Note\n"


async def test__move_note__creates_destination_parent_directory(
    obsidian_vault: AsyncPath,
) -> None:
    """Missing destination parent directories are created before the move."""
    source = AsyncPath("Tasks/review.md")
    destination = AsyncPath("Projects/Home Assistant/plan.md")
    await atomic_write_text(obsidian_vault / source, "# Plan\n")

    result = await ObsidianService.move_note(source, destination)

    assert result == destination
    assert await (obsidian_vault / destination).is_file()


async def test__move_note__removes_empty_source_directory(
    obsidian_vault: AsyncPath,
) -> None:
    """An empty source parent directory is deleted after the move."""
    source = AsyncPath("Archive/2026/entry.md")
    destination = AsyncPath("Journal/entry.md")
    await atomic_write_text(obsidian_vault / source, "# Entry\n")

    _ = await ObsidianService.move_note(source, destination)

    assert not await (obsidian_vault / "Archive/2026").exists()
    assert await (obsidian_vault / destination).is_file()


async def test__move_note__preserves_non_empty_source_directory(
    obsidian_vault: AsyncPath,
) -> None:
    """A source directory with remaining notes is kept after the move."""
    source = AsyncPath("Shared/first.md")
    destination = AsyncPath("Moved/first.md")
    await atomic_write_text(obsidian_vault / source, "# First\n")
    await atomic_write_text(obsidian_vault / "Shared/second.md", "# Second\n")

    _ = await ObsidianService.move_note(source, destination)

    assert await (obsidian_vault / "Shared").is_dir()
    assert await (obsidian_vault / "Shared/second.md").is_file()
    assert await (obsidian_vault / destination).is_file()


async def test__move_note__raises_not_found_for_missing_source() -> None:
    """Moving a missing note raises NotFoundError."""
    with pytest.raises(exc.NotFoundError, match="Note not found"):
        _ = await ObsidianService.move_note(
            AsyncPath("Missing/note.md"),
            AsyncPath("New/note.md"),
        )


async def test__move_note__raises_conflict_when_destination_exists(
    obsidian_vault: AsyncPath,
) -> None:
    """Moving to an existing destination raises ConflictError."""
    await atomic_write_text(obsidian_vault / AsyncPath("Source/note.md"), "# Source\n")
    await atomic_write_text(obsidian_vault / AsyncPath("Target/note.md"), "# Target\n")

    with pytest.raises(exc.ConflictError, match="Destination already exists"):
        _ = await ObsidianService.move_note(
            AsyncPath("Source/note.md"),
            AsyncPath("Target/note.md"),
        )


@pytest.mark.parametrize(
    "path",
    [
        AsyncPath("Notes/readme.txt"),
        AsyncPath("Notes/readme"),
    ],
)
async def test__move_note__raises_user_error_for_non_md_path(path: AsyncPath) -> None:
    """Non-markdown paths are rejected before any filesystem changes."""
    with pytest.raises(exc.UserError, match="markdown file"):
        _ = await ObsidianService.move_note(path, AsyncPath("New/note.md"))


async def test__move_note__raises_user_error_for_obsidian_path() -> None:
    """Paths under .obsidian/ are rejected."""
    with pytest.raises(exc.UserError, match=r".obsidian/"):
        _ = await ObsidianService.move_note(
            AsyncPath(".obsidian/notes.md"),
            AsyncPath("New/note.md"),
        )


async def test__move_note__rejects_unsafe_path(obsidian_vault: AsyncPath) -> None:
    """Traversal paths are rejected by resolve_under_root."""
    await atomic_write_text(obsidian_vault / "Safe/note.md", "# Safe\n")

    with pytest.raises(ValueError, match="Unsafe path"):
        _ = await ObsidianService.move_note(
            AsyncPath("../outside.md"),
            AsyncPath("New/note.md"),
        )
