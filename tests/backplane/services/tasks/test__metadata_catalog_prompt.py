"""Tests for task metadata catalog prompt generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backplane.services.tasks import _metadata_catalog_prompt

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


async def test__metadata_catalog_prompt_returns_empty_string_without_entities(
    mocker: MockerFixture,
) -> None:
    """No catalog entities produce no extra prompt text."""
    mocker.patch(
        "backplane.services.tasks.VaultEntityService.list_entities",
        new=mocker.AsyncMock(side_effect=[[], [], []]),
    )

    assert not await _metadata_catalog_prompt()


async def test__metadata_catalog_prompt_includes_available_entity_groups(
    mocker: MockerFixture,
) -> None:
    """Available domains, resources, and people are included in the prompt."""
    mocker.patch(
        "backplane.services.tasks.VaultEntityService.list_entities",
        new=mocker.AsyncMock(
            side_effect=[
                ["Home Assistant"],
                ["MQTT"],
                ["Jordan"],
            ],
        ),
    )

    prompt = await _metadata_catalog_prompt()

    assert prompt == (
        "Existing domains (prefer exact spelling when applicable): Home Assistant\n"
        "Existing resources (prefer exact spelling when applicable): MQTT\n"
        "Existing people (prefer exact spelling when applicable): Jordan"
    )
