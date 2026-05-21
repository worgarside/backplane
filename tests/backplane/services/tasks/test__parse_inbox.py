"""Tests for voice inbox capture parsing."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from backplane.services.obsidian import ObsidianService
from backplane.services.tasks import _parse_inbox
from backplane.utils import today
from backplane.utils.markdown import MarkdownDocument

if TYPE_CHECKING:
    import anyio


async def test__parse_inbox_returns_recent_captures(vault_path: anyio.Path) -> None:
    """Captures within the lookback window are parsed with stable IDs."""
    today_iso = today().isoformat()
    yesterday = (today() - dt.timedelta(days=1)).isoformat()
    old = (today() - dt.timedelta(days=40)).isoformat()
    inbox = vault_path / ObsidianService.IDEA_INBOX_PATH
    await inbox.parent.mkdir(parents=True, exist_ok=True)
    _ = await inbox.write_text(
        f"""# {today_iso}

## 09:15

Today's capture

# {yesterday}

## 10:00

Yesterday's capture

# {old}

## 11:00

Too old
""",
        encoding="utf-8",
    )

    async with MarkdownDocument(
        vault_path=ObsidianService.IDEA_INBOX_PATH,
        read_only=True,
    ) as doc:
        captures = _parse_inbox(doc, days=30)

    assert [c.id for c in captures] == [
        f"{today_iso}T09:15",
        f"{yesterday}T10:00",
    ]
    assert captures[0].text == "Today's capture"
