"""Tests for task entity stub creation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backplane.utils.async_path import AsyncPath

# pyright: reportPrivateUsage=false
from backplane.services.tasks import _create_stubs, _ensure_stub
from backplane.utils import VAULT_PATHS
from backplane.utils.helpers.files import atomic_write_text


async def test__ensure_stub_creates_missing_note(obsidian_vault: AsyncPath) -> None:
    """A missing entity note is created from the vault template with provenance."""
    created = await _ensure_stub(
        "Home Assistant",
        "domain",
        "review-home-assistant",
    )

    assert created is True
    text = await (obsidian_vault / "Domains/Home Assistant.md").read_text(
        encoding="utf-8",
    )
    assert "# Home Assistant" in text
    assert "## Overview" in text
    assert "## Notes" in text
    assert "Created automatically from task intake for review-home-assistant." in text


async def test__ensure_stub_returns_false_for_existing_note(
    obsidian_vault: AsyncPath,
) -> None:
    """Existing entity notes are left unchanged."""
    domains = obsidian_vault / "Domains"
    await domains.mkdir(parents=True)
    existing = domains / "home-assistant.md"
    await atomic_write_text(existing, "# Existing\n")

    created = await _ensure_stub(
        "Home Assistant",
        "domain",
        "review-home-assistant",
    )

    assert created is False
    assert await existing.read_text(encoding="utf-8") == "# Existing\n"


async def test__ensure_stub_creates_project_note(obsidian_vault: AsyncPath) -> None:
    """Project stub notes are created from the project template."""
    created = await _ensure_stub(
        "Garage Migration",
        "project",
        "plan-garage-migration",
    )

    assert created is True
    text = await (obsidian_vault / "Projects/Garage Migration.md").read_text(
        encoding="utf-8",
    )
    assert "# Garage Migration" in text
    assert "## Goals" in text
    assert "## Tasks" in text
    assert "Created automatically from task intake for plan-garage-migration." in text
    board = await (obsidian_vault / VAULT_PATHS.project_board_path).read_text(
        encoding="utf-8",
    )
    assert "- [ ] [[Projects/Garage Migration|Garage Migration]]" in board


async def test__create_stubs_returns_only_newly_created_names(
    obsidian_vault: AsyncPath,
) -> None:
    """Bulk stub creation reports names that were actually created."""
    domains = obsidian_vault / "Domains"
    await domains.mkdir(parents=True)
    await atomic_write_text(domains / "existing.md", "# Existing\n")

    created = await _create_stubs(
        ["Existing", "New Domain"],
        "domain",
        "review-home-assistant",
    )

    assert created == ["New Domain"]
