"""Tests for safe path resolution under a root directory."""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import anyio
import pytest

from backplane.utils.helpers.files import resolve_under_root
from backplane.utils.settings import SETTINGS

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def vault_settings(
    vault_path: anyio.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> anyio.Path:
    """Point SETTINGS at a temporary vault root."""
    monkeypatch.setattr(SETTINGS, "obsidian_vault_path", vault_path)
    return vault_path


async def test__resolve_under_root_accepts_relative_path(
    vault_settings: anyio.Path,
) -> None:
    """Normal relative paths resolve under the root."""
    resolved = await resolve_under_root(pathlib.PurePath("Tasks/foo.md"))
    expected = await anyio.Path(str(vault_settings / "Tasks/foo.md")).resolve()
    assert pathlib.Path(str(resolved)) == expected


async def test__resolve_under_root_rejects_traversal(
    vault_settings: anyio.Path,
) -> None:
    """Path traversal attempts are rejected."""
    _ = vault_settings
    with pytest.raises(ValueError, match="Unsafe path"):
        _ = await resolve_under_root(pathlib.PurePath("../etc/passwd"))


async def test__resolve_under_root_rejects_absolute_path(
    vault_settings: anyio.Path,
) -> None:
    """Absolute relative paths are rejected."""
    _ = vault_settings
    with pytest.raises(ValueError, match="Unsafe path"):
        _ = await resolve_under_root(pathlib.PurePath("/etc/passwd"))


async def test__resolve_under_root_rejects_embedded_parent_segments(
    vault_settings: anyio.Path,
) -> None:
    """Paths containing ``..`` segments are rejected even when nested."""
    _ = vault_settings
    with pytest.raises(ValueError, match="Unsafe path"):
        _ = await resolve_under_root(
            pathlib.PurePath("Tasks/foo/../../outside.md"),
        )


async def test__resolve_under_root_rejects_symlink_escape(
    vault_settings: anyio.Path,
    tmp_path: Path,
) -> None:
    """Symlinked paths that resolve outside the root are rejected."""
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (pathlib.Path(str(vault_settings)) / "escape").symlink_to(outside)
    with pytest.raises(ValueError, match="Path escapes root"):
        _ = await resolve_under_root(pathlib.PurePath("escape/secret.md"))
