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
    INBOX_DIRECTORY: Final = pathlib.PurePath("Inbox")
    PROJECTS_ACTIVE_DIRECTORY: Final = pathlib.PurePath("Projects/Active")

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
            date: Date of the daily note. Defaults to today's local date.
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

    @asynccontextmanager
    async def idea_inbox(self) -> AsyncGenerator[MarkdownDocument]:
        """Open the idea inbox for editing, flushing on successful exit.

        Yields:
            Loaded markdown document for the idea inbox.
        """
        async with MarkdownDocument(
            vault_path=self.INBOX_DIRECTORY / "Ideas.md",
            read_only=False,
        ) as idea_inbox:
            yield idea_inbox

    @asynccontextmanager
    async def project_inbox(self) -> AsyncGenerator[MarkdownDocument]:
        """Open the project capture audit log for editing.

        Yields:
            Loaded markdown document for the project inbox.
        """
        async with MarkdownDocument(
            vault_path=self.INBOX_DIRECTORY / "Projects.md",
            create_if_not_exists=True,
            read_only=False,
        ) as project_inbox:
            yield project_inbox

    async def _unique_project_slug(self, base: str) -> str:
        """Resolve ``base`` to a slug that doesn't collide with an existing folder.

        Appends ``-2``, ``-3``, ... until an unused folder name is found.

        Args:
            base: Desired slug.

        Returns:
            The first available slug starting from ``base``.
        """
        parent = SETTINGS.obsidian_vault_path / self.PROJECTS_ACTIVE_DIRECTORY
        candidate = base
        suffix = 2
        while await (parent / candidate).exists():
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    async def create_project(
        self,
        *,
        slug_base: str,
        project_content: str,
        board_content: str,
    ) -> tuple[str, pathlib.PurePath]:
        """Create a new project folder with ``Project.md`` and ``Board.md``.

        Resolves ``slug_base`` to an unused folder name (appending a numeric
        suffix on collision), creates the folder, and writes both notes.

        Args:
            slug_base: Desired folder slug; suffixed to avoid overwriting an existing project.
            project_content: Markdown body to write as ``Project.md``.
            board_content: Markdown body to write as ``Board.md``.

        Returns:
            Tuple of ``(resolved_slug, project_folder_vault_path)``.
        """
        slug = await self._unique_project_slug(slug_base)
        folder_vault_path = self.PROJECTS_ACTIVE_DIRECTORY / slug
        folder = SETTINGS.obsidian_vault_path / folder_vault_path
        await folder.mkdir(parents=True, exist_ok=False)
        _ = await (folder / "Project.md").write_text(project_content, encoding="utf-8")
        _ = await (folder / "Board.md").write_text(board_content, encoding="utf-8")
        return slug, folder_vault_path
