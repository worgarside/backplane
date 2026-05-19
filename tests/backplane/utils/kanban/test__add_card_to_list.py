"""Tests for Kanban column card insertion."""

from __future__ import annotations

import pytest

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
    result = add_card_to_list(_SAMPLE_BOARD, "new-task", "Backlog")
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
    assert add_card_to_list(board, "solo", "Backlog") == (
        "## Backlog\n- [ ] [[solo]]\n## Todo\n"
    )


def test__add_card_to_list_missing_section() -> None:
    """Missing section heading raises a clear error."""
    with pytest.raises(ValueError, match="## Backlog"):
        _ = add_card_to_list("## Todo\n", "x", "Backlog")


def test__add_card_to_list_other_column() -> None:
    """Cards can be added to any board column by section name."""
    board = "## Backlog\n\n## Todo\n- [ ] [[old]]\n\n## Done\n"
    result = add_card_to_list(board, "new-todo", "Todo")
    assert result == (
        "## Backlog\n\n## Todo\n- [ ] [[old]]\n- [ ] [[new-todo]]\n## Done\n"
    )
