"""Tests for the create_task MCP tool."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from backplane.mcp import tasks
from backplane.services.tasks import CaptureCandidate, CreateTaskResult
from backplane.utils import VAULT_PATHS, build_vault_note_metadata, enums

_CANDIDATE_SNIPPET_MAX_LEN = 80

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def _task_result(
    *,
    title: str,
    slug: str,
    matched_capture_id: str | None = None,
    candidate_captures: list[CaptureCandidate] | None = None,
) -> CreateTaskResult:
    """Build a sample create-task result for MCP tool tests."""
    note_path = VAULT_PATHS.task_notes_dir / f"{title}.md"
    return CreateTaskResult(
        title=title,
        slug=slug,
        path=note_path,
        metadata=build_vault_note_metadata(
            kind="task",
            title=title,
            path=str(note_path),
        ),
        matched_capture_id=matched_capture_id,
        candidate_captures=candidate_captures or [],
        domains_created=[],
        resources_created=[],
        projects_created=[],
        people_created=[],
    )


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
        return_value=_task_result(title=returned_title, slug=returned_slug),
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

    payload = json.loads(result)
    assert payload["title"] == returned_title
    assert payload["slug"] == returned_slug
    assert "_message" not in payload
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
        return_value=_task_result(
            title="Review backup logs",
            slug="review-backup-logs",
            matched_capture_id="2026-05-25T21:15",
        ),
    )
    mock_task_service = mocker.patch("backplane.mcp.tasks.TaskService")
    mock_task_service.return_value.create_task = mock_create_task  # pyright: ignore[reportAny]

    result = await tasks.create_task(
        description="backup logs",
    )

    payload = json.loads(result)
    assert payload["_message"] == "Matched inbox capture from 2026-05-25T21:15."


async def test__create_task__logs_success_response(
    mocker: MockerFixture,
) -> None:
    """Successful task creation logs the service result and response string."""
    mock_info = mocker.patch("backplane.mcp.tasks.logger.info")
    mock_create_task = mocker.AsyncMock(
        return_value=_task_result(title="Review backup logs", slug="review-backup-logs"),
    )
    mock_task_service = mocker.patch("backplane.mcp.tasks.TaskService")
    mock_task_service.return_value.create_task = mock_create_task  # pyright: ignore[reportAny]

    _ = await tasks.create_task(description="Review backup logs")

    assert any(
        "create_task succeeded" in str(call.args[0])  # pyright: ignore[reportAny]
        for call in mock_info.call_args_list
    )


async def test__create_task__candidate_capture_is_included_in_confirmation(
    mocker: MockerFixture,
) -> None:
    """Near matches are offered without failing task creation."""
    mock_create_task = mocker.AsyncMock(
        return_value=_task_result(
            title="Update rain alert notification",
            slug="update-rain-alert-notification",
            candidate_captures=[
                CaptureCandidate(
                    id="2026-05-17T01:44",
                    text=("I need to create reminder notifications for the mood tracker"),
                ),
            ],
        ),
    )
    mock_task_service = mocker.patch("backplane.mcp.tasks.TaskService")
    mock_task_service.return_value.create_task = mock_create_task  # pyright: ignore[reportAny]

    result = await tasks.create_task(description="Update rain alert notification")

    payload = json.loads(result)
    assert "2026-05-17T01:44" in payload["_message"]
    assert (
        "I need to create reminder notifications for the mood tracker"
        in payload["_message"]
    )


async def test__create_task__long_candidate_snippet_is_truncated(
    mocker: MockerFixture,
) -> None:
    """Long candidate snippets are truncated in the confirmation."""
    long_text = (
        "I need to investigate the automated backup verification system because "
        "the notifications have been failing intermittently for the past week"
    )
    mock_create_task = mocker.AsyncMock(
        return_value=_task_result(
            title="Fix backup notifications",
            slug="fix-backup-notifications",
            candidate_captures=[
                CaptureCandidate(id="2026-05-17T01:44", text=long_text),
            ],
        ),
    )
    mock_task_service = mocker.patch("backplane.mcp.tasks.TaskService")
    mock_task_service.return_value.create_task = mock_create_task  # pyright: ignore[reportAny]

    result = await tasks.create_task(description="Fix backup notifications")

    message = json.loads(result)["_message"]
    snippet = message.split("'")[1]
    assert snippet.endswith("...")
    assert len(snippet) == _CANDIDATE_SNIPPET_MAX_LEN


async def test__create_task__forwards_link_capture_id(
    mocker: MockerFixture,
) -> None:
    """An explicit capture link is forwarded to the task service."""
    mock_create_task = mocker.AsyncMock(
        return_value=_task_result(
            title="Review backup logs",
            slug="review-backup-logs",
            matched_capture_id="2026-05-25T21:15",
        ),
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
