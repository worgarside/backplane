"""API routes for CRUD operations on Obsidian notes."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, PastDate

from backplane.services.obsidian import ObsidianService
from backplane.utils import format_human_date, today
from backplane.utils.markdown import MarkdownDocument, MarkdownSection  # noqa: TC001

router = APIRouter(prefix="/obsidian", tags=["obsidian"])

DailyNoteDate = Annotated[
    PastDate | None,
    Query(description="Date of the daily note. Defaults to today's UTC date."),
]


@router.get("/daily-note")
async def get_daily_note(date: DailyNoteDate = None) -> MarkdownDocument:
    """Get today's daily note content.

    Args:
        date: Date of the daily note. Defaults to today's UTC date.

    Returns:
        The daily note content.
    """
    async with ObsidianService().daily_note(date=date, read_only=True) as daily_note:
        return daily_note


class PatchDailyNoteRequest(BaseModel):
    """Request body for updating a section in the daily note."""

    heading_path: Annotated[
        tuple[str, ...],
        Field(
            description=(
                "The headings to traverse to the section to update. Does not need to include the "
                "top-level date heading."
            ),
            min_length=1,
        ),
    ]
    content: str
    mode: Literal["append", "prepend", "replace"] = "append"


@router.patch("/daily-note")
async def update_daily_note(
    request: PatchDailyNoteRequest,
    date: DailyNoteDate = None,
) -> MarkdownSection | None:
    """Update a section in the daily note.

    Args:
        request: The request body.
        date: The date of the daily note. Defaults to today's UTC date.

    Returns:
        The updated section.
    """
    date = date or today()

    if request.heading_path[0] != (
        daily_note_top_level_heading := format_human_date(date)
    ):
        request.heading_path = (daily_note_top_level_heading, *request.heading_path)

    async with ObsidianService().daily_note(
        date=date,
        create_if_not_exists=True,
        read_only=False,
    ) as daily_note:
        section = daily_note.get_section(request.heading_path)

        if not section.content or request.mode == "replace":
            section.content = request.content
        elif request.mode == "append":
            section.content += "\n" + request.content
        elif request.mode == "prepend":
            section.content = request.content + "\n" + section.content

        print(daily_note.render())  # noqa: T201

    return section
