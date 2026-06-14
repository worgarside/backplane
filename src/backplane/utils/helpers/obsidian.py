"""Obsidian vault naming, linking, and wikilink helpers."""

from __future__ import annotations

import re
from typing import Final, Literal

from pydantic import BaseModel

from backplane.utils.enums import VaultEntityKind

from .slug import safe_slug

VaultNoteKind = VaultEntityKind | Literal["task"]

_FILENAME_INVALID_RE: Final = re.compile(r'[\\/:*?"<>|]')


class VaultNoteMetadata(BaseModel, frozen=True):
    """Structured metadata for a vault note returned by Backplane tools."""

    kind: VaultNoteKind
    display_name: str
    title: str
    path: str
    filename: str
    slug: str
    canonical_link: str
    canonical_link_with_alias: str


def note_filename(title: str) -> str:
    """Return a filesystem-safe human-readable filename stem from a display title."""
    normalized = re.sub(r"\s*/\s*", " - ", title)
    sanitized = _FILENAME_INVALID_RE.sub("", normalized).strip()
    sanitized = re.sub(r"\s+", " ", sanitized)
    return sanitized or "Untitled"


def obsidian_link_target_from_path(path: str) -> str:
    """Return the filename stem used as a display title for a vault-relative path."""
    stem = path.rsplit("/", maxsplit=1)[-1]
    if stem.endswith(".md"):
        return stem.removesuffix(".md")
    return stem


def _path_link_target(path: str) -> str:
    """Return a vault-relative wikilink target without the ``.md`` extension."""
    return path.removesuffix(".md") if path.endswith(".md") else path


def build_obsidian_link(
    path_or_target: str,
    *,
    alias: str | None = None,
    fragment: str | None = None,
) -> str:
    """Build an Obsidian wikilink from a vault path, target, optional alias, and fragment.

    When ``path_or_target`` is a vault-relative path (contains ``/`` or ends with
    ``.md``), the link target uses the full path and defaults the alias to the note
    title stem so folder prefixes are not shown in the rendered view.
    """
    is_path = "/" in path_or_target or path_or_target.endswith(".md")
    if is_path:
        target = _path_link_target(path_or_target)
        if alias is None and "/" in target:
            alias = obsidian_link_target_from_path(target)
    else:
        target = path_or_target

    if fragment:
        fragment_text = fragment if fragment.startswith("#") else f"#{fragment}"
        target = f"{target}{fragment_text}"

    if alias is not None and ("/" in target.split("#", maxsplit=1)[0] or alias != target.split("#", maxsplit=1)[0]):
        return f"[[{target}|{alias}]]"

    return f"[[{target}]]"


def build_vault_note_metadata(
    *,
    kind: VaultNoteKind,
    title: str,
    path: str,
) -> VaultNoteMetadata:
    """Build structured note metadata for tool responses."""
    filename = path.rsplit("/", maxsplit=1)[-1]
    canonical_link = build_obsidian_link(path)
    return VaultNoteMetadata(
        kind=kind,
        display_name=title,
        title=title,
        path=path,
        filename=filename,
        slug=safe_slug(title),
        canonical_link=canonical_link,
        canonical_link_with_alias=canonical_link,
    )
