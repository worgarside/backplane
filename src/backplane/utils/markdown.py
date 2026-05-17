"""Utilities for turning markdown files into structured documents."""

from __future__ import annotations

import datetime as dt
import difflib
import io
import pathlib
from dataclasses import dataclass
from functools import cache, lru_cache
from typing import TYPE_CHECKING, Annotated, Self

import mdformat
from loguru import logger
from markdown_it import MarkdownIt
from pydantic import BaseModel, Field, PrivateAttr, computed_field
from ruamel.yaml import YAML

from backplane.utils.settings import SETTINGS

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Sequence

    import anyio
    from markdown_it.token import Token


# YAML 1.2 produces these scalar Python types under ``YAML(typ="rt")``. Order matters
# for Pydantic union resolution: ``bool`` must precede ``int`` (since ``True`` is
# also an ``int``) and ``datetime`` must precede ``date`` (since ``datetime``
# subclasses ``date``). ruamel.yaml's tagged subclasses (``DoubleQuotedScalarString``,
# ``ScalarBoolean``, ``TimeStamp``, ...) all inherit from these natives, so the
# loaded values satisfy this union without coercion.
type FrontmatterScalar = bool | int | float | str | dt.datetime | dt.date | None

# Frontmatter values are arbitrary YAML scalars or nested containers
type FrontmatterValue = (
    FrontmatterScalar | list[FrontmatterValue] | dict[str, FrontmatterValue]
)

YAML_LOADER = YAML(typ="rt")
YAML_LOADER.explicit_start = True
YAML_LOADER.preserve_quotes = True
YAML_LOADER.indent(mapping=2, sequence=4, offset=2)  # pyright: ignore[reportAny]
YAML_LOADER.width = 4096


@cache
def _markdown_it() -> MarkdownIt:
    """Return the configured markdown parser."""
    return MarkdownIt("commonmark").enable(["table", "strikethrough"])


@dataclass(frozen=True, slots=True)
class _Heading:
    """A parsed heading with source position."""

    level: int
    line_no: int
    text: str


@lru_cache(maxsize=1024)
def _heading_plain_text(heading: str) -> str:
    """Return the plain-text form of a heading for format-insensitive lookups.

    Inline markdown markup (``**bold**``, ``_italic_``, ``` `code` ```,
    ``~~strike~~``, ``[link](url)``, ...) is stripped so that
    :meth:`MarkdownDocument.get_section` can match a section regardless of how its
    heading is decorated in the source. The cached result means repeated lookups
    over the same headings are O(1) after the first parse.

    Args:
        heading: The raw heading text as stored on a :class:`MarkdownSection`.

    Returns:
        The visible text of the heading with surrounding whitespace stripped.
    """
    parts: list[str] = []

    def _collect(tokens: Iterable[Token]) -> None:
        for token in tokens:
            if token.type in {"text", "code_inline"}:
                parts.append(token.content)
            elif token.children:
                _collect(token.children)

    _collect(_markdown_it().parseInline(heading))
    return "".join(parts).strip()


def _parse_frontmatter(text: str) -> tuple[dict[str, FrontmatterValue], str]:
    """Split Obsidian-style frontmatter from the markdown body.

    The YAML block is loaded through ``YAML_LOADER`` (round-trip mode) so types,
    quote styles, key order, and comments are preserved for the eventual dump.

    Returns:
        Parsed frontmatter as a ``CommentedMap`` and the remaining markdown body.
    """
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}, text

    try:
        closing_line = lines[1:].index("---") + 1
    except ValueError:
        return {}, text

    yaml_text = "\n".join(lines[1:closing_line])
    loaded: dict[str, FrontmatterValue] = (
        YAML_LOADER.load(yaml_text) or {}  # pyright: ignore[reportUnknownMemberType]
    )
    body_text = "\n".join(lines[closing_line + 1 :])
    return loaded, body_text


def _extract_headings(
    tokens: Sequence[Token],
    lines: Sequence[str],
) -> list[_Heading]:
    """Extract markdown headings from a token stream.

    The heading text is sliced directly from the source line rather than walking
    the parsed inline tokens, so inline formatting (``**bold**``, ``*italic*``,
    ``[links](url)``, etc.) is preserved verbatim.

    Returns:
        Headings in document order with raw text and zero-based source lines.
    """
    headings: list[_Heading] = []
    for token in tokens:
        if token.type != "heading_open" or not token.tag.startswith("h"):
            continue
        if not token.map:
            continue

        # Heading source lines are ``#... text``. Strip the leading marker run plus
        # the single separator space; any trailing whitespace is also dropped.
        raw = lines[token.map[0]].lstrip("#").lstrip(" \t").rstrip()
        headings.append(
            _Heading(
                level=int(token.tag.removeprefix("h")),
                line_no=token.map[0],
                text=raw,
            ),
        )
    return headings


