"""Kanban board markdown manipulation for Obsidian vault boards."""

from __future__ import annotations

import datetime as dt
import re
from functools import lru_cache
from typing import TYPE_CHECKING, Final

from .exceptions import SectionNotFoundError
from .helpers.files import atomic_write_text
from .settings import SETTINGS

if TYPE_CHECKING:
    import anyio

_NEXT_SECTION_RE: Final = re.compile(r"^## ", re.MULTILINE)


def _format_card_line(slug: str, *, due: dt.date | dt.datetime | None = None) -> str:
    """Build a single Obsidian Kanban task line for ``slug``.

    Returns:
        A markdown task line, optionally including ``@{…}`` due metadata.
    """
    line = f"- [ ] [[{slug}]]"
    if due is None:
        return line

    if isinstance(due, dt.datetime):
        if due.tzinfo is not None:
            due = due.astimezone(SETTINGS.local_timezone)

        due = due.replace(microsecond=0)
        return f"{line} @{{{due.date().isoformat()}}} @@{{{due.strftime('%H:%M')}}}"

    return f"{line} @{{{due.isoformat()}}}"


@lru_cache(maxsize=1024)
def _section_heading_re(section: str) -> re.Pattern[str]:
    return re.compile(rf"^## {re.escape(section)}\s*$", re.MULTILINE)


def add_card_to_list(
    text: str,
    slug: str,
    section: str,
    *,
    due: dt.date | dt.datetime | None = None,
) -> str:
    """Append a Kanban card at the end of a ``##`` section.

    Args:
        text: Full board markdown contents.
        slug: Task slug used as the wiki-link target.
        section: Heading text after ``##`` (e.g. ``Backlog``, ``Todo``).
        due: Optional due date or datetime rendered as Obsidian Kanban ``@{…}`` metadata.

    Returns:
        Updated board markdown.

    Raises:
        SectionNotFoundError: If the section heading is not found in the board file.
    """
    if (match := _section_heading_re(section).search(text)) is None:
        raise SectionNotFoundError(section)

    card_line = _format_card_line(slug, due=due)
    after_header = text[match.end() :]

    if (next_section := _NEXT_SECTION_RE.search(after_header)) is None:
        return f"{text.rstrip()}\n{card_line}\n"

    insert_pos = match.end() + next_section.start()
    before = text[:insert_pos].rstrip()
    after = text[insert_pos:]

    return f"{before}\n{card_line}\n{after}"


async def append_board_card(
    board_path: anyio.Path,
    slug: str,
    *,
    section: str = "Backlog",
    due: dt.date | dt.datetime | None = None,
) -> None:
    """Append a Kanban card at the end of a board column section.

    Args:
        board_path: Absolute path to Tasks/Board.md.
        slug: Task slug used as the wiki-link target.
        section: Heading text after ``##`` (e.g. ``Backlog``, ``Todo``).
        due: Optional due date or datetime rendered as Obsidian Kanban ``@{…}`` metadata.
    """
    text = await board_path.read_text(encoding="utf-8")
    new_text = add_card_to_list(text, slug, section, due=due)
    await atomic_write_text(board_path, new_text)
