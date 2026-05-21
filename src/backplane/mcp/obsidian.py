"""MCP tools and resources for the Obsidian vault."""

from __future__ import annotations

import datetime as dt  # used at runtime by FastMCP schema introspection
import json
import pathlib
import re
import unicodedata
from typing import Annotated, Literal, cast

from loguru import logger
from pydantic import Field, PastDate

from backplane.services.obsidian import ObsidianService
from backplane.utils import exc, format_human_date, today
from backplane.utils.settings import SETTINGS

from .server import mcp

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
        Field(description="The date of the daily note. Defaults to today's local date."),
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
        date: The date of the daily note. Defaults to today's local date.

    Returns:
        The updated section, rendered as markdown.

    Raises:
        InformationRequiredError: If the section is missing and ``create_section_if_not_exists`` is false.
    """
    date = date or today()
    logger.info(
        "add_to_daily_note: date={} heading={} mode={} create={}",
        date,
        heading_path,
        mode,
        create_section_if_not_exists,
    )

    if heading_path[0] != (daily_note_top_level_heading := format_human_date(date)):
        heading_path = (daily_note_top_level_heading, *heading_path)

    async with ObsidianService().daily_note(
        date=date,
        create_if_not_exists=True,
        read_only=False,
    ) as daily_note:
        try:
            section = daily_note.get_section(
                heading_path,
                create_if_not_exists=create_section_if_not_exists,
            )
        except exc.SectionNotFoundError as err:
            raise exc.InformationRequiredError(
                message=(
                    f"{err} Retry with an existing section, or set "
                    "`create_section_if_not_exists=true` to create it."
                ),
                detail=err.detail,
            ) from err

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
        Field(description="The date of the daily note. Defaults to today's local date."),
    ] = None,
) -> str:
    """Read the user's Obsidian daily note.

    Args:
        date: The date of the daily note. Defaults to today's local date.

    Returns:
        The daily note, rendered as markdown.
    """
    logger.info("get_daily_note: date={}", date)
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

You should convert the idea from a spoken phrase to a written sentence, but the user's original wording
should be preserved as closely as possible."""
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
    logger.info("record_idea")
    now = dt.datetime.now(tz=SETTINGS.local_timezone)
    heading_path = (now.strftime("%Y-%m-%d"), now.strftime("%H:%M"))

    async with ObsidianService().idea_inbox() as idea_inbox:
        section = idea_inbox.get_section(heading_path, create_if_not_exists=True)
        section.append_content(idea)

    return "Idea recorded successfully."


_SLUG_FALLBACK = "untitled-project"
_SLUG_MAX_LENGTH = 60
_NON_SLUG_CHARS = re.compile(r"[^a-z0-9]+")


def _slugify(title: str) -> str:
    """Convert ``title`` to a filesystem-safe kebab-case slug.

    Diacritics are stripped, non-alphanumerics collapse to single hyphens, and
    the result is truncated to keep folder names manageable. Falls back to a
    placeholder when the input contains no usable characters.

    Args:
        title: Free-form project title.

    Returns:
        A lowercase ASCII slug.
    """
    decomposed = unicodedata.normalize("NFKD", title)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    cleaned = _NON_SLUG_CHARS.sub("-", ascii_only.lower()).strip("-")
    truncated = cleaned[:_SLUG_MAX_LENGTH].rstrip("-")
    return truncated or _SLUG_FALLBACK


_BOARD_NOTE_CONTENT = """\
---
kanban-plugin: board
---

## Inbox

## Backlog

## Next

## Doing

## Blocked

## Done
"""


def _yaml_string_list(items: list[str]) -> str:
    """Render ``items`` as a YAML value to follow ``key:`` in a mapping line.

    Empty lists render inline as `` []`` (space-prefixed so the caller writes
    ``key:`` without a trailing space). Non-empty lists become a leading
    newline followed by indented block entries with JSON-quoted scalars
    (JSON-quoted strings are valid YAML double-quoted scalars and safely
    escape any special characters in the input).

    Args:
        items: List items to render.

    Returns:
        A string to append directly after the ``key:`` of a YAML mapping line.
    """
    if not items:
        return " []"
    return "\n" + "\n".join(f"  - {json.dumps(item)}" for item in items)


