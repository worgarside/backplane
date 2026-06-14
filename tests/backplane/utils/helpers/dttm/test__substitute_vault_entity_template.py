"""Tests for vault entity template substitution."""

from __future__ import annotations

import datetime as dt

import pytest

from backplane.utils.helpers.dttm import (
    format_obsidian_datetime,
    substitute_vault_entity_template,
)

_SAMPLE_DATETIME = dt.datetime(2026, 6, 6, 14, 30, 45, tzinfo=dt.UTC)


def test__substitute_vault_entity_template_expands_title() -> None:
    """The title placeholder is replaced with the entity display name."""
    assert (
        substitute_vault_entity_template("# {{title}}\n", title="Home Assistant")
        == "# Home Assistant\n"
    )


def test__substitute_vault_entity_template_expands_core_datetime() -> None:
    """Obsidian core ``{ date:... }`` placeholders expand to formatted datetimes."""
    template = 'created:\n  "{ date:YYYY-MM-DDTHH:mm:ss }":'
    result = substitute_vault_entity_template(
        template,
        title="Example",
        now=_SAMPLE_DATETIME,
    )
    assert '"2026-06-06T14:30:45":' in result


@pytest.mark.parametrize(
    ("fmt", "expected"),
    [
        ("YYYY-MM-DD", "2026-06-06"),
        ("HH:mm:ss", "14:30:45"),
    ],
)
def test__format_obsidian_datetime(fmt: str, expected: str) -> None:
    """Datetime tokens are formatted using Obsidian core template syntax."""
    assert format_obsidian_datetime(_SAMPLE_DATETIME, fmt) == expected


def test__substitute_vault_entity_template_expands_domain_template_snippet() -> None:
    """A realistic domain template snippet expands title and datetime placeholders."""
    template = """---
type: domain
created:
  "{ date:YYYY-MM-DDTHH:mm:ss }":
---
# {{title}}

## Overview
"""
    result = substitute_vault_entity_template(
        template,
        title="Home Assistant",
        now=_SAMPLE_DATETIME,
    )
    assert "# Home Assistant" in result
    assert r'"2026-06-06T14:30:45":' in result
