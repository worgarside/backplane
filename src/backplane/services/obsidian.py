"""Helpers for reading and editing Obsidian markdown notes."""

from __future__ import annotations

import datetime as dt
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import cache
from typing import TYPE_CHECKING, Final, final

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

from backplane.utils.settings import SETTINGS

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Sequence

    import anyio
    from markdown_it.token import Token


_MAX_MARKDOWN_HEADING_LEVEL: Final = 6
_MIN_HEADING_DEPTH_WITH_PARENT: Final = 2


@cache
def _markdown_it() -> MarkdownIt:
    """Return the configured markdown parser.

    Returns:
        A cached ``MarkdownIt`` instance with the extensions this module expects.
    """
    return MarkdownIt("commonmark").enable(["table", "strikethrough"])


def _validate_heading_level(level: int) -> None:
    """Validate that ``level`` is a markdown heading depth.

    Args:
        level: Heading depth where ``1`` is ``#`` and ``6`` is ``######``.

    Raises:
        ValueError: If ``level`` is outside markdown's supported heading range.
    """
    if level < 1:
        msg = "heading level must be at least 1."
        raise ValueError(msg)
    if level > _MAX_MARKDOWN_HEADING_LEVEL:
        msg = f"heading level must be at most {_MAX_MARKDOWN_HEADING_LEVEL}."
        raise ValueError(msg)


def _visible_inline_text(tokens: Sequence[Token] | None) -> str:
    """Return the visible text for parsed inline markdown tokens.

    Args:
        tokens: Inline markdown-it tokens, usually from a heading's following
            ``inline`` token.

    Returns:
        Text a reader would see after markdown formatting is removed. For example,
        ``Summary **done**`` becomes ``Summary done``.
    """
    if not tokens:
        return ""

    parts: list[str] = []
    for token in tokens:
        if token.type in {"text", "code_inline"}:
            parts.append(token.content)
        elif token.children:
            parts.append(_visible_inline_text(token.children))
    return "".join(parts)


def _heading_level(tag: str) -> int:
    """Convert a markdown-it heading tag into a numeric level.

    Args:
        tag: Heading tag such as ``h1`` or ``h3``.

    Returns:
        The numeric heading level.
    """
    return int(tag.removeprefix("h"))


def _extract_headings(tokens: Sequence[Token]) -> list[Heading]:
    """Extract markdown headings from a token stream.

    Args:
        tokens: Parsed markdown-it token stream for a full document.

    Returns:
        Headings in document order, with visible heading text and zero-based line numbers.
    """
    headings: list[Heading] = []
    for idx, token in enumerate(tokens):
        if token.type != "heading_open" or not token.tag.startswith("h"):
            continue
        if not token.map:
            continue

        title = ""
        if idx + 1 < len(tokens) and tokens[idx + 1].type == "inline":
            title = _visible_inline_text(tokens[idx + 1].children).strip()

        headings.append(
            Heading(
                level=_heading_level(token.tag),
                line_no=token.map[0],
                text=title,
            ),
        )
    return headings


def _section_block(level: int, heading_text: str, content: str) -> str:
    """Build a normalized markdown block for a new section.

    Args:
        level: Heading depth for the new section.
        heading_text: Visible heading text.
        content: Markdown body for the section.

    Returns:
        Markdown containing the heading and body, ready to insert into a document.
    """
    heading = f"{'#' * level} {heading_text.strip()}\n"

    if not (body := content.strip("\n")):
        return heading
    return f"{heading}\n{body}\n"


def _insert_markdown_at_line(text: str, line_index: int, markdown: str) -> str:
    """Insert markdown before ``line_index`` while keeping blank-line boundaries sane.

    Args:
        text: Existing document text.
        line_index: Zero-based line index before which ``markdown`` should be inserted.
        markdown: Markdown block to insert.

    Returns:
        Updated document text.
    """
    lines = text.splitlines(keepends=True)
    insert_at = max(0, min(line_index, len(lines)))
    before = "".join(lines[:insert_at])
    after = "".join(lines[insert_at:])

    prefix = ""
    if before and not before.endswith("\n\n"):
        prefix = "\n" if before.endswith("\n") else "\n\n"

    suffix = ""
    if after and not markdown.endswith("\n\n") and not after.startswith("\n"):
        suffix = "\n"

    return f"{before}{prefix}{markdown}{suffix}{after}"


