"""Tests for the Pydantic-compatible AsyncPath type."""

from __future__ import annotations

import pathlib

import anyio
import pytest
from pydantic import BaseModel

from backplane.utils.async_path import AsyncPath


class _SampleMetadata(BaseModel, frozen=True):
    path: AsyncPath


def test__async_path_validates_from_string() -> None:
    """AsyncPath fields accept vault-relative path strings."""
    metadata = _SampleMetadata(path="Tasks/Tasks/Foo.md")  # pyright: ignore[reportArgumentType]
    assert metadata.path == AsyncPath("Tasks/Tasks/Foo.md")


def test__async_path_validates_from_anyio_path() -> None:
    """AsyncPath fields accept plain anyio.Path instances."""
    metadata = _SampleMetadata(path=anyio.Path("Domains/Home - Property.md"))  # pyright: ignore[reportArgumentType]
    assert metadata.path == AsyncPath("Domains/Home - Property.md")


def test__async_path_rejects_invalid_type() -> None:
    """AsyncPath fields reject non-path values."""
    with pytest.raises(TypeError, match="Expected path"):
        _ = _SampleMetadata(path=123)  # pyright: ignore[reportArgumentType]


def test__async_path_validates_from_pure_path() -> None:
    """AsyncPath fields accept pathlib.PurePath values."""
    metadata = _SampleMetadata(path=pathlib.PurePath("Daily Notes/2026-05-20.md"))  # pyright: ignore[reportArgumentType]
    assert metadata.path == AsyncPath("Daily Notes/2026-05-20.md")


def test__async_path_serializes_to_posix_string() -> None:
    """AsyncPath fields dump to vault-relative posix strings."""
    metadata = _SampleMetadata(path=AsyncPath("Projects/Example.md"))
    assert metadata.model_dump() == {"path": "Projects/Example.md"}
    assert metadata.model_dump_json() == '{"path":"Projects/Example.md"}'


def test__async_path_div_preserves_subclass() -> None:
    """Path division returns AsyncPath rather than anyio.Path."""
    child = AsyncPath("Tasks") / "Tasks/Foo.md"
    assert type(child) is AsyncPath
    assert child.as_posix() == "Tasks/Tasks/Foo.md"
