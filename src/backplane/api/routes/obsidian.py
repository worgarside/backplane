from __future__ import annotations

from fastapi import APIRouter
from pydantic import PastDate

from backplane.services.obsidian import MarkdownDocument, ObsidianService
from backplane.utils import today

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
