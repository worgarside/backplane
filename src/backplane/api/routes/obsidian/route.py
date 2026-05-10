"""API routes for CRUD operations on Obsidian notes."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import PastDate  # noqa: TC002

from backplane.services.obsidian import ObsidianService
from backplane.utils import today
from backplane.utils.markdown import MarkdownDocument  # noqa: TC001

router = APIRouter(prefix="/obsidian", tags=["obsidian"])


@router.get("/daily-note")
async def get_daily_note(date: PastDate | None = None) -> MarkdownDocument:
    """Get today's daily note content.

    Args:
        date: Date of the daily note. Defaults to today's UTC date.

    Returns:
        The daily note content.
    """
    async with ObsidianService().daily_note(date=date or today()) as daily_note:
        return daily_note
