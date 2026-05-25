"""Shared test fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import anyio
import pytest

from backplane.utils.settings import SETTINGS

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def vault_path(tmp_path: Path) -> anyio.Path:
    """Provide a temporary vault root for path-resolution tests."""
    return anyio.Path(tmp_path)


@pytest.fixture
def obsidian_vault(
    vault_path: anyio.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> anyio.Path:
    """Point application settings at a temporary vault root."""
    monkeypatch.setattr(SETTINGS, "obsidian_vault_path", vault_path)
    return vault_path
