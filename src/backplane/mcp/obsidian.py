"""MCP tools and resources for the Obsidian vault."""

from __future__ import annotations

import datetime as dt  # used at runtime by FastMCP schema introspection
import json
import pathlib
import re
from typing import TYPE_CHECKING, Annotated, Literal, cast

from pydantic import Field, PastDate

from backplane.services.obsidian import ObsidianService
from backplane.utils import format_human_date, today
from backplane.utils.markdown import MarkdownSection
from backplane.utils.settings import SETTINGS

from .server import mcp

if TYPE_CHECKING:
    from backplane.utils.markdown import MarkdownDocument

_HEADING_LINE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_CODE_FENCE = re.compile(r"^\s*```")


def _read_template_text() -> str | None:
    """Resolve and read the daily-note template configured for the vault.

    Returns:
        Raw template text, or ``None`` if the config or template file is missing
        or malformed.
    """
    vault = pathlib.Path(str(SETTINGS.obsidian_vault_path))

    config_path = vault / ".obsidian" / "daily-notes.json"
    try:
        raw = config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None

    try:
        parsed = json.loads(raw)  # pyright: ignore[reportAny]
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    rel = cast("dict[str, object]", parsed).get("template")
    if not isinstance(rel, str) or not rel:
        return None

    template_path = vault / (rel if rel.endswith(".md") else f"{rel}.md")
    try:
        return template_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _format_template_heading_tree(template_text: str) -> str:
    """Parse template markdown for headings and return an indented bullet tree.

    The level-1 heading (the date heading) is dropped — it is added
    automatically by the tool and is not user-facing as a section name.

    Args:
        template_text: Raw markdown of the daily-note template.

    Returns:
        Indented bullet list of headings, or a fallback message if the template
        has no sub-sections.
    """
    in_code = False
    lines: list[str] = []
    for line in template_text.splitlines():
        if _CODE_FENCE.match(line):
            in_code = not in_code
            continue
        if in_code:
            continue
        match = _HEADING_LINE.match(line)
        if match is None:
            continue
        level = len(match.group(1))
        if level == 1:
            continue
        indent = "  " * (level - 2)
        lines.append(f"{indent}- {match.group(2)}")

    return "\n".join(lines) if lines else "(template has no sub-sections)"


def _load_template_heading_tree() -> str:
    """Return a formatted tree of the daily-note template's headings."""
    template_text = _read_template_text()
    if template_text is None:
        return "(template structure unavailable)"
    return _format_template_heading_tree(template_text)


_TEMPLATE_TREE = _load_template_heading_tree()

_ADD_DESCRIPTION = (
    "Add content to a section of the user's Obsidian daily note. Use this when "
    "the user wants to capture something into their daily note.\n\n"
    "The user's daily-note template defines this section structure (prefer these "
    "names verbatim):\n"
    f"{_TEMPLATE_TREE}\n\n"
    "If the user explicitly asks for a section not listed above, set "
    "`create_section_if_not_exists=true` — this creates the section and is the "
    "correct and supported action in that case. Do not decline or ask for "
    "clarification; just call the tool with that flag set.\n\n"
    "If the section is missing and `create_section_if_not_exists=false` (the "
    "default), the call returns the actual sections in today's note so you can "
    "either match an existing one or retry with the flag set to true."
)


def _find_deepest_existing(
    doc: MarkdownDocument,
    heading_path: tuple[str, ...],
) -> tuple[MarkdownSection | None, tuple[str, ...]]:
    """Walk ``heading_path`` and return (deepest_existing, missing_tail).

    Args:
        doc: The loaded daily-note document.
        heading_path: The full heading path to resolve.

    Returns:
        Tuple of (the deepest section that exists, the remaining headings that
        need creating). If no prefix matches, the first element is ``None``.
    """
    for length in range(len(heading_path), 0, -1):
        try:
            section = doc.get_section(heading_path[:length])
        except ValueError:
            continue
        return section, heading_path[length:]
    return None, heading_path


