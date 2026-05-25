"""Tests for vault entity catalog listing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backplane.services.tasks import (
    _DOMAINS_DIR,
    _list_vault_entity_names,
    _note_title_from_markdown,
)
from backplane.utils.helpers.files import atomic_write_text

if TYPE_CHECKING:
    import anyio


def test__note_title_from_markdown_skips_frontmatter() -> None:
    """The first H1 after frontmatter is returned."""
    text = """---
type: domain
---

# Home Assistant

## Notes
"""
    assert _note_title_from_markdown(text) == "Home Assistant"


async def test__list_vault_entity_names_returns_sorted_titles(
    obsidian_vault: anyio.Path,
) -> None:
    """Note titles are read from H1 headings and deduplicated case-insensitively."""
    domains = obsidian_vault / "Domains"
    await domains.mkdir(parents=True)
    await atomic_write_text(
        domains / "obsidian.md",
        "---\ntype: domain\n---\n\n# Obsidian\n",
    )
    await atomic_write_text(
        domains / "home-assistant.md",
        "---\ntype: domain\n---\n\n# Home Assistant\n",
    )

    names = await _list_vault_entity_names(_DOMAINS_DIR)

    assert names == ["Home Assistant", "Obsidian"]


async def test__list_vault_entity_names_missing_directory(
    obsidian_vault: anyio.Path,
) -> None:
    """A missing catalog directory yields an empty list."""
    _ = obsidian_vault
    assert await _list_vault_entity_names(_DOMAINS_DIR) == []