def _project_frontmatter(
    *,
    created: dt.date,
    domains: list[str],
    resources: list[str],
) -> str:
    """Render the YAML frontmatter block for a new project note.

    Args:
        created: Date to use for both ``created`` and ``updated`` fields.
        domains: Related domain note names.
        resources: Related resource note names.

    Returns:
        A YAML frontmatter block including the opening and closing ``---`` lines.
    """
    created_iso = created.isoformat()
    return (
        "---\n"
        "type: project\n"
        "status: active\n"
        f"created: {created_iso}\n"
        f"updated: {created_iso}\n"
        f"domains:{_yaml_string_list(domains)}\n"
        f"resources:{_yaml_string_list(resources)}\n"
        "tags:\n"
        "  - project\n"
        "source: assist\n"
        "---\n"
    )


def _bullets(items: list[str], *, task: bool = False) -> str:
    """Render ``items`` as a markdown bullet list (empty string when no items).

    Args:
        items: List items to render.
        task: When true, render each item as an unchecked task (``- [ ] ...``).

    Returns:
        The rendered list, or an empty string when ``items`` is empty.
    """
    marker = "- [ ] " if task else "- "
    return "\n".join(f"{marker}{item}" for item in items)


def _wikilinks(targets: list[str]) -> list[str]:
    """Wrap each target in Obsidian wikilink brackets.

    Args:
        targets: Note names (without ``.md`` or brackets).

    Returns:
        One ``[[name]]`` string per target, in the same order.
    """
    return [f"[[{target}]]" for target in targets]


def _build_project_note(
    *,
    title: str,
    capture: str,
    summary: str | None,
    desired_outcome: str | None,
    open_questions: list[str],
    next_actions: list[str],
    domains: list[str],
    resources: list[str],
    created: dt.date,
) -> str:
    """Assemble the markdown body for a new ``Project.md``.

    Empty sections are kept as templated placeholders so the user can fill them
    in inside Obsidian.

    Args:
        title: Project title (rendered as the H1 and stored in the audit log).
        capture: Original user wording, preserved verbatim.
        summary: Optional summary paragraph.
        desired_outcome: Optional description of the success state.
        open_questions: Outstanding questions, one per bullet.
        next_actions: Next concrete actions, rendered as unchecked task items.
        domains: Related Domain notes (used in frontmatter + Related section).
        resources: Related Resource notes (used in frontmatter + Related section).
        created: Creation date for the frontmatter.

    Returns:
        The full markdown source for ``Project.md``.
    """
    related = _bullets(_wikilinks(domains) + _wikilinks(resources))

    sections = [
        f"# {title}",
        f"## Capture\n\n{capture}",
        f"## Summary\n\n{summary or ''}".rstrip(),
        f"## Desired Outcome\n\n{desired_outcome or ''}".rstrip(),
        f"## Open Questions\n\n{_bullets(open_questions)}".rstrip(),
        f"## Next Actions\n\n{_bullets(next_actions, task=True)}".rstrip(),
        f"## Related\n\n{related}".rstrip(),
    ]
    frontmatter = _project_frontmatter(
        created=created,
        domains=domains,
        resources=resources,
    )
    return f"{frontmatter}\n" + "\n\n".join(sections) + "\n"


_RECORD_PROJECT_DESCRIPTION = """\
Record a new project in the user's Obsidian vault.

Use this when the user is committing to start a project — phrases like "let's
start a project to ...", "I want to build ...", "kick off a project for ...".
For fleeting ideas with no commitment, use `record_idea` instead.

Creates a folder `Projects/Active/<slug>/` containing:
- `Project.md` — title, captured wording, summary, desired outcome, open
  questions, next actions, and links to related Domains/Resources.
- `Board.md` — a basic kanban board (Inbox / Backlog / Next / Doing / Blocked /
  Done).

The raw capture is also appended to `Inbox/Projects.md` as an audit log entry.

Preserve the user's original wording verbatim in `capture` — do not paraphrase.
Generate a concise `title`. Fill in `summary`, `desired_outcome`,
`open_questions`, `next_actions`, `domains`, and `resources` only when the
user's words give you clear signal; otherwise leave them empty for the user to
flesh out later in Obsidian.
"""


