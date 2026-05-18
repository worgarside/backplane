"""Tests for atomic text file writes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import anyio

from backplane.utils.helpers.files import atomic_write_text

if TYPE_CHECKING:
    from pathlib import Path


async def test__atomic_write_text_writes_content(tmp_path: Path) -> None:
    """Destination file receives the full written content."""
    target = anyio.Path(tmp_path) / "Tasks" / "note.md"
    await atomic_write_text(target, "hello\n")
    assert await target.read_text(encoding="utf-8") == "hello\n"


async def test__atomic_write_text_leaves_no_tmp_in_destination_dir(
    tmp_path: Path,
) -> None:
    """No .tmp siblings are created next to the destination during the write."""
    parent = anyio.Path(tmp_path) / "Tasks"
    target = parent / "note.md"
    await atomic_write_text(target, "hello\n")
    names = [entry.name async for entry in parent.iterdir()]
    assert names == ["note.md"]


async def test__atomic_write_text_overwrites_existing_file(tmp_path: Path) -> None:
    """An existing destination file is replaced atomically."""
    target = anyio.Path(tmp_path) / "note.md"
    _ = await target.write_text("old\n", encoding="utf-8")
    await atomic_write_text(target, "new\n")
    assert await target.read_text(encoding="utf-8") == "new\n"
