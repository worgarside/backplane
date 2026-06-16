"""Shared fixtures for task service tests."""

from __future__ import annotations

import pytest

from backplane.services.tasks import Capture
from backplane.utils import VAULT_PATHS


@pytest.fixture
def sample_captures() -> list[Capture]:
    """Recent inbox captures used for matching tests."""
    path = VAULT_PATHS.inbox_dir / "Ideas.md"
    return [
        Capture(
            id="2026-01-10T09:00",
            date="2026-01-10",
            time="09:00",
            text="Schedule weekly backup verification for the database server",
            path=path,
        ),
        Capture(
            id="2026-01-10T14:30",
            date="2026-01-10",
            time="14:30",
            text=(
                "Add Jordan's calendar feed to the shared dashboard and notify them "
                "when meetings change."
            ),
            path=path,
        ),
    ]


@pytest.fixture
def rain_alert_unrelated_captures() -> list[Capture]:
    """Inbox captures that used to block a new rain-alert task."""
    path = VAULT_PATHS.inbox_dir / "Ideas.md"
    return [
        Capture(
            id="2026-05-17T01:44",
            date="2026-05-17",
            time="01:44",
            text="I need to create reminder notifications for the mood tracker",
            path=path,
        ),
        Capture(
            id="2026-05-17T14:29",
            date="2026-05-17",
            time="14:29",
            text=(
                "Update the Open Banking integration in Home Assistant to include "
                "Alice's bank card and send her notifications of how much she's spent."
            ),
            path=path,
        ),
        Capture(
            id="2026-05-17T23:04",
            date="2026-05-17",
            time="23:04",
            text=(
                "When I do some kind of interaction with backplane, I should send "
                "myself notifications with deep links to that specific note."
            ),
            path=path,
        ),
    ]
