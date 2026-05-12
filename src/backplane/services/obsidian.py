"""Helpers for reading and editing Obsidian markdown notes."""

from __future__ import annotations

import pathlib
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Final, final

from backplane.utils import today
from backplane.utils.markdown import MarkdownDocument

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import AsyncGenerator


@final
class ObsidianService:
    """Service for interacting with the Obsidian vault."""

    DAILY_NOTE_DIRECTORY: Final = pathlib.PurePath("Daily Notes")

    @asynccontextmanager
    async def daily_note(
        self,
        date: dt.date | None = None,
    ) -> AsyncGenerator[MarkdownDocument]:
        """Open a daily note for editing, flushing on successful exit.

        Args:
            date: Date of the daily note. Defaults to today's UTC date.

        Yields:
            Loaded markdown document for the requested daily note.
        """
        date = date or today()

        async with MarkdownDocument(
            vault_path=self.DAILY_NOTE_DIRECTORY / f"{date.isoformat()}.md",
        ) as daily_note:  # pyright: ignore[reportCallIssue]
            yield daily_note
