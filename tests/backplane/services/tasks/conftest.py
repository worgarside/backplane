"""Shared fixtures for task service tests."""

from __future__ import annotations

import pathlib

import pytest

from backplane.services.tasks import Capture


@pytest.fixture
def sample_captures() -> list[Capture]:
    """Recent inbox captures used for matching tests."""
    path = pathlib.PurePath("Inbox/Ideas.md")
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
