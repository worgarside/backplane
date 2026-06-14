"""Tests for task creation orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backplane.services.tasks import (
    CreateTaskResult,
    TaskMetadata,
    TaskService,
)
from backplane.utils import VAULT_PATHS, enums

if TYPE_CHECKING:
    import anyio
    from pytest_mock import MockerFixture


async def test__create_task_skips_missing_inbox_and_avoids_slug_collisions(
    obsidian_vault: anyio.Path,
    mocker: MockerFixture,
) -> None:
    """Missing inbox files are skipped and duplicate task slugs get a suffix."""
    tasks_dir = obsidian_vault / VAULT_PATHS.task_notes_dir
    await tasks_dir.mkdir(parents=True)
    _ = await (obsidian_vault / VAULT_PATHS.task_board_path).write_text(
        "## Backlog\n\n",
        encoding="utf-8",
    )
    _ = await (tasks_dir / "review-backup-logs.md").write_text(
        "# Existing task\n",
        encoding="utf-8",
    )
    metadata = TaskMetadata(
        title="Review backup logs",
        domains=[],
        resources=[],
        projects=[],
        people=[],
        priority=enums.Priority.MEDIUM,
        effort=enums.Effort.MEDIUM,
        next_action="Open the latest backup report.",
    )
    _ = mocker.patch(
        "backplane.services.tasks._extract_metadata",
        new=mocker.AsyncMock(return_value=metadata),
    )

    result = await TaskService.create_task("Review backup logs")

    assert result == CreateTaskResult(
        slug="review-backup-logs-2",
        path=VAULT_PATHS.task_notes_dir / "review-backup-logs-2.md",
        title="Review backup logs",
        matched_capture_id=None,
        candidate_captures=[],
        domains_created=[],
        resources_created=[],
        projects_created=[],
        people_created=[],
    )
    assert await (tasks_dir / "review-backup-logs-2.md").exists()
