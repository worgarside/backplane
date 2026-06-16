"""Tests for title-based vault note search."""

from __future__ import annotations

import pytest

from backplane.services.vault_search import VaultSearchService
from backplane.utils.async_path import AsyncPath
from backplane.utils.helpers.files import atomic_write_text


async def test__find_notes_by_title__matches_exact_title(
    obsidian_vault: AsyncPath,
) -> None:
    """An exact H1 title match ranks highest."""
    _ = obsidian_vault
    domains = obsidian_vault / "Domains"
    await domains.mkdir(parents=True)
    await atomic_write_text(
        domains / "home-assistant.md",
        "# Home Assistant\n\n## Overview\n",
    )

    hits = await VaultSearchService.find_notes_by_title("Home Assistant")

    assert len(hits) == 1
    assert hits[0].title == "Home Assistant"
    assert hits[0].kind == "domain"
    assert hits[0].score == pytest.approx(100.0)
    assert hits[0].excerpt is None


async def test__find_notes_by_title__matches_filename_stem(
    obsidian_vault: AsyncPath,
) -> None:
    """Daily notes without an H1 fall back to the filename stem."""
    _ = obsidian_vault
    daily_notes = obsidian_vault / "Daily Notes"
    await daily_notes.mkdir(parents=True)
    await atomic_write_text(daily_notes / "2026-06-16.md", "## Tasks\n")

    hits = await VaultSearchService.find_notes_by_title(
        "2026-06-16",
        kinds=["daily_note"],
    )

    assert len(hits) == 1
    assert hits[0].title == "2026-06-16"
    assert hits[0].kind == "daily_note"
    assert hits[0].path == AsyncPath("Daily Notes/2026-06-16.md")


async def test__find_notes_by_title__matches_fuzzy_title(
    obsidian_vault: AsyncPath,
) -> None:
    """A close title match returns a fuzzy score above the threshold."""
    _ = obsidian_vault
    projects = obsidian_vault / "Projects"
    await projects.mkdir(parents=True, exist_ok=True)
    await atomic_write_text(
        projects / "garage-migration.md",
        "# Garage Migration\n",
    )

    hits = await VaultSearchService.find_notes_by_title(
        "Garage Migrtion",
        kinds=["project"],
    )

    assert len(hits) == 1
    assert hits[0].title == "Garage Migration"
    assert hits[0].score >= 70.0


async def test__find_notes_by_title__respects_kind_filter(
    obsidian_vault: AsyncPath,
) -> None:
    """Kind filters restrict the search to the requested directories."""
    _ = obsidian_vault
    domains = obsidian_vault / "Domains"
    tasks = obsidian_vault / "Tasks" / "Tasks"
    await domains.mkdir(parents=True)
    await tasks.mkdir(parents=True)
    await atomic_write_text(domains / "mqtt.md", "# MQTT\n")
    await atomic_write_text(tasks / "mqtt-task.md", "# MQTT Task\n")

    hits = await VaultSearchService.find_notes_by_title("MQTT", kinds=["domain"])

    assert [hit.kind for hit in hits] == ["domain"]


async def test__find_notes_by_title__returns_empty_for_missing_directory(
    obsidian_vault: AsyncPath,
) -> None:
    """A missing search directory yields no hits."""
    _ = obsidian_vault
    assert (
        await VaultSearchService.find_notes_by_title("Anything", kinds=["person"]) == []
    )


async def test__find_notes_by_title__dedupes_and_sorts_by_score(
    obsidian_vault: AsyncPath,
) -> None:
    """Results are sorted by score and limited to the requested count."""
    _ = obsidian_vault
    domains = obsidian_vault / "Domains"
    await domains.mkdir(parents=True)
    await atomic_write_text(domains / "home-assistant.md", "# Home Assistant\n")
    await atomic_write_text(domains / "home.md", "# Home\n")

    hits = await VaultSearchService.find_notes_by_title("Home Assistant", limit=1)

    assert len(hits) == 1
    assert hits[0].title == "Home Assistant"
