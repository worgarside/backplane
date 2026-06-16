"""Shared helper utilities for Backplane."""

from __future__ import annotations

from backplane.utils.async_path import AsyncPath

from .dttm import (
    format_human_date,
    format_obsidian_moment_date,
    ordinal_day_of_month,
    ordinal_suffix_for_day,
    substitute_obsidian_core_date_variables,
    substitute_vault_entity_template,
    today,
)
from .files import atomic_write_text, resolve_under_root
from .obsidian import (
    VaultNoteMetadata,
    build_entity_wikilink,
    build_obsidian_link,
    build_vault_note_metadata,
    note_filename,
    obsidian_link_target_from_path,
)
from .slug import safe_slug

__all__ = [
    "AsyncPath",
    "VaultNoteMetadata",
    "atomic_write_text",
    "build_entity_wikilink",
    "build_obsidian_link",
    "build_vault_note_metadata",
    "format_human_date",
    "format_obsidian_moment_date",
    "note_filename",
    "obsidian_link_target_from_path",
    "ordinal_day_of_month",
    "ordinal_suffix_for_day",
    "resolve_under_root",
    "safe_slug",
    "substitute_obsidian_core_date_variables",
    "substitute_vault_entity_template",
    "today",
]
