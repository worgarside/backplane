"""Shared helper utilities for Backplane."""

from __future__ import annotations

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
from .slug import safe_slug

__all__ = [
    "atomic_write_text",
    "format_human_date",
    "format_obsidian_moment_date",
    "ordinal_day_of_month",
    "ordinal_suffix_for_day",
    "resolve_under_root",
    "safe_slug",
    "substitute_obsidian_core_date_variables",
    "substitute_vault_entity_template",
    "today",
]
