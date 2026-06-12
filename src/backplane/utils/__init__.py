"""Utility functions for Backplane."""

from __future__ import annotations

from . import exceptions as exc
from .helpers import (
    atomic_write_text,
    format_human_date,
    resolve_under_root,
    safe_slug,
    substitute_obsidian_core_date_variables,
    substitute_vault_entity_template,
    today,
)
from .kanban import append_board_card
from .markdown import MarkdownDocument
from .settings import SETTINGS, VAULT_PATHS
from .yaml import YAML_LOADER

__all__ = [
    "SETTINGS",
    "VAULT_PATHS",
    "YAML_LOADER",
    "MarkdownDocument",
    "append_board_card",
    "atomic_write_text",
    "exc",
    "format_human_date",
    "resolve_under_root",
    "safe_slug",
    "substitute_obsidian_core_date_variables",
    "substitute_vault_entity_template",
    "today",
]
