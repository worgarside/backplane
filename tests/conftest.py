"""Shared test fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import anyio
import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def vault_path(tmp_path: Path) -> anyio.Path:
    """Provide a temporary vault root for path-resolution tests."""
    return anyio.Path(tmp_path)
