"""Tests for content-based vault note search."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backplane.services.vault_search import VaultSearchService
from backplane.utils.helpers.files import atomic_write_text

if TYPE_CHECKING:
    from backplane.utils.async_path import AsyncPath


async def test__search_note_contents__matches_body_with_excerpt(
    obsidian_vault: AsyncPath,
) -> None:
    """A body match returns an excerpt around the matched phrase."""
    _ = obsidian_vault
    resources = obsidian_vault / "Resources"
    await resources.mkdir(parents=True)
    await atomic_write_text(
        resources / "mqtt-broker.md",
        "# MQTT Broker\n\nConfigure the local MQTT broker for automations.\n",
    )

    hits = await VaultSearchService.search_note_contents(
        "MQTT broker",
        kinds=["resource"],
    )

    assert len(hits) == 1
    assert hits[0].title == "MQTT Broker"
    assert hits[0].kind == "resource"
    assert hits[0].excerpt is not None
    assert "mqtt broker" in hits[0].excerpt.casefold()


async def test__search_note_contents__skips_frontmatter_only_matches(
    obsidian_vault: AsyncPath,
) -> None:
    """Frontmatter text is not searched for content matches."""
    _ = obsidian_vault
    domains = obsidian_vault / "Domains"
    await domains.mkdir(parents=True)
    await atomic_write_text(
        domains / "secret-topic.md",
        "---\nsummary: rain alert\n---\n\n# Secret Topic\n\nNothing here.\n",
    )

    hits = await VaultSearchService.search_note_contents("rain alert", kinds=["domain"])

    assert hits == []


async def test__search_note_contents__returns_empty_when_no_match(
    obsidian_vault: AsyncPath,
) -> None:
    """Unmatched queries return an empty result list."""
    _ = obsidian_vault
    domains = obsidian_vault / "Domains"
    await domains.mkdir(parents=True)
    await atomic_write_text(domains / "zigbee.md", "# Zigbee\n\nMesh network notes.\n")

    hits = await VaultSearchService.search_note_contents("rain alert", kinds=["domain"])

    assert hits == []


async def test__search_note_contents__respects_kind_filter(
    obsidian_vault: AsyncPath,
) -> None:
    """Kind filters restrict content search to the requested directories."""
    _ = obsidian_vault
    domains = obsidian_vault / "Domains"
    tasks = obsidian_vault / "Tasks" / "Tasks"
    await domains.mkdir(parents=True)
    await tasks.mkdir(parents=True)
    await atomic_write_text(domains / "backup.md", "# Backup\n\nVerify weekly backups.\n")
    await atomic_write_text(
        tasks / "backup-task.md",
        "# Backup Task\n\nVerify weekly backups.\n",
    )

    hits = await VaultSearchService.search_note_contents(
        "weekly backups",
        kinds=["task"],
    )

    assert [hit.kind for hit in hits] == ["task"]


async def test__search_note_contents__respects_limit(obsidian_vault: AsyncPath) -> None:
    """The result list is capped at the requested limit."""
    _ = obsidian_vault
    domains = obsidian_vault / "Domains"
    await domains.mkdir(parents=True)
    await atomic_write_text(domains / "alpha.md", "# Alpha\n\nshared phrase here\n")
    await atomic_write_text(domains / "beta.md", "# Beta\n\nshared phrase here\n")

    hits = await VaultSearchService.search_note_contents(
        "shared phrase",
        kinds=["domain"],
        limit=1,
    )

    assert len(hits) == 1
