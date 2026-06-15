"""Tests for vault entity MCP tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backplane.mcp import vault_entities
from backplane.services.vault_entities import VaultEntityService
from backplane.utils import build_vault_note_metadata
from backplane.utils.async_path import AsyncPath
from backplane.utils.enums import VaultEntityKind
from backplane.utils.helpers.files import atomic_write_text

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


async def test__list_vault_entities__returns_json_names(mocker: MockerFixture) -> None:
    """The list tool returns entity names as a JSON array."""
    mock_list = mocker.patch(
        "backplane.mcp.vault_entities.VaultEntityService.list_entities",
        new=mocker.AsyncMock(return_value=["Home Assistant", "Obsidian"]),
    )

    result = await vault_entities.list_vault_entities(kind="domain")

    assert result == ["Home Assistant", "Obsidian"]
    _ = mock_list.assert_awaited_once()


async def test__list_vault_entity_sections__returns_json_sections(
    mocker: MockerFixture,
) -> None:
    """The section list tool returns section metadata as JSON."""
    mock_list_sections = mocker.patch(
        "backplane.mcp.vault_entities.VaultEntityService.list_entity_sections",
        new=mocker.AsyncMock(
            return_value=[
                {"heading": "Overview", "path": ["Overview"], "level": 2},
            ],
        ),
    )

    result = await vault_entities.list_vault_entity_sections(
        kind="resource",
        name="MQTT",
    )

    assert result == [
        {"heading": "Overview", "path": ["Overview"], "level": 2},
    ]
    _ = mock_list_sections.assert_awaited_once()


async def test__get_vault_entity__delegates_to_service(mocker: MockerFixture) -> None:
    """The get tool delegates to VaultEntityService.get_entity."""
    mock_get = mocker.patch(
        "backplane.mcp.vault_entities.VaultEntityService.get_entity",
        new=mocker.AsyncMock(return_value="# Home Assistant\n"),
    )

    result = await vault_entities.get_vault_entity(kind="domain", name="Home Assistant")

    assert result == "# Home Assistant\n"
    _ = mock_get.assert_awaited_once()


async def test__get_vault_entity_section__delegates_to_service(
    mocker: MockerFixture,
) -> None:
    """The section get tool delegates to VaultEntityService.get_entity_section."""
    mock_get_section = mocker.patch(
        "backplane.mcp.vault_entities.VaultEntityService.get_entity_section",
        new=mocker.AsyncMock(return_value="## Overview\n\nAutomation platform.\n"),
    )

    result = await vault_entities.get_vault_entity_section(
        kind="domain",
        name="Home Assistant",
        heading_path=["Overview"],
    )

    assert result == "## Overview\n\nAutomation platform.\n"
    _ = mock_get_section.assert_awaited_once()


async def test__create_vault_entity__returns_confirmation(mocker: MockerFixture) -> None:
    """The create tool returns JSON metadata for the created note."""
    mock_create = mocker.patch(
        "backplane.mcp.vault_entities.VaultEntityService.create_entity",
        new=mocker.AsyncMock(
            return_value=build_vault_note_metadata(
                kind=VaultEntityKind.PROJECT,
                title="Garage Migration",
                path=AsyncPath("Projects/Garage Migration.md"),
            ),
        ),
    )

    result = await vault_entities.create_vault_entity(
        kind="project",
        name="Garage Migration",
    )

    assert result.path == AsyncPath("Projects/Garage Migration.md")
    assert result.canonical_link == "[[Projects/Garage Migration|Garage Migration]]"
    _ = mock_create.assert_awaited_once_with(VaultEntityKind.PROJECT, "Garage Migration")


async def test__update_vault_entity__delegates_to_service(mocker: MockerFixture) -> None:
    """The update tool delegates to VaultEntityService.update_entity."""
    mock_update = mocker.patch(
        "backplane.mcp.vault_entities.VaultEntityService.update_entity",
        new=mocker.AsyncMock(return_value="## Overview\n\nUpdated.\n"),
    )

    result = await vault_entities.update_vault_entity(
        kind="resource",
        name="MQTT",
        heading_path=["Overview"],
        content="Updated.",
        mode="append",
    )

    assert "Updated." in result
    _ = mock_update.assert_awaited_once()


async def test__list_vault_entities__integration(obsidian_vault: AsyncPath) -> None:
    """The list tool reads entity names from the vault."""
    domains = obsidian_vault / "Domains"
    await domains.mkdir(parents=True)
    await atomic_write_text(domains / "home-assistant.md", "# Home Assistant\n")

    result = await vault_entities.list_vault_entities(kind="domain")

    assert result == await VaultEntityService.list_entities(
        VaultEntityKind.DOMAIN,
    )