def _section_content(lines: list[str], start_line: int, end_line: int) -> str | None:
    """Return trimmed markdown body content for a heading span."""
    content_lines = lines[start_line:end_line]
    while content_lines and not content_lines[0].strip():
        del content_lines[0]
    while content_lines and not content_lines[-1].strip():
        del content_lines[-1]

    if not content_lines:
        return None

    return "\n".join(content_lines)


class MarkdownSection(BaseModel):
    """A markdown section with nested child sections."""

    heading: str
    content: str | None = None
    sections: list[MarkdownSection] = Field(default_factory=list)
    level: Annotated[
        int,
        Field(ge=1, le=6, description="The heading level of the section."),
    ]

    def append_content(self, content: str) -> None:
        """Append content to this section.

        Args:
            content: The content to append.
        """
        self.content = (self.content or "") + "\n" + content

    def prepend_content(self, content: str) -> None:
        """Prepend content to this section.

        Args:
            content: The content to prepend.
        """
        self.content = content + "\n" + (self.content or "")

    def replace_content(self, content: str) -> None:
        """Replace this section's content.

        Args:
            content: The replacement content.
        """
        self.content = content

    def iter_sections(self) -> Generator[MarkdownSection]:
        """Yield this section followed by its nested sections in document order.

        Yields:
            The section and its nested sections.
        """
        yield self
        for section in self.sections:
            yield from section.iter_sections()

    def render(self) -> str:
        """Render the section to markdown.

        Returns:
            A markdown source string for this section and its nested sections.
            The output is valid markdown but not necessarily canonically formatted;
            :meth:`MarkdownDocument.render` runs the final document through
            ``mdformat`` to normalise spacing, table alignment, and so on.
        """
        parts: list[str] = [f"{'#' * self.level} {self.heading}"]
        if self.content is not None and self.content.strip():
            parts.append(self.content)
        parts.extend(section.render() for section in self.sections)
        return "\n\n".join(parts)


