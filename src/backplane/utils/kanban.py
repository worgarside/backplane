"""Kanban board markdown manipulation for Obsidian vault boards."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from backplane.utils.helpers.files import atomic_write_text

if TYPE_CHECKING:
    import anyio

_NEXT_SECTION_RE: Final = re.compile(r"^## ", re.MULTILINE)


def _section_heading_re(section: str) -> re.Pattern[str]:
    return re.compile(rf"^## {re.escape(section)}\s*$", re.MULTILINE)


def add_card_to_list(text: str, slug: str, section: str) -> str:
    """Append a Kanban card at the end of a ``##`` section.

    Args:
        text: Full board markdown contents.
        slug: Task slug used as the wiki-link target.
        section: Heading text after ``##`` (e.g. ``Backlog``, ``Todo``).

    Returns:
        Updated board markdown.

    Raises:
        ValueError: If the section heading is not found in the board file.
    """
    match = _section_heading_re(section).search(text)
    if match is None:
        msg = f"## {section} section not found in Tasks/Board.md"
        raise ValueError(msg)

    after_header = text[match.end() :]
    next_section = _NEXT_SECTION_RE.search(after_header)
    if next_section is None:
        return f"{text.rstrip()}\n- [ ] [[{slug}]]\n"

    insert_pos = match.end() + next_section.start()
    before = text[:insert_pos].rstrip()
    after = text[insert_pos:]
    return f"{before}\n- [ ] [[{slug}]]\n{after}"


async def append_board_card(
    board_path: anyio.Path,
    slug: str,
    *,
    section: str = "Backlog",
) -> None:
    """Append a Kanban card at the end of a board column section.

    Args:
        board_path: Absolute path to Tasks/Board.md.
        slug: Task slug used as the wiki-link target.
        section: Heading text after ``##`` (e.g. ``Backlog``, ``Todo``).
    """
    text = await board_path.read_text(encoding="utf-8")
    new_text = add_card_to_list(text, slug, section)
    await atomic_write_text(board_path, new_text)
