"""Filesystem-safe slug generation."""

from __future__ import annotations

import re
import unicodedata


def safe_slug(text: str, max_len: int = 60) -> str:
    """Convert arbitrary text into a lowercase, filesystem-safe slug.

    Processing steps:

    1. **Unicode normalization (NFKD)** — decompose accented characters into
       base letters plus combining marks (e.g. ``é`` → ``e`` + accent).
    2. **ASCII transliteration** — encode as ASCII, dropping characters that
       cannot be represented (combining marks and non-Latin scripts).
    3. **Sanitize** — remove punctuation and symbols, keeping word characters,
       spaces, and hyphens; lowercase and trim edges.
    4. **Hyphenate** — collapse runs of spaces and hyphens into a single ``-``,
       then strip leading and trailing hyphens.
    5. **Truncate** — cap length at ``max_len``; return ``"task"`` when the
       result would otherwise be empty.

    Args:
        text: Source string, typically a task title or domain name.
        max_len: Maximum slug length before truncation.

    Returns:
        A slug safe for use in vault filenames and wikilink paths.
    """
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode()
    cleaned = re.sub(r"[^\w\s-]", "", ascii_text).strip().lower()
    slug = re.sub(r"[-\s]+", "-", cleaned).strip("-")
    return slug[:max_len] or "task"
