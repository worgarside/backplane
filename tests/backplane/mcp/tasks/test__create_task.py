"""Tests for the create_task MCP tool."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from backplane.mcp import tasks
from backplane.utils import enums

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


async def test__create_task__omitted_due_defaults_to_none(
    mocker: MockerFixture,
) -> None:
    """An omitted due date should be forwarded to the service as None."""
    mock_create_task = mocker.AsyncMock(
        return_value={
            "title": "Review backup logs",
            "slug": "review-backup-logs",
            "matched_capture_id": None,
        },
    )
    mock_task_service = mocker.patch("backplane.mcp.tasks.TaskService")
    mock_task_service.return_value.create_task = mock_create_task  # pyright: ignore[reportAny]

    result = await tasks.create_task(
        description="Review backup logs",
    )

    assert result == "Task 'Review backup logs' created at Tasks/review-backup-logs.md."
    assert "Matched inbox capture" not in result
    mock_task_service.assert_called_once_with()
    mock_create_task.assert_awaited_once_with(
        "Review backup logs",
        title=None,
        due=None,
        priority=None,
    )


async def test__create_task__provided_due_is_forwarded_to_task_service(
    mocker: MockerFixture,
) -> None:
    """A provided due date should be forwarded with the other task fields."""
    mock_create_task = mocker.AsyncMock(
        return_value={
            "title": "Install hallway sensor",
            "slug": "install-hallway-sensor",
            "matched_capture_id": None,
        },
    )
    mock_task_service = mocker.patch("backplane.mcp.tasks.TaskService")
    mock_task_service.return_value.create_task = mock_create_task  # pyright: ignore[reportAny]

    result = await tasks.create_task(
        description="Install the hallway sensor before Friday",
        title="Install hallway sensor",
        due="2026-05-29",
        priority=enums.Priority.HIGH,
    )

    assert (
        result
        == "Task 'Install hallway sensor' created at Tasks/install-hallway-sensor.md."
    )
    mock_create_task.assert_awaited_once_with(
        "Install the hallway sensor before Friday",
        title="Install hallway sensor",
        due="2026-05-29",
        priority=enums.Priority.HIGH,
    )


async def test__create_task__matched_capture_is_included_in_confirmation(
    mocker: MockerFixture,
) -> None:
    """A matched inbox capture should be mentioned in the confirmation."""
    mock_create_task = mocker.AsyncMock(
        return_value={
            "title": "Review backup logs",
            "slug": "review-backup-logs",
            "matched_capture_id": "2026-05-25T21:15",
        },
    )
    mock_task_service = mocker.patch("backplane.mcp.tasks.TaskService")
    mock_task_service.return_value.create_task = mock_create_task  # pyright: ignore[reportAny]

    result = await tasks.create_task(
        description="backup logs",
    )

    assert result == (
        "Task 'Review backup logs' created at Tasks/review-backup-logs.md. "
        "Matched inbox capture from 2026-05-25T21:15."
    )


async def test__create_task__logs_success_response(
    mocker: MockerFixture,
) -> None:
    """Successful task creation logs the service result and response string."""
    mock_info = mocker.patch("backplane.mcp.tasks.logger.info")
    mock_create_task = mocker.AsyncMock(
        return_value={
            "title": "Review backup logs",
            "slug": "review-backup-logs",
            "matched_capture_id": None,
        },
    )
    mock_task_service = mocker.patch("backplane.mcp.tasks.TaskService")
    mock_task_service.return_value.create_task = mock_create_task  # pyright: ignore[reportAny]

    _ = await tasks.create_task(description="Review backup logs")

    assert any(
        "create_task succeeded" in str(call.args[0]) for call in mock_info.call_args_list
    )


async def test__create_task__logs_warning_and_reraises_ambiguous_match(
    mocker: MockerFixture,
) -> None:
    """Ambiguous inbox matches are logged at WARNING and re-raised."""
    mock_warning = mocker.patch("backplane.mcp.tasks.logger.warning")
    mock_create_task = mocker.AsyncMock(
        side_effect=ValueError("Ambiguous match (score=60)."),
    )
    mock_task_service = mocker.patch("backplane.mcp.tasks.TaskService")
    mock_task_service.return_value.create_task = mock_create_task  # pyright: ignore[reportAny]

    with pytest.raises(ValueError, match="Ambiguous match"):
        await tasks.create_task(description="something vague")

    mock_warning.assert_called_once()