@dataclass(frozen=True, slots=True)
class Heading:
    """A markdown heading with its parsed title and zero-based source line."""

    level: int
    line_no: int
    text: str


@dataclass(slots=True)
class Section:
    """A markdown section spanning from one heading to its outline boundary."""

    heading: Heading
    start_line: int
    end_line: int
    content: str
    position: int
    _document: MarkdownDocument = field(repr=False, compare=False)

    def subsections(self, level: int | None = None) -> list[Section]:
        """Return sections at ``level`` contained within this section.

        Args:
            level: Heading depth to split on. If omitted, the next heading depth below
                this section is used.

        Returns:
            Child sections in document order.

        Raises:
            ValueError: If ``level`` is not deeper than this section's heading level,
                or is outside markdown's supported heading range.
        """
        split_level = self.heading.level + 1 if level is None else level
        if split_level <= self.heading.level:
            msg = (
                f"subsection level ({split_level}) must be greater than "
                f"section heading level ({self.heading.level})."
            )
            raise ValueError(msg)
        _validate_heading_level(split_level)
        return self._document.sections(
            split_level,
            start_line=self.start_line + 1,
            end_line=self.end_line,
        )

    def print_tree(self) -> None:
        """Print this section's markdown-it syntax tree for debugging.

        This is intentionally side-effectful: it prints a compact tree to stdout,
        matching the local sandbox visualizer used while building the parser.
        """

        def print_node(node: SyntaxTreeNode, indent: int = 0) -> None:
            branch = "├── " if indent else ""
            label = f'"{node.content}"' if node.type == "text" else node.type
            print("│   " * max(indent - 1, 0) + branch + label)  # noqa: T201
            for child in node.children:
                print_node(child, indent + 1)

        print_node(SyntaxTreeNode(_markdown_it().parse(self.content)))


