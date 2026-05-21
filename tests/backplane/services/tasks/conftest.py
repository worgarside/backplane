"""Fixtures for task service tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from backplane.utils.settings import SETTINGS

if TYPE_CHECKING:
    import anyio


@pytest.fixture
def vault_settings(
    vault_path: anyio.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> anyio.Path:
    """Point SETTINGS at a temporary vault root."""
    monkeypatch.setattr(SETTINGS, "obsidian_vault_path", vault_path)
    return vault_path