@mcp.tool(description=_RECORD_PROJECT_DESCRIPTION)
async def record_project(
    *,
    title: Annotated[
        str,
        Field(
            description=(
                "A short, human-readable project title (e.g. 'Voice-controlled lights'). "
                "Used for the note's H1 and to derive the folder slug."
            ),
            min_length=1,
        ),
    ],
    capture: Annotated[
        str,
        Field(
            description=(
                "The user's original wording for the project, preserved verbatim. "
                "Do not paraphrase or summarise — that goes in `summary`."
            ),
            min_length=1,
        ),
    ],
    summary: Annotated[
        str | None,
        Field(
            description=(
                "A short interpretive summary of the project. Leave empty if the "
                "user's wording is already self-explanatory."
            ),
        ),
    ] = None,
    desired_outcome: Annotated[
        str | None,
        Field(
            description=(
                "What 'done' looks like for this project, if the user has hinted at it."
            ),
        ),
    ] = None,
    open_questions: Annotated[
        list[str] | None,
        Field(
            description=(
                "Outstanding questions raised by the capture (one per item). "
                "Leave empty when none are obvious."
            ),
        ),
    ] = None,
    next_actions: Annotated[
        list[str] | None,
        Field(
            description=(
                "Concrete next actions the user mentioned (rendered as unchecked "
                "task items). Leave empty when none are explicit."
            ),
        ),
    ] = None,
    domains: Annotated[
        list[str] | None,
        Field(
            description=(
                "Names of related Domain notes (no `.md`, no brackets). Used for "
                "frontmatter and rendered as wikilinks under `## Related`."
            ),
        ),
    ] = None,
    resources: Annotated[
        list[str] | None,
        Field(
            description=(
                "Names of related Resource notes (no `.md`, no brackets). Used for "
                "frontmatter and rendered as wikilinks under `## Related`."
            ),
        ),
    ] = None,
) -> str:
    """Record a new project, creating its folder structure and an audit entry.

    Args:
        title: Short project title.
        capture: Original user wording, preserved verbatim.
        summary: Optional interpretive summary.
        desired_outcome: Optional description of the success state.
        open_questions: Optional list of outstanding questions.
        next_actions: Optional list of concrete next actions.
        domains: Optional list of related Domain note names.
        resources: Optional list of related Resource note names.

    Returns:
        A short confirmation including the created project's vault path.
    """
    open_questions = open_questions or []
    next_actions = next_actions or []
    domains = domains or []
    resources = resources or []

    now = dt.datetime.now(dt.UTC)
    created_date = now.date()

    service = ObsidianService()

    project_content = _build_project_note(
        title=title,
        capture=capture,
        summary=summary,
        desired_outcome=desired_outcome,
        open_questions=open_questions,
        next_actions=next_actions,
        domains=domains,
        resources=resources,
        created=created_date,
    )
    slug, folder_vault_path = await service.create_project(
        slug_base=_slugify(title),
        project_content=project_content,
        board_content=_BOARD_NOTE_CONTENT,
    )

    project_note_vault_path = folder_vault_path / "Project"
    audit_entry = f"[[{project_note_vault_path.as_posix()}|{title}]]\n\n{capture}"
    heading_path = (now.strftime("%Y-%m-%d"), now.strftime("%H:%M"))
    async with service.project_inbox() as project_inbox:
        section = project_inbox.get_section(heading_path, create_if_not_exists=True)
        section.append_content(audit_entry)

    return (
        f"Project '{title}' recorded at {folder_vault_path.as_posix()}/ (slug: {slug})."
    )


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