@final
class MarkdownDocument:
    """Editable markdown document backed by a file."""

    def __init__(self, file_path: anyio.Path) -> None:
        """Create an unloaded markdown document.

        Args:
            file_path: Path to the markdown file. The file is read when entering the
                async context manager.
        """
        self.file_path = file_path
        self.text = ""
        self._tokens: list[Token] = []
        self._headings: list[Heading] = []
        self._loaded = False

    async def __aenter__(self) -> MarkdownDocument:
        """Load the document and return it for editing.

        Returns:
            The loaded document instance.
        """
        self._set_text(await self.read())
        self._loaded = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: object,
    ) -> None:
        """Flush successful edits and clear loaded state.

        Args:
            exc_type: Exception type from the context manager, if any.
            _exc_value: Exception value from the context manager, if any.
            _traceback: Exception traceback from the context manager, if any.
        """
        if exc_type is None:
            await self.flush()
        self._loaded = False
        self.text = ""
        self._tokens = []
        self._headings = []

    async def read(self) -> str:
        """Read the file content.

        Returns:
            Markdown text from ``self.file_path``.
        """
        return await self.file_path.read_text(encoding="utf-8")

    async def flush(self) -> None:
        """Write the current document text to disk.

        The document must be loaded; call this from inside the async context manager.
        """
        self._ensure_loaded()
        _ = await self.file_path.write_text(self.text, encoding="utf-8")

    async def reset(self) -> None:
        """Discard in-memory edits and reload the file from disk.

        Use this inside the async context manager when you want to inspect or mutate the
        document temporarily, but do not want those in-memory changes flushed on context
        exit.
        """
        self._ensure_loaded()
        self._set_text(await self.read())

    def _ensure_loaded(self) -> None:
        """Require the document to be inside its async context manager.

        Raises:
            RuntimeError: If the document is not currently loaded.
        """
        if not self._loaded:
            msg = "Document is not loaded; use `async with MarkdownDocument(...)`."
            raise RuntimeError(msg)

    def _set_text(self, text: str) -> None:
        """Replace document text and refresh derived parser state.

        Args:
            text: New full markdown document text.
        """
        self.text = text
        self._tokens = _markdown_it().parse(text)
        self._headings = _extract_headings(self._tokens)

    def _lines(self) -> list[str]:
        """Return document text as source lines, preserving line endings.

        Returns:
            Lines produced by ``splitlines(keepends=True)``.
        """
        return self.text.splitlines(keepends=True)

    def _last_line_index(self) -> int:
        """Return the last zero-based source line index.

        Returns:
            Last line index, or ``-1`` for an empty document.
        """
        return len(self._lines()) - 1

    def headings(self, level: int | None = None) -> list[Heading]:
        """Return headings, optionally filtered to one depth.

        Args:
            level: Optional heading depth to filter by.

        Returns:
            Matching headings in document order.
        """
        self._ensure_loaded()
        if level is not None:
            _validate_heading_level(level)
        return [h for h in self._headings if level is None or h.level == level]

    def get_heading(self, heading_text: str, level: int | None = None) -> Heading | None:
        """Return the first heading matching ``heading_text`` and optional ``level``.

        Args:
            heading_text: Visible heading title to search for.
            level: Optional heading depth to filter by.

        Returns:
            The first matching heading, or ``None`` if no heading matches.
        """
        text = heading_text.strip()
        return next(
            (heading for heading in self.headings(level) if heading.text == text),
            None,
        )

    def sections(
        self,
        level: int,
        *,
        start_line: int = 0,
        end_line: int | None = None,
    ) -> list[Section]:
        """Return all sections whose heading is at ``level``.

        Args:
            level: Heading depth to split on.
            start_line: Inclusive lower line bound used by subsections.
            end_line: Inclusive upper line bound. Defaults to the end of the document.

        Returns:
            Matching sections in document order.
        """
        self._ensure_loaded()
        scope_end = self._last_line_index() if end_line is None else end_line
        _validate_heading_level(level)
        if scope_end < start_line:
            return []

        headings = [
            heading
            for heading in self._headings
            if heading.level == level and start_line <= heading.line_no <= scope_end
        ]

        return [
            self._section_for_heading(heading, position, scope_end)
            for position, heading in enumerate(headings)
        ]

    def _section_for_heading(
        self,
        heading: Heading,
        position: int = 0,
        end_line: int | None = None,
    ) -> Section:
        """Build the section span for a parsed heading.

        Args:
            heading: Heading that starts the section.
            position: Position among sibling sections at the requested level.
            end_line: Optional inclusive upper bound for the section's parent scope.

        Returns:
            A section whose content spans from ``heading`` until the next same-or-higher
            heading, or the supplied scope end.
        """
        scope_end = self._last_line_index() if end_line is None else end_line
        next_boundary = next(
            (
                other.line_no
                for other in self._headings
                if other.line_no > heading.line_no
                and other.line_no <= scope_end
                and other.level <= heading.level
            ),
            scope_end + 1,
        )
        section_end = max(heading.line_no, next_boundary - 1)
        lines = self._lines()
        return Section(
            heading=heading,
            start_line=heading.line_no,
            end_line=section_end,
            content="".join(lines[heading.line_no : section_end + 1]),
            position=position,
            _document=self,
        )

    def _resolve_parent_section(
        self,
        level: int,
        nest_under_heading: str | Heading | None,
    ) -> Section | None:
        """Resolve the parent section for a new heading.

        Args:
            level: Heading depth of the section being inserted.
            nest_under_heading: Explicit parent heading title/object, or ``None`` to infer
                the parent when there is exactly one candidate at ``level - 1``.

        Returns:
            Parent section, or ``None`` when inserting a top-level ``#`` section.

        Raises:
            ValueError: If the parent is ambiguous, missing, or at the wrong depth.
        """
        if level < _MIN_HEADING_DEPTH_WITH_PARENT:
            if nest_under_heading is not None:
                msg = "nest_under_heading is only valid when level is at least 2."
                raise ValueError(msg)
            return None

        parent_level = level - 1
        if nest_under_heading is None:
            parents = self.sections(parent_level)
            if len(parents) != 1:
                msg = (
                    "nest_under_heading must be given unless there is exactly one "
                    f"section at level {parent_level} (found {len(parents)})."
                )
                raise ValueError(msg)
            return parents[0]

        if isinstance(nest_under_heading, str):
            heading = self.get_heading(nest_under_heading, parent_level)
            if heading is None:
                msg = f"No heading {nest_under_heading!r} at level {parent_level}."
                raise ValueError(msg)
        else:
            heading = nest_under_heading
            if heading.level != parent_level:
                msg = (
                    f"nest_under_heading level ({heading.level}) must be "
                    f"level - 1 ({parent_level})."
                )
                raise ValueError(msg)

        return self._section_for_heading(heading)

    @staticmethod
    def _insert_line_for_position(
        sections: list[Section],
        position: int | None,
        append_line: int,
    ) -> int:
        """Choose the line before which a section should be inserted.

        Args:
            sections: Sibling sections in the insertion scope.
            position: Insertion index. ``None`` appends after all siblings.
            append_line: Line index to use for append-style insertion.

        Returns:
            The line index before which new markdown should be inserted.

        Raises:
            ValueError: If ``position`` is outside the sibling list bounds.
        """
        if position is None or position == len(sections):
            return append_line
        if position < 0 or position > len(sections):
            msg = f"position ({position}) out of range for {len(sections)} section(s)."
            raise ValueError(msg)
        return sections[position].start_line

    def add_section(
        self,
        heading_text: str,
        content: str,
        level: int,
        *,
        nest_under_heading: str | Heading | None = None,
        position: int | None = None,
    ) -> Section:
        """Insert a new section and return the resulting section.

        Args:
            heading_text: Visible title for the new section heading.
            content: Markdown body to place under the new heading.
            level: Heading depth for the new section.
            nest_under_heading: Optional parent heading. For ``level >= 2``, this may be
                omitted only when there is exactly one section at ``level - 1``.
            position: Optional insertion index among sibling sections. ``None`` appends
                to the end of the inferred or explicit scope.

        Returns:
            The inserted section after reparsing the document.

        Raises:
            RuntimeError: If the document is not currently loaded, or the inserted heading
                cannot be found after reparsing.
        """
        self._ensure_loaded()
        _validate_heading_level(level)

        parent = self._resolve_parent_section(level, nest_under_heading)
        if parent is None:
            scoped_sections = self.sections(level)
            append_line = len(self._lines())
        else:
            scoped_sections = parent.subsections(level)
            append_line = parent.end_line + 1

        insert_line = self._insert_line_for_position(
            scoped_sections,
            position,
            append_line,
        )
        block = _section_block(level, heading_text, content)
        self._set_text(_insert_markdown_at_line(self.text, insert_line, block))

        inserted = self.get_heading(heading_text, level)
        if inserted is None:
            msg = f"Inserted heading {heading_text!r} could not be found after reparsing."
            raise RuntimeError(msg)
        return self._section_for_heading(inserted)

    def append_to_section(
        self,
        heading_text: str,
        content: str,
        *,
        level: int = 2,
    ) -> Section:
        """Append content to the section headed by ``heading_text``.

        Args:
            heading_text: Visible title of the section to append to.
            content: Markdown content to append.
            level: Heading depth of the target section.

        Returns:
            The updated section after reparsing the document.

        Raises:
            ValueError: If no matching heading exists.
        """
        self._ensure_loaded()
        _validate_heading_level(level)

        heading = self.get_heading(heading_text, level)
        if heading is None:
            msg = f"No heading {heading_text.strip()!r} at level {level}."
            raise ValueError(msg)

        section = self._section_for_heading(heading)
        chunk = content.strip("\n")
        if not chunk:
            return section

        self._set_text(
            _insert_markdown_at_line(self.text, section.end_line + 1, f"{chunk}\n"),
        )
        return self._section_for_heading(heading)


@final
class ObsidianService:
    """Service for interacting with the Obsidian vault."""

    DAILY_NOTE_DIRECTORY: Final = "Daily Notes"

    async def append_to_daily_note(self, section_heading: str, content: str) -> None:
        """Append content to a section in today's daily note, creating it if needed.

        Args:
            section_heading: Visible title of the ``##`` section to append to.
            content: Markdown content to append.
        """
        async with self.daily_note() as daily_note:
            if daily_note.get_heading(section_heading, level=2) is None:
                _ = daily_note.add_section(section_heading, content, level=2)
            else:
                _ = daily_note.append_to_section(section_heading, content, level=2)

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
        date = date or dt.datetime.now(tz=dt.UTC).date()
        daily_note_path = (
            SETTINGS.obsidian_vault_path
            / self.DAILY_NOTE_DIRECTORY
            / f"{date.isoformat()}.md"
        )

        async with MarkdownDocument(daily_note_path) as daily_note:
            yield daily_note
