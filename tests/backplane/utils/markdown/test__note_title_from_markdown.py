"""Tests for note title extraction from markdown."""

from __future__ import annotations

from backplane.utils.markdown import note_title_from_markdown


def test__note_title_from_markdown_skips_frontmatter() -> None:
    """The first H1 after frontmatter is returned."""
    text = """---
type: domain
---

# Home Assistant

## Notes
"""
    assert note_title_from_markdown(text) == "Home Assistant"


def test__note_title_from_markdown_returns_none_without_h1() -> None:
    """Markdown without a level-1 heading has no note title."""
    assert note_title_from_markdown("---\ntype: domain\n---\n\n## Notes\n") is None
