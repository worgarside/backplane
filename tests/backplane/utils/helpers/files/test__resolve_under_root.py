"""Tests for safe path resolution under a root directory."""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import pytest

from backplane.utils.helpers.files import resolve_under_root

if TYPE_CHECKING:
    import anyio


def test__resolve_under_root_accepts_relative_path(vault_path: anyio.Path) -> None:
    """Normal relative paths resolve under the root."""
    resolved = resolve_under_root(vault_path, pathlib.PurePath("Tasks/foo.md"))
    expected = pathlib.Path(str(vault_path / "Tasks/foo.md")).resolve()
    assert pathlib.Path(str(resolved)) == expected


def test__resolve_under_root_rejects_traversal(vault_path: anyio.Path) -> None:
    """Path traversal attempts are rejected."""
    with pytest.raises(ValueError, match="Unsafe path"):
        _ = resolve_under_root(vault_path, pathlib.PurePath("../etc/passwd"))


def test__resolve_under_root_rejects_absolute_path(vault_path: anyio.Path) -> None:
    """Absolute relative paths are rejected."""
    with pytest.raises(ValueError, match="Unsafe path"):
        _ = resolve_under_root(vault_path, pathlib.PurePath("/etc/passwd"))


def test__resolve_under_root_rejects_embedded_parent_segments(
    vault_path: anyio.Path,
) -> None:
    """Paths containing ``..`` segments are rejected even when nested."""
    with pytest.raises(ValueError, match="Unsafe path"):
        _ = resolve_under_root(
            vault_path,
            pathlib.PurePath("Tasks/foo/../../outside.md"),
        )
