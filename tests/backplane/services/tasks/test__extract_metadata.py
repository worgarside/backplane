"""Tests for task metadata extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backplane.services.tasks import TaskMetadata, _extract_metadata
from backplane.utils import enums

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@dataclass(frozen=True, slots=True)
class FakeMetadataResult:
    """Metadata agent result shape consumed by extraction."""

    output: TaskMetadata


async def test__extract_metadata_returns_defaults_when_agent_fails(
    mocker: MockerFixture,
) -> None:
    """Agent failures fall back to deterministic task metadata."""
    mocker.patch(
        "backplane.services.tasks._metadata_catalog_prompt",
        new=mocker.AsyncMock(return_value=""),
    )
    mock_agent = mocker.Mock()
    mock_agent.run = mocker.AsyncMock(side_effect=RuntimeError("boom"))
    mocker.patch("backplane.services.tasks._metadata_agent", return_value=mock_agent)

    metadata = await _extract_metadata(
        "Install the hallway motion sensor",
        None,
        None,
    )

    assert metadata == TaskMetadata(
        title="Install the hallway motion sensor",
        domains=[],
        resources=[],
        people=[],
        priority=enums.Priority.MEDIUM,
        effort=enums.Effort.MEDIUM,
        next_action="",
    )


async def test__extract_metadata_applies_catalog_and_user_overrides(
    mocker: MockerFixture,
) -> None:
    """Catalog text is sent to the agent and explicit fields win."""
    mocker.patch(
        "backplane.services.tasks._metadata_catalog_prompt",
        new=mocker.AsyncMock(return_value="Existing domains: Home Assistant"),
    )
    mock_agent = mocker.Mock()
    mock_agent.run = mocker.AsyncMock(
        return_value=FakeMetadataResult(
            output=TaskMetadata(
                title="Generated title",
                domains=["Home Assistant", "MQTT"],
                resources=["mqtt"],
                people=["Jordan"],
                priority=enums.Priority.LOW,
                effort=enums.Effort.SMALL,
                next_action="Install the sensor.",
            ),
        ),
    )
    mocker.patch("backplane.services.tasks._metadata_agent", return_value=mock_agent)
    mocker.patch("backplane.services.tasks._log_metadata_agent_run")

    metadata = await _extract_metadata(
        "Install the hallway motion sensor",
        "Install hallway sensor",
        enums.Priority.HIGH,
    )

    assert metadata == TaskMetadata(
        title="Install hallway sensor",
        domains=["Home Assistant"],
        resources=["mqtt"],
        people=["Jordan"],
        priority=enums.Priority.HIGH,
        effort=enums.Effort.SMALL,
        next_action="Install the sensor.",
    )
    mock_agent.run.assert_awaited_once()
    assert mock_agent.run.await_args is not None
    prompt = str(mock_agent.run.await_args.args[0])  # pyright: ignore[reportAny]
    assert "Existing domains: Home Assistant" in prompt
    assert "Title already provided: 'Install hallway sensor'" in prompt
    assert "Priority already provided: <Priority.HIGH: 'high'>" in prompt
