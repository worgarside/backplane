"""Tests for rendering task notes."""

from __future__ import annotations

import datetime as dt

from backplane.services.tasks import Capture, TaskMetadata, _build_task_note
from backplane.utils import VAULT_PATHS, enums


def test__build_task_note_serializes_enum_frontmatter_as_strings() -> None:
    """Priority and effort enums are rendered as plain YAML scalars."""
    capture = Capture(
        id="2026-05-25T21:15",
        date="2026-05-25",
        time="21:15",
        text="Review backup logs",
        path=VAULT_PATHS.inbox_dir / "Ideas.md",
    )
    metadata = TaskMetadata(
        title="Review backup logs",
        domains=["Infrastructure"],
        resources=["Backups"],
        people=[],
        priority=enums.Priority.HIGH,
        effort=enums.Effort.SMALL,
        next_action="Open the latest backup report.",
    )

    note = _build_task_note(
        title=metadata.title,
        now=dt.datetime(2026, 5, 25, 21, 30, tzinfo=dt.UTC),
        metadata=metadata,
        capture=capture,
        description="backup logs",
        due="2026-05-29",
    )

    assert "priority: high\n" in note
    assert "effort: small\n" in note
    assert "source_capture: 2026-05-25T21:15\n" in note
    assert "> Review backup logs\n" in note
