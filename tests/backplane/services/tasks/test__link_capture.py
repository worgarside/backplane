"""Tests for linking existing tasks to inbox captures."""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

from backplane.services.obsidian import ObsidianService
from backplane.services.tasks import TaskService
from backplane.utils import today
from backplane.utils.markdown import MarkdownDocument

if TYPE_CHECKING:
    import anyio


async def test__link_capture_sets_task_frontmatter_and_annotates_capture(
    obsidian_vault: anyio.Path,
) -> None:
    """A confirmed capture link updates the task and capture notes."""
    capture_date = today().isoformat()
    inbox = obsidian_vault / ObsidianService.IDEA_INBOX_PATH
    task_path = obsidian_vault / "Tasks" / "review-backup-logs.md"
    await inbox.parent.mkdir(parents=True, exist_ok=True)
    await task_path.parent.mkdir(parents=True, exist_ok=True)
    _ = await inbox.write_text(
        f"""# {capture_date}

## 09:15

Review backup logs
""",
        encoding="utf-8",
    )
    _ = await task_path.write_text(
        """---
type: task
source_capture:
---
# Review backup logs
""",
        encoding="utf-8",
    )

    result = await TaskService.link_capture(
        "review-backup-logs",
        f"{capture_date}T09:15",
    )

    assert result == f"Task review-backup-logs linked to capture {capture_date}T09:15."
    async with MarkdownDocument(
        vault_path=ObsidianService.IDEA_INBOX_PATH,
        read_only=True,
    ) as inbox_doc:
        capture_section = inbox_doc.get_section((capture_date, "09:15"))
        assert capture_section.content == (
            "Review backup logs\n\n↗ \\[[review-backup-logs]\\]"
        )

    async with MarkdownDocument(
        vault_path=pathlib.PurePath("Tasks/review-backup-logs.md"),
        read_only=True,
    ) as task_doc:
        assert task_doc.frontmatter["source_capture"] == f"{capture_date}T09:15"


async def test__link_capture_unknown_capture_does_not_change_task(
    obsidian_vault: anyio.Path,
) -> None:
    """An unknown capture ID returns a safe no-op confirmation."""
    task_path = obsidian_vault / "Tasks" / "review-backup-logs.md"
    await task_path.parent.mkdir(parents=True, exist_ok=True)
    _ = await task_path.write_text(
        """---
type: task
source_capture:
---
# Review backup logs
""",
        encoding="utf-8",
    )

    result = await TaskService.link_capture(
        "review-backup-logs",
        "2026-05-25T21:15",
    )

    assert result == (
        "Capture 2026-05-25T21:15 was not found; task review-backup-logs was not changed."
    )
