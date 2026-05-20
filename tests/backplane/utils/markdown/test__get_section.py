"""Tests for MarkdownDocument.get_section error handling."""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import pytest

from backplane.utils.exceptions import SectionNotFoundError, UserError
from backplane.utils.markdown import MarkdownDocument
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


async def test__get_section__rejects_empty_heading_path(
    obsidian_vault: anyio.Path,
) -> None:
    """An empty heading path is rejected before any section traversal."""
    rel = pathlib.PurePath("note.md")
    target = obsidian_vault / rel
    _ = await target.write_text("## Tasks\n\n", encoding="utf-8")

    async with MarkdownDocument(
        vault_path=rel,
        detect_external_modification=False,
    ) as doc:
        with pytest.raises(UserError, match="Heading path cannot be empty"):
            _ = doc.get_section(())


async def test__get_section__raises_when_section_missing(
    obsidian_vault: anyio.Path,
) -> None:
    """Missing sections list available siblings when creation is disabled."""
    rel = pathlib.PurePath("note.md")
    target = obsidian_vault / rel
    _ = await target.write_text("## Tasks\n\n- item\n", encoding="utf-8")

    async with MarkdownDocument(
        vault_path=rel,
        detect_external_modification=False,
    ) as doc:
        with pytest.raises(SectionNotFoundError, match="Ideas") as exc_info:
            _ = doc.get_section(("Ideas",))

    err = exc_info.value
    assert err.section == "Ideas"
    assert err.parent is None
    assert err.siblings == ["Tasks"]


async def test__get_section__raises_for_missing_nested_section(
    obsidian_vault: anyio.Path,
) -> None:
    """Nested lookups report the parent heading and sibling names."""
    rel = pathlib.PurePath("note.md")
    target = obsidian_vault / rel
    _ = await target.write_text("## Parent\n\n### Child\n\n", encoding="utf-8")

    async with MarkdownDocument(
        vault_path=rel,
        detect_external_modification=False,
    ) as doc:
        with pytest.raises(SectionNotFoundError, match="Missing") as exc_info:
            _ = doc.get_section(("Parent", "Missing"))

    err = exc_info.value
    assert err.section == "Missing"
    assert err.parent == "Parent"
    assert err.siblings == ["Child"]
