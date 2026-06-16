"""Tests for vault entity reads and updates."""

from __future__ import annotations

import pathlib

import pytest

from backplane.services.vault_entities import VaultEntityService
from backplane.utils import AsyncPath, exc
from backplane.utils.enums import VaultEntityKind
from backplane.utils.helpers.files import atomic_write_text
from backplane.utils.settings import SETTINGS

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


async def test__get_entity_works_when_vault_root_is_symlink(
    obsidian_vault: AsyncPath,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Entity reads work when the configured vault root is a symlink."""
    real_vault = pathlib.Path(obsidian_vault.as_posix())
    symlink_parent = real_vault.parent / "vault_symlink_parent"
    symlink_parent.mkdir(exist_ok=True)
    symlink_vault = symlink_parent / "vault"
    if symlink_vault.exists() or symlink_vault.is_symlink():
        symlink_vault.unlink()
    symlink_vault.symlink_to(real_vault, target_is_directory=True)

    monkeypatch.setattr(SETTINGS, "obsidian_vault_path", AsyncPath(symlink_vault))

    _ = await VaultEntityService.create_entity(VaultEntityKind.RESOURCE, "Symlink Test")
    rendered = await VaultEntityService.get_entity(
        VaultEntityKind.RESOURCE,
        "Symlink Test",
    )

    assert "# Symlink Test" in rendered


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
        heading_path=["Overview"],
        content="Network architecture and operations.",
        mode="append",
    )

    rendered = await VaultEntityService.get_entity_section(
        VaultEntityKind.DOMAIN,
        "Networking",
        heading_path=["Overview"],
    )

    assert rendered == "## Overview\n\nNetwork architecture and operations."


async def test__get_entity_section_uses_document_h1_not_caller_name(
    obsidian_vault: AsyncPath,
) -> None:
    """Section reads use the note H1 even when the entity is resolved by filename."""
    domains = obsidian_vault / "Domains"
    await domains.mkdir(parents=True)
    await atomic_write_text(
        domains / "home-assistant.md",
        """---
type: domain
---
# Home Assistant Platform

## Overview

Platform notes.
""",
    )

    rendered = await VaultEntityService.get_entity_section(
        VaultEntityKind.DOMAIN,
        "home-assistant",
        heading_path=["Overview"],
    )

    assert "Platform notes." in rendered


async def test__get_entity_section_wraps_missing_section() -> None:
    """Reading a missing entity section returns available-section guidance."""
    _ = await VaultEntityService.create_entity(VaultEntityKind.RESOURCE, "OpenWrt")

    with pytest.raises(exc.InformationRequiredError) as exc_info:
        _ = await VaultEntityService.get_entity_section(
            VaultEntityKind.RESOURCE,
            "OpenWrt",
            heading_path=["Missing Section"],
        )

    assert "Retry with an existing section" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, exc.SectionNotFoundError)


async def test__update_entity_appends_to_section(obsidian_vault: AsyncPath) -> None:
    """Updates append content to the requested section."""
    _ = await VaultEntityService.create_entity(VaultEntityKind.DOMAIN, "Home Assistant")

    rendered = await VaultEntityService.update_entity(
        VaultEntityKind.DOMAIN,
        "Home Assistant",
        heading_path=["Overview"],
        content="Primary automation platform.",
        mode="append",
    )

    assert "Primary automation platform." in rendered
    note = await (obsidian_vault / "Domains/Home Assistant.md").read_text(
        encoding="utf-8",
    )
    assert "Primary automation platform." in note


async def test__update_entity_bumps_updated_frontmatter(
    obsidian_vault: AsyncPath,
) -> None:
    """Successful updates set the updated frontmatter timestamp."""
    _ = await VaultEntityService.create_entity(VaultEntityKind.PERSON, "Alice")

    _ = await VaultEntityService.update_entity(
        VaultEntityKind.PERSON,
        "Alice",
        heading_path=["Notes"],
        content="Prefers concise updates.",
    )

    note = await (obsidian_vault / "People/Alice.md").read_text(encoding="utf-8")
    assert "updated:" in note
    assert "Prefers concise updates." in note


async def test__update_entity_wraps_missing_section() -> None:
    """Missing sections surface retry guidance instead of a raw not-found error."""
    _ = await VaultEntityService.create_entity(VaultEntityKind.RESOURCE, "MQTT")

    with pytest.raises(exc.InformationRequiredError) as exc_info:
        _ = await VaultEntityService.update_entity(
            VaultEntityKind.RESOURCE,
            "MQTT",
            heading_path=["Missing Section"],
            content="content",
            create_section_if_not_exists=False,
        )

    assert "create_section_if_not_exists=true" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, exc.SectionNotFoundError)
