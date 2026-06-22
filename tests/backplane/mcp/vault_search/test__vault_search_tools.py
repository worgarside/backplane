"""Tests for vault search MCP tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backplane.mcp import vault_search
from backplane.services.vault_search import VaultNoteSearchHit
from backplane.utils.async_path import AsyncPath

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


async def test__find_vault_notes__delegates_to_service(mocker: MockerFixture) -> None:
    """The find tool delegates to VaultSearchService.find_notes_by_title."""
    mock_find = mocker.patch(
        "backplane.mcp.vault_search.VaultSearchService.find_notes_by_title",
        new=mocker.AsyncMock(
            return_value=[
                VaultNoteSearchHit(
                    kind="domain",
                    title="Home Assistant",
                    path=AsyncPath("Domains/home-assistant.md"),
                    score=100.0,
                ),
            ],
        ),
    )

    result = await vault_search.find_vault_notes(
        query="Home Assistant",
        kinds=["domain"],
        limit=5,
    )

    assert result[0].title == "Home Assistant"
    _ = mock_find.assert_awaited_once_with(
        "Home Assistant",
        kinds=["domain"],
        limit=5,
    )


async def test__search_vault_notes__delegates_to_service(mocker: MockerFixture) -> None:
    """The search tool delegates to VaultSearchService.search_note_contents."""
    mock_search = mocker.patch(
        "backplane.mcp.vault_search.VaultSearchService.search_note_contents",
        new=mocker.AsyncMock(
            return_value=[
                VaultNoteSearchHit(
                    kind="resource",
                    title="MQTT Broker",
                    path=AsyncPath("Resources/mqtt-broker.md"),
                    score=80.0,
                    excerpt="Configure the local MQTT broker",
                ),
            ],
        ),
    )

    result = await vault_search.search_vault_notes(
        query="MQTT broker",
        kinds=["resource"],
        limit=10,
    )

    assert result[0].excerpt == "Configure the local MQTT broker"
    _ = mock_search.assert_awaited_once_with(
        "MQTT broker",
        kinds=["resource"],
        limit=10,
    )
