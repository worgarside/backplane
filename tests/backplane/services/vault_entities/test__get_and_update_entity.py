"""Tests for vault entity reads and updates."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from backplane.services.vault_entities import VaultEntityService
from backplane.utils import exc
from backplane.utils.enums import VaultEntityKind

if TYPE_CHECKING:
    import anyio

pytestmark = pytest.mark.usefixtures("obsidian_vault")


async def test__get_entity_returns_rendered_markdown() -> None:
    """Reading an entity returns the note rendered as markdown."""
    _ = await VaultEntityService.create_entity(
        VaultEntityKind.RESOURCE,
        "Geocoding API",
    )

    rendered = await VaultEntityService.get_entity(
        VaultEntityKind.RESOURCE,
        "Geocoding API",
    )

    assert "# Geocoding API" in rendered
    assert "## Overview" in rendered


async def test__get_entity_raises_not_found() -> None:
    """Reading a missing entity raises NotFoundError."""
    with pytest.raises(exc.NotFoundError, match="not found"):
        _ = await VaultEntityService.get_entity(VaultEntityKind.PERSON, "Missing")


async def test__list_entity_sections_returns_section_metadata() -> None:
    """Listing entity sections returns ordered metadata relative to the note title."""
    _ = await VaultEntityService.create_entity(VaultEntityKind.RESOURCE, "Proxmox")

    sections = await VaultEntityService.list_entity_sections(
        VaultEntityKind.RESOURCE,
        "Proxmox",
    )

    assert sections == [
        {"heading": "Overview", "path": ["Overview"], "level": 2},
        {"heading": "Links", "path": ["Links"], "level": 2},
        {"heading": "Related Tasks", "path": ["Related Tasks"], "level": 2},
        {"heading": "Notes", "path": ["Notes"], "level": 2},
    ]


async def test__get_entity_section_returns_rendered_section() -> None:
    """Reading an entity section returns only that section as markdown."""
    _ = await VaultEntityService.create_entity(VaultEntityKind.DOMAIN, "Networking")
    _ = await VaultEntityService.update_entity(
        VaultEntityKind.DOMAIN,
        "Networking",
        section="Overview",
        content="Network architecture and operations.",
        mode="append",
    )

    rendered = await VaultEntityService.get_entity_section(
        VaultEntityKind.DOMAIN,
        "Networking",
        section="Overview",
    )

    assert rendered == "## Overview\n\nNetwork architecture and operations."


async def test__get_entity_section_wraps_missing_section() -> None:
    """Reading a missing entity section returns available-section guidance."""
    _ = await VaultEntityService.create_entity(VaultEntityKind.RESOURCE, "OpenWrt")

    with pytest.raises(exc.InformationRequiredError) as exc_info:
        _ = await VaultEntityService.get_entity_section(
            VaultEntityKind.RESOURCE,
            "OpenWrt",
            section="Missing Section",
        )

    assert "Retry with an existing section" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, exc.SectionNotFoundError)


async def test__update_entity_appends_to_section(obsidian_vault: anyio.Path) -> None:
    """Updates append content to the requested section."""
    _ = await VaultEntityService.create_entity(VaultEntityKind.DOMAIN, "Home Assistant")

    rendered = await VaultEntityService.update_entity(
        VaultEntityKind.DOMAIN,
        "Home Assistant",
        section="Overview",
        content="Primary automation platform.",
        mode="append",
    )

    assert "Primary automation platform." in rendered
    note = await (obsidian_vault / "Domains/home-assistant.md").read_text(
        encoding="utf-8",
    )
    assert "Primary automation platform." in note


async def test__update_entity_bumps_updated_frontmatter(
    obsidian_vault: anyio.Path,
) -> None:
    """Successful updates set the updated frontmatter timestamp."""
    _ = await VaultEntityService.create_entity(VaultEntityKind.PERSON, "Vic")

    _ = await VaultEntityService.update_entity(
        VaultEntityKind.PERSON,
        "Vic",
        section="Notes",
        content="Prefers concise updates.",
    )

    note = await (obsidian_vault / "People/vic.md").read_text(encoding="utf-8")
    assert "updated:" in note
    assert "Prefers concise updates." in note


async def test__update_entity_wraps_missing_section() -> None:
    """Missing sections surface retry guidance instead of a raw not-found error."""
    _ = await VaultEntityService.create_entity(VaultEntityKind.RESOURCE, "MQTT")

    with pytest.raises(exc.InformationRequiredError) as exc_info:
        _ = await VaultEntityService.update_entity(
            VaultEntityKind.RESOURCE,
            "MQTT",
            section="Missing Section",
            content="content",
            create_section_if_not_exists=False,
        )

    assert "create_section_if_not_exists=true" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, exc.SectionNotFoundError)
