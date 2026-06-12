"""Tests for vault entity listing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backplane.services.vault_entities import VaultEntityService
from backplane.utils.enums import VaultEntityKind
from backplane.utils.helpers.files import atomic_write_text

if TYPE_CHECKING:
    import anyio


async def test__list_entities_returns_sorted_titles(obsidian_vault: anyio.Path) -> None:
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

    names = await VaultEntityService.list_entities(VaultEntityKind.DOMAIN)

    assert names == ["Home Assistant", "Obsidian"]


async def test__list_entities_skips_non_markdown_and_untitled_notes(
    obsidian_vault: anyio.Path,
) -> None:
    """Only Markdown notes with level-1 headings are included."""
    domains = obsidian_vault / "Domains"
    await domains.mkdir(parents=True)
    await atomic_write_text(domains / "README.txt", "# Ignored\n")
    await atomic_write_text(domains / "untitled.md", "## Notes\n")
    await atomic_write_text(domains / "zigbee.md", "# Zigbee\n")

    names = await VaultEntityService.list_entities(VaultEntityKind.DOMAIN)

    assert names == ["Zigbee"]


async def test__list_entities_missing_directory(obsidian_vault: anyio.Path) -> None:
    """A missing catalog directory yields an empty list."""
    _ = obsidian_vault
    assert await VaultEntityService.list_entities(VaultEntityKind.DOMAIN) == []
