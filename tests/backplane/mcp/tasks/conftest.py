"""Shared fixtures for MCP task tool tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from backplane.services.tasks import CaptureCandidate, CreateTaskResult
from backplane.utils import VAULT_PATHS, build_vault_note_metadata

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def make_create_task_result() -> Callable[..., CreateTaskResult]:
    """Build sample create-task results for MCP tool tests."""

    def _make_create_task_result(
        *,
        title: str,
        slug: str,
        matched_capture_id: str | None = None,
        candidate_captures: list[CaptureCandidate] | None = None,
    ) -> CreateTaskResult:
        note_path = VAULT_PATHS.task_notes_dir / f"{title}.md"
        return CreateTaskResult(
            title=title,
            slug=slug,
            path=note_path,
            metadata=build_vault_note_metadata(
                kind="task",
                title=title,
                path=note_path,
            ),
            matched_capture_id=matched_capture_id,
            candidate_captures=candidate_captures or [],
            domains_created=[],
            resources_created=[],
            projects_created=[],
            people_created=[],
        )

    return _make_create_task_result