class MarkdownDocument(BaseModel):
    """A markdown document split into frontmatter and heading sections."""

    _frontmatter: dict[str, FrontmatterValue] = PrivateAttr(default_factory=dict)
    _body: list[MarkdownSection] = PrivateAttr(default_factory=list)
    _loaded_rendered: Annotated[str, PrivateAttr()] = ""

    vault_path: Annotated[
        pathlib.PurePath,
        Field(description="The path within the vault to the markdown file."),
    ]

    initial_content: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "When ``create_if_not_exists`` is true and the file is missing, this "
                "string is written as the new file contents instead of an empty file."
            ),
        ),
    ] = None

    create_if_not_exists: Annotated[
        bool,
        Field(description="Whether to create the file if it does not exist."),
    ] = False

    read_only: Annotated[
        bool,
        Field(description="When true, skip all validation and writes on exit."),
    ] = False

    validate_file_content_unchanged: Annotated[
        bool,
        Field(
            description=(
                "Whether to validate that the file content has not changed since the document was "
                "loaded before writing modifications to the file."
            ),
        ),
    ] = True

    @computed_field
    @property
    def frontmatter(self) -> dict[str, FrontmatterValue]:
        """Return the document frontmatter."""
        return self._frontmatter

    @computed_field
    @property
    def body(self) -> list[MarkdownSection]:
        """Return the document body."""
        return self._body

    @property
    def _async_file_path(self) -> anyio.Path:
        """Async-capable path wrapper for disk I/O."""
        return SETTINGS.obsidian_vault_path / self.vault_path

    async def __aenter__(self) -> Self:
        """Load the document and return it for editing.

        Returns:
            The loaded document instance.

        Raises:
            FileNotFoundError: If the file does not exist and creation is disabled.
        """
        try:
            text = await self._async_file_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            if not self.create_if_not_exists:
                raise

            text = self.initial_content if self.initial_content is not None else ""
            _ = await self._async_file_path.parent.mkdir(parents=True, exist_ok=True)
            _ = await self._async_file_path.write_text(text, encoding="utf-8")

        self._frontmatter, body_text = _parse_frontmatter(text)
        lines = body_text.splitlines()

        if not (headings := _extract_headings(_markdown_it().parse(body_text), lines)):
            self._body = []
            self._loaded_rendered = self.render()
            return self

        sections_by_heading: dict[_Heading, MarkdownSection] = {}
        roots: list[MarkdownSection] = []
        stack: list[tuple[_Heading, MarkdownSection]] = []
        for heading in headings:
            section = MarkdownSection(heading=heading.text, level=heading.level)
            sections_by_heading[heading] = section

            # The stack tracks the active heading path. Pop until the top is a
            # shallower heading, which is the parent of this section.
            while stack and stack[-1][0].level >= heading.level:
                _ = stack.pop()

            # If a parent remains, nest under it; otherwise this is a top-level
            # section in the document body.
            if stack:
                stack[-1][1].sections.append(section)
            else:
                roots.append(section)

            # This section may become the parent for later, deeper headings.
            stack.append((heading, section))

        for idx, heading in enumerate(headings):
            next_heading_line = (
                headings[idx + 1].line_no if idx + 1 < len(headings) else len(lines)
            )
            section = sections_by_heading[heading]
            section.content = _section_content(
                lines,
                start_line=heading.line_no + 1,
                end_line=next_heading_line,
            )
            if section.content is None and section.sections:
                section.content = ""

        self._body = roots

        self._loaded_rendered = self.render()
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

        Raises:
            ValueError: If the file content has changed since the document was loaded and validation is enabled.
        """
        if exc_type is not None or self.read_only:
            return

        rendered = self.render()

        if self.validate_file_content_unchanged and rendered != self._loaded_rendered:
            diff = "".join(
                difflib.unified_diff(
                    self._loaded_rendered.splitlines(keepends=True),
                    rendered.splitlines(keepends=True),
                    fromfile="loaded",
                    tofile="rendered",
                ),
            )
            logger.debug("Document mutation detected:\n{}", diff)
            msg = "File content has changed since the document was loaded."
            raise ValueError(msg)

        _ = await self._async_file_path.write_text(rendered, encoding="utf-8")

    def get_section(self, heading_path: tuple[str, ...]) -> MarkdownSection:
        """Return the section at the given heading path.

        Heading comparison is case-insensitive and format-insensitive: inline markdown markup on each
        side (``**bold**``, ``_italic_``, ``` `code` ``, links, ...) is stripped and case-folded
        before matching.

        Args:
            heading_path: List of heading text components to traverse.

        Returns:
            The section at the given path.

        Raises:
            ValueError: If the section is not found at the given path.
        """
        path_parts = list(heading_path)

        section: MarkdownSection | None = None
        prev_heading: str | None = None
        sections: Iterable[MarkdownSection] = self.body

        while path_parts:
            heading = path_parts.pop(0)
            target = _heading_plain_text(heading).casefold()
            section = next(
                (
                    s
                    for s in sections
                    if _heading_plain_text(s.heading).casefold() == target
                ),
                None,
            )
            if section is None:
                msg = f"Section with heading {heading!r} not found under {prev_heading!r}"
                raise ValueError(msg)

            sections = section.iter_sections()
            prev_heading = heading

        if section is None:
            msg = f"Section not found at path {heading_path!r}"
            raise ValueError(msg)

        return section

    def iter_sections(self) -> Generator[MarkdownSection]:
        """Yield every section in the document in document order.

        Yields:
            Each top-level section followed by its nested sections.
        """
        for section in self.body:
            yield from section.iter_sections()

    def render(self) -> str:
        """Render the document to markdown.

        The body is normalised by ``mdformat`` (canonical spacing, list markers,
        and table alignment). The frontmatter is rendered separately through
        ``YAML_LOADER`` to preserve quoting styles, key order, types, and comments
        that ``mdformat-frontmatter`` would otherwise flatten by re-parsing through
        PyYAML.

        Returns:
            The full markdown document including frontmatter (if any) and body.
        """
        body = mdformat.text(  # pyright: ignore[reportUnknownMemberType]
            "\n\n".join(section.render() for section in self.body),
            extensions={"gfm"},  # GitHub-flavored markdown extensions
        ).lstrip()

        if not self.frontmatter:
            return body

        # ruamel.yaml's ``YAML.dump`` writes to a stream and returns ``None``; per-call
        # ``sort_keys``/``allow_unicode`` kwargs don't exist (round-trip mode preserves
        # key order, and unicode is allowed by default on the instance). Dumping into
        # an ``io.StringIO`` is the documented way to capture the output as a string.
        buffer = io.StringIO()
        YAML_LOADER.dump(self.frontmatter, buffer)  # pyright: ignore[reportUnknownMemberType]

        # ``explicit_start = True`` emits the opening ``---``; the closing delimiter for
        # Obsidian-style frontmatter is also ``---`` (not the YAML ``...`` document-end
        # marker that ``explicit_end = True`` would produce), so it's added manually.
        return f"{buffer.getvalue()}---\n{body}"
