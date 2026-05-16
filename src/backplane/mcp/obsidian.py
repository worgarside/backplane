"""MCP tools and resources for the Obsidian vault."""

from __future__ import annotations

import datetime as dt  # noqa: TC003  # used at runtime by FastMCP schema introspection
from typing import Annotated, Literal

from pydantic import Field, PastDate

from backplane.services.obsidian import ObsidianService
from backplane.utils import format_human_date, today

from .server import mcp


@mcp.tool(
    description=(
        "Add content to a section of the user's Obsidian daily note. Use this when "
        "the user wants to capture something into their daily note — tasks, ideas, "
        "reminders, journal entries, or anything they want to record for the day. "
        "The note is created from the vault's daily note template if it doesn't yet "
        "exist."
    ),
)
async def add_to_daily_note(
    heading_path: Annotated[
        tuple[str, ...],
        Field(
            description=(
                "The headings to traverse to the section to update. Pick based on the "
                "content: e.g. ('Tasks',) for actionable items, ('Ideas',) for thoughts "
                "to revisit, ('Notes',) for general capture. If unsure, default to "
                "('Notes',). Nest deeper only when the user explicitly references a "
                "subsection. The top-level date heading is added automatically — do not "
                "include it."
            ),
            min_length=1,
        ),
    ],
    content: Annotated[str, Field(description="The text to add to the section.")],
    mode: Annotated[
        Literal["append", "prepend", "replace"],
        Field(
            description=(
                "How to combine `content` with any existing section text. `append` is "
                "almost always the right choice for voice capture; use `replace` only "
                "when the user explicitly asks to overwrite."
            ),
        ),
    ] = "append",
    date: Annotated[
        PastDate | None,
        Field(description="The date of the daily note. Defaults to today's UTC date."),
    ] = None,
) -> str:
    """Add content to a section of the user's Obsidian daily note.

    Args:
        heading_path: The headings to traverse to the section to update.
        content: The text to add to the section.
        mode: How to combine ``content`` with any existing section text.
        date: The date of the daily note. Defaults to today's UTC date.

    Returns:
        The updated section, rendered as markdown.
    """
    date = date or today()

    if heading_path[0] != (daily_note_top_level_heading := format_human_date(date)):
        heading_path = (daily_note_top_level_heading, *heading_path)

    async with ObsidianService().daily_note(
        date=date,
        create_if_not_exists=True,
        read_only=False,
    ) as daily_note:
        section = daily_note.get_section(heading_path)

        if not section.content or mode == "replace":
            section.content = content
        elif mode == "append":
            section.content += "\n" + content
        elif mode == "prepend":
            section.content = content + "\n" + section.content

    return section.render()


@mcp.tool(
    description=(
        "Read the user's Obsidian daily note. Use this when the user asks what's in "
        "their daily note, wants to review tasks/ideas/notes they've captured, or "
        "needs context about their day to answer a follow-up question."
    ),
)
async def get_daily_note(
    date: Annotated[
        PastDate | None,
        Field(description="The date of the daily note. Defaults to today's UTC date."),
    ] = None,
) -> str:
    """Read the user's Obsidian daily note.

    Args:
        date: The date of the daily note. Defaults to today's UTC date.

    Returns:
        The daily note, rendered as markdown.
    """
    async with ObsidianService().daily_note(date=date, read_only=True) as daily_note:
        return daily_note.render()


@mcp.resource(
    uri="obsidian://daily-note/today",
    name="Today's Daily Note",
    description="The user's Obsidian daily note for today's date.",
    mime_type="text/markdown",
)
async def daily_note_today_resource() -> str:
    """Return today's daily note as rendered markdown."""
    async with ObsidianService().daily_note(date=today(), read_only=True) as daily_note:
        return daily_note.render()


@mcp.resource(
    uri="obsidian://daily-note/{date}",
    name="Daily Note by Date",
    description=(
        "The user's Obsidian daily note for a given ISO date (YYYY-MM-DD), e.g. "
        "obsidian://daily-note/2026-05-16."
    ),
    mime_type="text/markdown",
)
async def daily_note_by_date_resource(date: dt.date) -> str:
    """Return the daily note for the given ISO date as rendered markdown.

    Args:
        date: ISO date string (YYYY-MM-DD).

    Returns:
        The rendered markdown of the daily note.
    """
    async with ObsidianService().daily_note(date=date, read_only=True) as daily_note:
        return daily_note.render()
