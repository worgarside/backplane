"""Async file I/O and path resolution helpers."""

from __future__ import annotations

import pathlib
from os import PathLike

import anyio
from anyio import NamedTemporaryFile
from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema
from typing_extensions import override

from backplane.utils.settings import SETTINGS


class AsyncPath(anyio.Path):
    """Pydantic-compatible ``anyio.Path`` for models and tool responses."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: object,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        def validate(value: object) -> AsyncPath:
            if isinstance(value, cls):
                return value
            if isinstance(value, anyio.Path):
                return cls(value.as_posix())
            if isinstance(value, str | pathlib.Path):
                return cls(value)
            msg = f"Expected path, got {type(value)!r}"
            raise TypeError(msg)

        def serialize_path(path: AsyncPath) -> str:
            return path.as_posix()

        return core_schema.json_or_python_schema(
            json_schema=core_schema.no_info_plain_validator_function(validate),
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(cls),
                core_schema.no_info_plain_validator_function(validate),
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                serialize_path,
            ),
        )

    @override
    def __truediv__(self, other: str | PathLike[str]) -> AsyncPath:
        return type(self)(self._path / other)

    @override
    def __rtruediv__(self, other: str | PathLike[str]) -> AsyncPath:
        return type(self)(other) / self


async def atomic_write_text(path: anyio.Path, content: str) -> None:
    """Write ``content`` to ``path`` atomically via a system temporary file.

    Content is written to a temp file under the system temp directory, then
    moved into place with ``replace`` so readers never see a partial file.
    Temp files are not created next to ``path``, avoiding sync/index noise.

    Args:
        path: Destination file path.
        content: Text to write.
    """
    await path.parent.mkdir(parents=True, exist_ok=True)
    async with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix="backplane-",
        suffix=".tmp",
    ) as tmp_file:
        _ = await tmp_file.write(content)

        await tmp_file.flush()
        _ = await anyio.Path(tmp_file.wrapped.name).replace(path)


async def resolve_under_root(relative: anyio.Path | pathlib.PurePath) -> anyio.Path:
    """Resolve a path relative to the Obsidian vault and ensure it stays inside.

    Args:
        relative: Path relative to the configured vault root.

    Returns:
        Resolved absolute path under the vault.

    Raises:
        ValueError: If ``relative`` is absolute, contains ``..``, or escapes the vault.
    """
    if relative.is_absolute() or ".." in relative.parts:
        msg = f"Unsafe path: {relative!s}"
        raise ValueError(msg)

    root_resolved = await SETTINGS.obsidian_vault_path.resolve()
    resolved = await (root_resolved / relative).resolve()

    try:
        _ = resolved.relative_to(root_resolved)
    except ValueError as exc:
        msg = f"Path escapes root: {relative!s}"
        raise ValueError(msg) from exc

    return resolved
