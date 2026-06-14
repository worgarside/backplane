"""Tests for which text is passed to task metadata extraction."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from backplane.services.obsidian import ObsidianService
from backplane.services.tasks import TaskMetadata, TaskService
from backplane.utils import VAULT_PATHS, enums, today

if TYPE_CHECKING:
    import anyio
    from pytest_mock import MockerFixture


@pytest.mark.anyio
async def test__create_task_uses_matched_capture_text_for_metadata(
    obsidian_vault: anyio.Path,
    mocker: MockerFixture,
) -> None:
    """Metadata extraction should use the inbox capture text, not the short query."""
    capture_date = today().isoformat()
    capture_text = (
        "Add Jordan's calendar feed to the shared dashboard and notify them "
        "when meetings change."
    )
    inbox = obsidian_vault / ObsidianService.IDEA_INBOX_PATH
    board = obsidian_vault / VAULT_PATHS.task_board_path
    await inbox.parent.mkdir(parents=True, exist_ok=True)
    await board.parent.mkdir(parents=True, exist_ok=True)
    _ = await board.write_text("## Backlog\n\n", encoding="utf-8")
    _ = await inbox.write_text(
        f"""# {capture_date}

## 14:30

{capture_text}
""",
        encoding="utf-8",
    )

    metadata = TaskMetadata(
        title="Stub",
        domains=[],
        resources=[],
        projects=[],
        people=["Jordan"],
        priority=enums.Priority.MEDIUM,
        effort=enums.Effort.MEDIUM,
        next_action="",
    )
    extract = mocker.patch(
        "backplane.services.tasks._extract_metadata",
        new=mocker.AsyncMock(return_value=metadata),
    )

    _ = await TaskService.create_task("calendar dashboard")

    _ = extract.assert_awaited_once_with(capture_text, None, None)
