"""Helpers for reading and editing Obsidian markdown notes."""

from __future__ import annotations

import datetime as dt  # noqa: TC003
import json
import pathlib
import re
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Final, cast, final

from backplane.utils import today
from backplane.utils.helpers import format_obsidian_moment_date
from backplane.utils.markdown import MarkdownDocument
from backplane.utils.settings import SETTINGS

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

_DATE_TEMPLATE = re.compile(r"\{\{\s*date\s*(?::([^}]*))?\s*\}\}", re.IGNORECASE)


def substitute_obsidian_core_date_variables(template: str, date: dt.date) -> str:
    """Replace ``{{date}}`` and ``{{date:...}}`` placeholders (Obsidian core template syntax).

    Args:
        template: Raw template file contents.
        date: Calendar date used for substitution.

    Returns:
        Template text with date placeholders expanded.
    """

    def _replace(match: re.Match[str]) -> str:
        inner = match.group(1)
        if inner is None or not inner.strip():
            return date.isoformat()
        return format_obsidian_moment_date(date, inner.strip())

    return _DATE_TEMPLATE.sub(_replace, template)


@final
class ObsidianService:
    """Service for interacting with the Obsidian vault."""

    DAILY_NOTE_DIRECTORY: Final = pathlib.PurePath("Daily Notes")

    @staticmethod
    async def _daily_note_template_source() -> str | None:
        """Load the daily note template file configured in ``.obsidian/daily-notes.json``.

        Returns:
            Raw template file contents, or ``None`` if config or template is missing.
        """
        config_path = SETTINGS.obsidian_vault_path / ".obsidian" / "daily-notes.json"
        try:
            raw = await config_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

        try:
            parsed_unknown = json.loads(raw)  # pyright: ignore[reportAny]
        except json.JSONDecodeError:
            return None

        if not isinstance(parsed_unknown, dict):
            return None

        data = cast("dict[str, object]", parsed_unknown)
        rel = data.get("template")
        if not isinstance(rel, str) or not rel:
            return None

        path_str = rel if rel.endswith(".md") else f"{rel}.md"
        template_path = SETTINGS.obsidian_vault_path / path_str
        try:
            return await template_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

    @asynccontextmanager
    async def daily_note(
        self,
        date: dt.date | None = None,
        *,
        create_if_not_exists: bool = False,
        read_only: bool = True,
    ) -> AsyncGenerator[MarkdownDocument]:
        """Open a daily note for editing, flushing on successful exit.

        Args:
            date: Date of the daily note. Defaults to today's UTC date.
            create_if_not_exists: If true, create the note when missing using the vault's
                daily note template from ``.obsidian/daily-notes.json`` when configured.
            read_only: When true, require file content unchanged on exit (no accidental writes).

        Yields:
            Loaded markdown document for the requested daily note.
        """
        date = date or today()
        vault_path = self.DAILY_NOTE_DIRECTORY / f"{date.isoformat()}.md"
        full_path = SETTINGS.obsidian_vault_path / vault_path

        initial_content: str | None = None
        if (
            create_if_not_exists
            and not await full_path.exists()
            and (template := await ObsidianService._daily_note_template_source())
            is not None
        ):
            initial_content = substitute_obsidian_core_date_variables(template, date)

        async with MarkdownDocument(
            vault_path=vault_path,
            create_if_not_exists=create_if_not_exists,
            initial_content=initial_content,
            read_only=read_only,
        ) as daily_note:
            yield daily_note
