"""Tests for the create_task MCP tool."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from backplane.mcp import tasks
from backplane.utils import enums

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.parametrize(
    (
        "description",
        "title",
        "due",
        "priority",
        "returned_title",
        "returned_slug",
    ),
    [
        (
            "Review backup logs",
            None,
            None,
            None,
            "Review backup logs",
            "review-backup-logs",
        ),
        (
            "Install the hallway sensor before Friday",
            "Install hallway sensor",
            "2026-05-29",
            enums.Priority.HIGH,
            "Install hallway sensor",
            "install-hallway-sensor",
        ),
    ],
)
async def test__create_task__forwards_fields_to_task_service(
    mocker: MockerFixture,
    description: str,
    title: str | None,
    due: str | None,
    priority: enums.Priority | None,
    returned_title: str,
    returned_slug: str,
) -> None:
    """Task fields are forwarded while omitted optional values default to None."""
    mock_create_task = mocker.AsyncMock(
        return_value={
            "title": returned_title,
            "slug": returned_slug,
            "matched_capture_id": None,
            "candidate_captures": [],
        },
    )
    mock_task_service = mocker.patch("backplane.mcp.tasks.TaskService")
    mock_task_service.return_value.create_task = mock_create_task  # pyright: ignore[reportAny]

    result = await tasks.create_task(
        description=description,
        title=title,
        due=due,
        priority=priority,
        link_capture_id=None,
    )

    assert result == f"Task '{returned_title}' created at Tasks/{returned_slug}.md."
    assert "Matched inbox capture" not in result
    mock_task_service.assert_called_once_with()
    mock_create_task.assert_awaited_once_with(
        description,
        title=title,
        due=due,
        priority=priority,
        link_capture_id=None,
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
            "candidate_captures": [],
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
            "candidate_captures": [],
        },
    )
    mock_task_service = mocker.patch("backplane.mcp.tasks.TaskService")
    mock_task_service.return_value.create_task = mock_create_task  # pyright: ignore[reportAny]

    _ = await tasks.create_task(description="Review backup logs")

    assert any(
        "create_task succeeded" in str(call.args[0]) for call in mock_info.call_args_list
    )


async def test__create_task__candidate_capture_is_included_in_confirmation(
    mocker: MockerFixture,
) -> None:
    """Near matches are offered without failing task creation."""
    mock_create_task = mocker.AsyncMock(
        return_value={
            "title": "Update rain alert notification",
            "slug": "update-rain-alert-notification",
            "matched_capture_id": None,
            "candidate_captures": [
                {
                    "id": "2026-05-17T01:44",
                    "text": "I need to create reminder notifications for the mood tracker",
                },
            ],
        },
    )
    mock_task_service = mocker.patch("backplane.mcp.tasks.TaskService")
    mock_task_service.return_value.create_task = mock_create_task  # pyright: ignore[reportAny]

    result = await tasks.create_task(description="Update rain alert notification")

    assert result == (
        "Task 'Update rain alert notification' created at "
        "Tasks/update-rain-alert-notification.md. This looked similar to "
        "2026-05-17T01:44 ('I need to create reminder notifications for the mood "
        "tracker'); say 'link it to 2026-05-17T01:44' to connect that capture."
    )


async def test__create_task__forwards_link_capture_id(
    mocker: MockerFixture,
) -> None:
    """An explicit capture link is forwarded to the task service."""
    mock_create_task = mocker.AsyncMock(
        return_value={
            "title": "Review backup logs",
            "slug": "review-backup-logs",
            "matched_capture_id": "2026-05-25T21:15",
            "candidate_captures": [],
        },
    )
    mock_task_service = mocker.patch("backplane.mcp.tasks.TaskService")
    mock_task_service.return_value.create_task = mock_create_task  # pyright: ignore[reportAny]

    _ = await tasks.create_task(
        description="backup logs",
        link_capture_id="2026-05-25T21:15",
    )

    mock_create_task.assert_awaited_once_with(
        "backup logs",
        title=None,
        due=None,
        priority=None,
        link_capture_id="2026-05-25T21:15",
    )


async def test__link_task_to_capture__forwards_fields(
    mocker: MockerFixture,
) -> None:
    """The follow-up linking tool delegates to the task service."""
    mock_link_capture = mocker.AsyncMock(
        return_value="Task review-backup-logs linked to capture 2026-05-25T21:15.",
    )
    mock_task_service = mocker.patch("backplane.mcp.tasks.TaskService")
    mock_task_service.return_value.link_capture = mock_link_capture  # pyright: ignore[reportAny]

    result = await tasks.link_task_to_capture(
        task_slug="review-backup-logs",
        capture_id="2026-05-25T21:15",
    )

    assert result == "Task review-backup-logs linked to capture 2026-05-25T21:15."
    mock_link_capture.assert_awaited_once_with(
        "review-backup-logs",
        "2026-05-25T21:15",
    )
