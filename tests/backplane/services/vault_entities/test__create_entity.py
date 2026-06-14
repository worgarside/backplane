"""Tests for vault entity creation."""

from __future__ import annotations

import anyio
import pytest

from backplane.services.vault_entities import VaultEntityService
from backplane.utils import VAULT_PATHS, exc
from backplane.utils.enums import VaultEntityKind
from backplane.utils.helpers.files import atomic_write_text


async def test__create_entity_uses_template_shape(obsidian_vault: anyio.Path) -> None:
    """Created entity notes include template frontmatter and section headings."""
    metadata = await VaultEntityService.create_entity(
        VaultEntityKind.DOMAIN,
        "Home Assistant",
    )

    text = await (obsidian_vault / metadata.path).read_text(encoding="utf-8")
    assert "type: domain" in text
    assert "# Home Assistant" in text
    assert "## Overview" in text
    assert "## Key Resources" in text
    assert "## Notes" in text
    assert "{{title}}" not in text
    assert "{ date:YYYY-MM-DDTHH:mm:ss }" not in text


async def test__create_entity_supports_projects(obsidian_vault: anyio.Path) -> None:
    """Project entity notes are created under Projects from the project template."""
    metadata = await VaultEntityService.create_entity(
        VaultEntityKind.PROJECT,
        "Garage Migration",
    )

    text = await (obsidian_vault / metadata.path).read_text(encoding="utf-8")
    board = await (obsidian_vault / VAULT_PATHS.project_board_path).read_text(
        encoding="utf-8",
    )
    assert metadata.path == "Projects/Garage Migration.md"
    assert "type: project" in text
    assert "# Garage Migration" in text
    assert "## Goals" in text
    assert "## Tasks" in text
    assert "## Notes" in text
    assert "- [ ] [[Projects/Garage Migration|Garage Migration]]" in board


async def test__create_entity_does_not_add_non_projects_to_board(
    obsidian_vault: anyio.Path,
) -> None:
    """Only project notes are appended to the project Kanban board."""
    board_before = await (obsidian_vault / VAULT_PATHS.project_board_path).read_text(
        encoding="utf-8",
    )

    _ = await VaultEntityService.create_entity(
        VaultEntityKind.DOMAIN,
        "Home Assistant",
    )

    board_after = await (obsidian_vault / VAULT_PATHS.project_board_path).read_text(
        encoding="utf-8",
    )
    assert board_after == board_before


async def test__create_entity_raises_conflict_for_duplicate(
    obsidian_vault: anyio.Path,
) -> None:
    """Creating an entity with an existing name raises ConflictError."""
    domains = obsidian_vault / "Domains"
    await domains.mkdir(parents=True)
    await atomic_write_text(domains / "Home Assistant.md", "# Home Assistant\n")

    with pytest.raises(exc.ConflictError, match="already exists"):
        _ = await VaultEntityService.create_entity(
            VaultEntityKind.DOMAIN,
            "Home Assistant",
        )


async def test__create_entity_appends_provenance_note(obsidian_vault: anyio.Path) -> None:
    """Optional provenance text is appended to the Notes section."""
    metadata = await VaultEntityService.create_entity(
        VaultEntityKind.DOMAIN,
        "Home Assistant",
        provenance_note="Created automatically from task intake for [[task]].",
    )

    text = await (obsidian_vault / metadata.path).read_text(encoding="utf-8")
    assert "Created automatically from task intake for [[task]]." in text
