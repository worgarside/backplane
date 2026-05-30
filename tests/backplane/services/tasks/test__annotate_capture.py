"""Tests for annotating matched inbox captures."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backplane.services.tasks import Capture, _annotate_capture
from backplane.utils import VAULT_PATHS

if TYPE_CHECKING:
    import anyio
    from pytest_mock import MockerFixture


async def test__annotate_capture_logs_warning_when_inbox_is_missing(
    obsidian_vault: anyio.Path,
    mocker: MockerFixture,
) -> None:
    """Missing inbox files are ignored because annotation is best effort."""
    _ = obsidian_vault
    mock_warning = mocker.patch("backplane.services.tasks.logger.warning")
    capture = Capture(
        id="2026-05-25T21:15",
        date="2026-05-25",
        time="21:15",
        text="Review backup logs",
        path=VAULT_PATHS.inbox_dir / "Ideas.md",
    )

    await _annotate_capture(capture, "review-backup-logs")

    mock_warning.assert_called_once()
