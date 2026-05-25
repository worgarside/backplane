"""Tests for MarkdownDocument vault I/O."""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

from backplane.utils.markdown import MarkdownDocument

if TYPE_CHECKING:
    import anyio


async def test__markdown_document__creates_missing_file_on_enter(
    obsidian_vault: anyio.Path,
) -> None:
    """A missing note is created with atomic_write_text during __aenter__."""
    rel = pathlib.PurePath("Daily/2026-05-20.md")
    target = obsidian_vault / rel
    assert not await target.exists()

    async with MarkdownDocument(
        vault_path=rel,
        create_if_not_exists=True,
        initial_content="## Tasks\n\n",
        detect_external_modification=False,
    ) as doc:
        assert doc.get_section(("Tasks",)).heading == "Tasks"

    assert await target.exists()
    assert "## Tasks" in await target.read_text(encoding="utf-8")


async def test__markdown_document__creates_empty_file_without_initial_content(
    obsidian_vault: anyio.Path,
) -> None:
    """create_if_not_exists with no initial_content writes an empty file."""
    rel = pathlib.PurePath("empty.md")
    target = obsidian_vault / rel

    async with MarkdownDocument(
        vault_path=rel,
        create_if_not_exists=True,
        detect_external_modification=False,
    ):
        pass

    assert await target.exists()
    assert not await target.read_text(encoding="utf-8")


async def test__markdown_document__persists_edits_on_exit(
    obsidian_vault: anyio.Path,
) -> None:
    """Successful edits are flushed with atomic_write_text on __aexit__."""
    rel = pathlib.PurePath("note.md")
    target = obsidian_vault / rel
    _ = await target.write_text("## Ideas\n\nfirst thought\n", encoding="utf-8")

    async with MarkdownDocument(
        vault_path=rel,
        detect_external_modification=False,
    ) as doc:
        doc.get_section(("Ideas",)).append_content("second thought")

    text = await target.read_text(encoding="utf-8")
    assert "second thought" in text
