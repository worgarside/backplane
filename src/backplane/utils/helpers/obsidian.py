"""Obsidian vault naming, linking, and wikilink helpers."""

from __future__ import annotations

import re
from typing import Annotated, Final, Literal

from pydantic import BaseModel, Field, computed_field

from backplane.utils.async_path import AsyncPath
from backplane.utils.enums import VaultEntityKind

from .slug import safe_slug

VaultNoteKind = VaultEntityKind | Literal["task"]

_FILENAME_INVALID_RE: Final = re.compile(r'[\\/:*?"<>|]')


class VaultNoteMetadata(BaseModel, frozen=True):
    """Structured metadata for a vault note returned by Backplane tools."""

    kind: Annotated[
        VaultNoteKind,
        Field(
            description=(
                "Note kind: a vault entity (`domain`, `person`, `project`, `resource`) "
                "or `task`."
            ),
        ),
    ]
    display_name: Annotated[
        str,
        Field(description="Human-readable name shown to users and MCP tool responses."),
    ]
    title: Annotated[
        str,
        Field(description="Note H1 title, typically matching ``display_name``."),
    ]
    path: Annotated[
        AsyncPath,
        Field(description="Vault-relative path to the note file."),
    ]
    slug: Annotated[
        str,
        Field(description="URL-safe slug derived from the title."),
    ]
    canonical_link: Annotated[
        str,
        Field(
            description=(
                "Primary Obsidian wikilink for referencing the note, e.g. "
                "``[[Domains/Home - Property|Home - Property]]``."
            ),
        ),
    ]

    @computed_field
    @property
    def filename(self) -> str:
        """Note filename including the ``.md`` extension."""
        return self.path.name


def note_filename(title: str) -> str:
    """Convert a display title into a filesystem-safe, human-readable filename stem.

    Removes characters that are invalid on filesystems and normalizes whitespace.
    If the result is empty, returns "Untitled".

    Returns:
        str: The sanitized filename stem.
    """
    normalized = re.sub(r"\s*/\s*", " - ", title)
    sanitized = _FILENAME_INVALID_RE.sub("", normalized).strip()
    sanitized = re.sub(r"\s+", " ", sanitized)
    return sanitized or "Untitled"


def obsidian_link_target_from_path(path: str) -> str:
    """Derive the wikilink target display stem from a vault-relative path.

    Returns:
        The filename from the last path component, with `.md` extension removed if present.
    """
    stem = path.rsplit("/", maxsplit=1)[-1]

    return stem.removesuffix(".md")


def build_obsidian_link(
    path_or_target: AsyncPath,
    *,
    alias: str | None = None,
    fragment: str | None = None,
) -> str:
    """Build an Obsidian wikilink from a vault path, target, optional alias, and fragment.

    When ``path_or_target`` is a vault-relative path (multiple path components or ends
    with ``.md``), the link target uses the full path and defaults the alias to the
    title stem so folder prefixes are not shown in the rendered view.

    Args:
        path_or_target: Vault-relative note path or bare wikilink target name.
        alias: Optional display text for ``[[target|alias]]`` rendering.
        fragment: Optional heading or block anchor, with or without a leading ``#``.

    Returns:
        A rendered Obsidian wikilink string.

    Examples:
        >>> build_obsidian_link(AsyncPath("Domains/Home - Property.md"))
        '[[Domains/Home - Property|Home - Property]]'
        >>> build_obsidian_link(AsyncPath("Home Assistant"))
        '[[Home Assistant]]'
        >>> build_obsidian_link(
        ...     AsyncPath("Domains/Home - Property.md"),
        ...     alias="Home / Property",
        ... )
        '[[Domains/Home - Property|Home / Property]]'
        >>> build_obsidian_link(
        ...     AsyncPath("Projects/Rented Home Formal Complaint.md"),
        ...     fragment="Tasks",
        ... )
        '[[Projects/Rented Home Formal Complaint#Tasks|Rented Home Formal Complaint]]'
    """
    if len(path_or_target.parts) > 1 or path_or_target.suffix == ".md":
        target = path_or_target.as_posix().removesuffix(".md")
        if alias is None and "/" in target:
            alias = obsidian_link_target_from_path(target)
    else:
        target = path_or_target.as_posix()

    if fragment:
        fragment_text = fragment if fragment.startswith("#") else f"#{fragment}"
        target = f"{target}{fragment_text}"

    if alias is not None and (
        "/" in target.split("#", maxsplit=1)[0]
        or alias != target.split("#", maxsplit=1)[0]
    ):
        return f"[[{target}|{alias}]]"

    return f"[[{target}]]"


def build_entity_wikilink(kind: VaultEntityKind, name: str) -> str:
    """Build a wikilink to an entity note.

    Parameters:
        kind: Entity kind determining the vault subdirectory (domain, person, project, or resource).
        name: Human-readable display name used as the link alias.

    Returns:
        Obsidian wikilink string targeting the entity's note.
    """
    return build_obsidian_link(
        kind.vault_dir / f"{note_filename(name)}.md",
        alias=name,
    )


def build_vault_note_metadata(
    *,
    kind: VaultNoteKind,
    title: str,
    path: AsyncPath,
) -> VaultNoteMetadata:
    """Create vault note metadata for a given title and vault-relative path.

    Parameters:
        kind: The kind of vault note (entity kind or "task").
        title: The note's human-readable title.
        path: The vault-relative path to the note file.

    Returns:
        A VaultNoteMetadata object with the specified kind, title, path, slug, and canonical link.
    """
    canonical_link = build_obsidian_link(path)

    return VaultNoteMetadata(
        kind=kind,
        display_name=title,
        title=title,
        path=AsyncPath(path),
        slug=safe_slug(title),
        canonical_link=canonical_link,
    )
