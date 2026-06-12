"""Tests for vault entity MCP tools."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import anyio

from backplane.mcp import vault_entities
from backplane.services.vault_entities import VaultEntityService
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

    assert json.loads(result) == ["Home Assistant", "Obsidian"]
    mock_list.assert_awaited_once()


async def test__get_vault_entity__delegates_to_service(mocker: MockerFixture) -> None:
    """The get tool delegates to VaultEntityService.get_entity."""
    mock_get = mocker.patch(
        "backplane.mcp.vault_entities.VaultEntityService.get_entity",
        new=mocker.AsyncMock(return_value="# Home Assistant\n"),
    )

    result = await vault_entities.get_vault_entity(kind="domain", name="Home Assistant")

    assert result == "# Home Assistant\n"
    mock_get.assert_awaited_once()


async def test__create_vault_entity__returns_confirmation(mocker: MockerFixture) -> None:
    """The create tool returns a concise confirmation with the vault path."""
    mock_create = mocker.patch(
        "backplane.mcp.vault_entities.VaultEntityService.create_entity",
        new=mocker.AsyncMock(return_value=anyio.Path("Domains/home-assistant.md")),
    )

    result = await vault_entities.create_vault_entity(
        kind="domain",
        name="Home Assistant",
    )

    assert result == "Created domain 'Home Assistant' at Domains/home-assistant.md."
    mock_create.assert_awaited_once()


async def test__update_vault_entity__delegates_to_service(mocker: MockerFixture) -> None:
    """The update tool delegates to VaultEntityService.update_entity."""
    mock_update = mocker.patch(
        "backplane.mcp.vault_entities.VaultEntityService.update_entity",
        new=mocker.AsyncMock(return_value="## Overview\n\nUpdated.\n"),
    )

    result = await vault_entities.update_vault_entity(
        kind="resource",
        name="MQTT",
        section="Overview",
        content="Updated.",
        mode="append",
    )

    assert "Updated." in result
    mock_update.assert_awaited_once()


async def test__list_vault_entities__integration(obsidian_vault: anyio.Path) -> None:
    """The list tool reads entity names from the vault."""
    domains = obsidian_vault / "Domains"
    await domains.mkdir(parents=True)
    await atomic_write_text(domains / "home-assistant.md", "# Home Assistant\n")

    result = await vault_entities.list_vault_entities(kind="domain")

    assert json.loads(result) == await VaultEntityService.list_entities(
        VaultEntityKind.DOMAIN,
    )
