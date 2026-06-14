"""Tests for task metadata catalog prompt generation."""

from __future__ import annotations

# pyright: reportPrivateUsage=false
from typing import TYPE_CHECKING

from backplane.services.tasks import _metadata_catalog_prompt

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


async def test__metadata_catalog_prompt_returns_empty_string_without_entities(
    mocker: MockerFixture,
) -> None:
    """No catalog entities produce no extra prompt text."""
    _ = mocker.patch(
        "backplane.services.tasks.VaultEntityService.list_entities",
        new=mocker.AsyncMock(side_effect=[[], [], [], []]),
    )

    assert not await _metadata_catalog_prompt()


async def test__metadata_catalog_prompt_includes_available_entity_groups(
    mocker: MockerFixture,
) -> None:
    """Available domains, resources, projects, and people are included in the prompt."""
    _ = mocker.patch(
        "backplane.services.tasks.VaultEntityService.list_entities",
        new=mocker.AsyncMock(
            side_effect=[
                ["Home Assistant"],
                ["MQTT"],
                ["Garage Migration"],
                ["Jordan"],
            ],
        ),
    )

    prompt = await _metadata_catalog_prompt()

    assert prompt == (
        "Existing domains (prefer exact spelling when applicable): Home Assistant\n"
        "Existing resources (prefer exact spelling when applicable): MQTT\n"
        "Existing projects (prefer exact spelling when applicable): Garage Migration\n"
        "Existing people (prefer exact spelling when applicable): Jordan"
    )
