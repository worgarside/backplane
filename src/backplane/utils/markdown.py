"""Utilities for turning markdown files into structured documents."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Annotated, Self

from markdown_it import MarkdownIt
from pydantic import BaseModel, Field, PrivateAttr, computed_field

from backplane.utils.settings import SETTINGS

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    import anyio
    from markdown_it.token import Token


type FrontmatterValue = list[str] | str | None


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


def _parse_scalar(value: str) -> str:
    """Parse a simple frontmatter scalar.

    Returns:
        The scalar value without surrounding quotes.
    """
    return value.strip().strip("\"'")


def _parse_frontmatter(text: str) -> tuple[dict[str, FrontmatterValue], str]:
    """Split Obsidian-style frontmatter from the markdown body.

    Returns:
        Parsed frontmatter and the remaining markdown body.
    """
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}, text

    try:
        closing_line = lines[1:].index("---") + 1
    except ValueError:
        return {}, text

    frontmatter: dict[str, FrontmatterValue] = {}
    frontmatter_lines = lines[1:closing_line]
    idx = 0
    while idx < len(frontmatter_lines):
        line = frontmatter_lines[idx]
        idx += 1
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue

        key, value = line.split(":", maxsplit=1)
        key = key.strip()
        value = value.strip()
        if value:
            frontmatter[key] = _parse_scalar(value)
            continue

        items: list[str] = []
        while idx < len(frontmatter_lines):
            item_line = frontmatter_lines[idx]
            if item_line and not item_line.startswith(" "):
                break
            stripped_item = item_line.strip()
            idx += 1
            if stripped_item.startswith("- "):
                items.append(_parse_scalar(stripped_item[2:]))
        frontmatter[key] = items or None

    return frontmatter, "\n".join(lines[closing_line + 1 :])


def _visible_inline_text(tokens: Sequence[Token] | None) -> str:
    """Return visible text from parsed inline markdown tokens."""
    if not tokens:
        return ""

    parts: list[str] = []
    for token in tokens:
        if token.type in {"text", "code_inline"}:
            parts.append(token.content)
        elif token.children:
            parts.append(_visible_inline_text(token.children))
    return "".join(parts)


def _extract_headings(tokens: Sequence[Token]) -> list[_Heading]:
    """Extract markdown headings from a token stream.

    Returns:
        Headings in document order with visible text and zero-based source lines.
    """
    headings: list[_Heading] = []
    for idx, token in enumerate(tokens):
        if token.type != "heading_open" or not token.tag.startswith("h"):
            continue
        if not token.map:
            continue

        text = ""
        if idx + 1 < len(tokens) and tokens[idx + 1].type == "inline":
            text = _visible_inline_text(tokens[idx + 1].children).strip()

        headings.append(
            _Heading(
                level=int(token.tag.removeprefix("h")),
                line_no=token.map[0],
                text=text,
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
    sections: list[Self] = Field(default_factory=list)
    level: Annotated[
        int,
        Field(ge=1, le=6, description="The heading level of the section."),
    ]

    def iter_sections(self) -> Generator[Self]:
        """Yield this section followed by its nested sections in document order.

        Yields:
            The section and its nested sections.
        """
        yield self
        for section in self.sections:
            yield from section.iter_sections()


class MarkdownDocument(BaseModel):
    """A markdown document split into frontmatter and heading sections."""

    _frontmatter: dict[str, FrontmatterValue]
    _body: list[MarkdownSection]

    vault_path: Annotated[
        pathlib.PurePath,
        Field(description="The path within the vault to the markdown file."),
    ]

    validate_file_content_unchanged: Annotated[
        bool,
        Field(
            description=(
                "Whether to validate that the file content has not changed since the document was "
                "loaded before writing modifications to the file."
            ),
        ),
    ] = True

    _text: Annotated[str, PrivateAttr()]

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
        """
        self._text = await self._async_file_path.read_text(encoding="utf-8")

        self._frontmatter, body_text = _parse_frontmatter(self._text)
        lines = body_text.splitlines()

        if not (headings := _extract_headings(_markdown_it().parse(body_text))):
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
        if exc_type is not None:
            return

        if (
            self.validate_file_content_unchanged
            and await self._async_file_path.read_text(encoding="utf-8") != self._text
        ):
            msg = "File content has changed since the document was loaded."
            raise ValueError(msg)

        _ = await self._async_file_path.write_text(self._text, encoding="utf-8")

    def iter_sections(self) -> Generator[MarkdownSection]:
        """Yield every section in the document in document order.

        Yields:
            Each top-level section followed by its nested sections.
        """
        for section in self.body:
            yield from section.iter_sections()
