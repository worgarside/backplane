"""Tests for Kanban column card insertion."""

from __future__ import annotations

import datetime as dt

import pytest

from backplane.utils.async_path import AsyncPath
from backplane.utils.exceptions import SectionNotFoundError
from backplane.utils.kanban import add_card_to_list

_SAMPLE_BOARD = """---

kanban-plugin: board

---

## Backlog

- [ ] [[existing-task]]

## Todo

## In Progress
"""


def test__add_card_to_list_appends_before_next_section() -> None:
    """New cards are appended at the end of the target column."""
    result = add_card_to_list(_SAMPLE_BOARD, AsyncPath("new-task.md"), "Backlog")
    assert result == (
        "---\n\n"
        "kanban-plugin: board\n\n"
        "---\n\n"
        "## Backlog\n\n"
        "- [ ] [[existing-task]]\n"
        "- [ ] [[new-task]]\n"
        "## Todo\n\n"
        "## In Progress\n"
    )


def test__add_card_to_list_empty_section() -> None:
    """An empty section still accepts a new card."""
    board = "## Backlog\n\n## Todo\n"
    assert add_card_to_list(board, AsyncPath("solo.md"), "Backlog") == (
        "## Backlog\n- [ ] [[solo]]\n## Todo\n"
    )


def test__add_card_to_list_missing_section() -> None:
    """Missing section heading raises a clear error."""
    with pytest.raises(SectionNotFoundError, match="Backlog") as exc_info:
        _ = add_card_to_list("## Todo\n", AsyncPath("x.md"), "Backlog")

    assert exc_info.value.section == "Backlog"


def test__add_card_to_list_other_column() -> None:
    """Cards can be added to any board column by section name."""
    board = "## Backlog\n\n## Todo\n- [ ] [[old]]\n\n## Done\n"
    result = add_card_to_list(board, AsyncPath("new-todo.md"), "Todo")
    assert result == (
        "## Backlog\n\n## Todo\n- [ ] [[old]]\n- [ ] [[new-todo]]\n## Done\n"
    )


def test__add_card_to_list_with_due_date() -> None:
    """Due dates use Obsidian Kanban ``@{YYYY-MM-DD}`` metadata."""
    board = "## ToDo\n- [ ] todo1 @{2026-05-16}\n## Done\n"
    result = add_card_to_list(
        board,
        AsyncPath("new-task.md"),
        "ToDo",
        due=dt.date(2026, 5, 20),
    )
    assert result == (
        "## ToDo\n- [ ] todo1 @{2026-05-16}\n- [ ] [[new-task]] @{2026-05-20}\n## Done\n"
    )


def test__add_card_to_list_with_due_datetime() -> None:
    """Due datetimes use separate ``@{date}`` and ``@@{HH:MM}`` tokens in local time."""
    board = "## ToDo\n\n## Done\n"
    result = add_card_to_list(
        board,
        AsyncPath("timed.md"),
        "ToDo",
        due=dt.datetime(2026, 5, 20, 14, 30, tzinfo=dt.UTC),
    )
    assert result == "## ToDo\n- [ ] [[timed]] @{2026-05-20} @@{14:30}\n## Done\n"