def _siblings_of(
    doc: MarkdownDocument,
    parent: MarkdownSection | None,
) -> list[str]:
    """Return the headings of the children of ``parent`` (or document roots).

    Args:
        doc: The loaded daily-note document.
        parent: The parent section, or ``None`` for the document root.

    Returns:
        Heading text for each child in document order.
    """
    container = doc.body if parent is None else parent.sections
    return [s.heading for s in container]


@mcp.tool(description=_ADD_DESCRIPTION)
async def add_to_daily_note(
    *,
    heading_path: Annotated[
        tuple[str, ...],
        Field(
            description=(
                "The headings to traverse to the section to update. Pick based on "
                "the content and the section structure provided in the tool "
                "description. The top-level date heading is added automatically — "
                "do not include it."
            ),
            min_length=1,
        ),
    ],
    content: Annotated[str, Field(description="The text to add to the section.")],
    mode: Annotated[
        Literal["append", "prepend", "replace"],
        Field(
            description=(
                "How to combine `content` with any existing section text. `append` "
                "is almost always the right choice for voice capture; use `replace` "
                "only when the user explicitly asks to overwrite."
            ),
        ),
    ] = "append",
    create_section_if_not_exists: Annotated[
        bool,
        Field(
            description=(
                "Set to true to create the section (and any missing ancestors) when "
                "it doesn't exist. Set to false (default) to fail with a list of "
                "available sections so you can pick the right one. Use true when the "
                "user explicitly asks for a new section, or when retrying after a "
                "missing-section error and creation is the right resolution."
            ),
        ),
    ] = False,
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
        create_section_if_not_exists: Set true to create the section (and any missing
            ancestors) if it doesn't exist; false returns an error listing available
            sections.
        date: The date of the daily note. Defaults to today's UTC date.

    Returns:
        The updated section, rendered as markdown.

    Raises:
        ValueError: If the section is missing and ``create_section_if_not_exists`` is false.
    """
    date = date or today()

    if heading_path[0] != (daily_note_top_level_heading := format_human_date(date)):
        heading_path = (daily_note_top_level_heading, *heading_path)

    async with ObsidianService().daily_note(
        date=date,
        create_if_not_exists=True,
        read_only=False,
    ) as daily_note:
        parent, missing = _find_deepest_existing(daily_note, heading_path)

        if missing and not create_section_if_not_exists:
            parent_repr = parent.heading if parent is not None else "(document root)"
            siblings = _siblings_of(daily_note, parent)
            siblings_repr = ", ".join(siblings) if siblings else "(none)"
            msg = (
                f"Section {missing[0]!r} not found under {parent_repr!r}. "
                f"Existing sections there: {siblings_repr}. "
                f"Retry with an existing section, or set "
                f"`create_section_if_not_exists=true` to create it."
            )
            raise ValueError(msg)

        section = parent
        for heading in missing:
            new_level = (section.level if section is not None else 0) + 1
            new_section = MarkdownSection(heading=heading, level=new_level)
            container = daily_note.body if section is None else section.sections
            container.append(new_section)
            section = new_section

        assert section is not None  # narrowed by heading_path min_length=1  # noqa: S101

        if not section.content or mode == "replace":
            section.replace_content(content)
        elif mode == "append":
            section.append_content(content)
        elif mode == "prepend":
            section.prepend_content(content)

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


@mcp.tool(
    description=(
        """Record a new idea in the Obsidian idea inbox.

Use this when the user mentions:
- an idea
- something they could build
- something worth investigating
- a possible automation/improvement
- a future project

Preserve the user's original wording as closely as possible."""
    ),
)
async def record_idea(
    *,
    idea: Annotated[str, Field(description="The idea to record.")],
) -> str:
    """Record a new idea in the Obsidian idea inbox.

    Args:
        idea: The idea to record.

    Returns:
        A confirmation message.
    """
    now = dt.datetime.now(dt.UTC)

    async with ObsidianService().idea_inbox() as idea_inbox:
        section = idea_inbox.get_section((
            now.strftime("# %Y-%m-%d"),
            now.strftime("## %H:%M"),
        ))

        section.append_content(idea)

    return "Idea recorded successfully."


# ------------------------------------------------------------
# Resources


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
