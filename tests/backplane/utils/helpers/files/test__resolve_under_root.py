"""Tests for safe path resolution under a root directory."""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import pytest

from backplane.utils.async_path import AsyncPath
from backplane.utils.helpers.files import resolve_under_root

if TYPE_CHECKING:
    from pathlib import Path


async def test__resolve_under_root_accepts_relative_path(
    obsidian_vault: AsyncPath,
) -> None:
    """Verify that resolve_under_root correctly resolves relative paths under the root directory."""
    resolved = await resolve_under_root(AsyncPath("Tasks/foo.md"))
    expected = await AsyncPath(str(obsidian_vault / "Tasks/foo.md")).resolve()
    assert pathlib.Path(str(resolved)) == expected


async def test__resolve_under_root_rejects_traversal(
    obsidian_vault: AsyncPath,
) -> None:
    """Path traversal attempts are rejected."""
    _ = obsidian_vault
    with pytest.raises(ValueError, match="Unsafe path"):
        _ = await resolve_under_root(pathlib.PurePath("../etc/passwd"))


async def test__resolve_under_root_rejects_absolute_path(
    obsidian_vault: AsyncPath,
) -> None:
    """Verify that resolve_under_root rejects absolute paths."""
    _ = obsidian_vault
    with pytest.raises(ValueError, match="Unsafe path"):
        _ = await resolve_under_root(pathlib.PurePath("/etc/passwd"))


async def test__resolve_under_root_rejects_embedded_parent_segments(
    obsidian_vault: AsyncPath,
) -> None:
    """Paths containing ``..`` segments are rejected even when nested."""
    _ = obsidian_vault
    with pytest.raises(ValueError, match="Unsafe path"):
        _ = await resolve_under_root(
            pathlib.PurePath("Tasks/foo/../../outside.md"),
        )


async def test__resolve_under_root_rejects_symlink_escape(
    obsidian_vault: AsyncPath,
    tmp_path: Path,
) -> None:
    """Symlinked paths that resolve outside the root are rejected."""
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (pathlib.Path(str(obsidian_vault)) / "escape").symlink_to(outside)
    with pytest.raises(ValueError, match="Path escapes root"):
        _ = await resolve_under_root(pathlib.PurePath("escape/secret.md"))
