"""Async file I/O and path resolution helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from anyio import NamedTemporaryFile

from backplane.utils.async_path import AsyncPath
from backplane.utils.settings import SETTINGS

if TYPE_CHECKING:
    import pathlib


async def atomic_write_text(path: AsyncPath, content: str) -> None:
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
        _ = await AsyncPath(tmp_file.wrapped.name).replace(path)


async def resolve_under_root(
    relative: AsyncPath | pathlib.PurePath | str,
) -> AsyncPath:
    """Resolve a path relative to the Obsidian vault and ensure it stays inside.

    Args:
        relative: Path relative to the configured vault root.

    Returns:
        Resolved absolute path under the vault.

    Raises:
        ValueError: If ``relative`` is absolute, contains ``..``, or escapes the vault.
    """
    path = relative if isinstance(relative, AsyncPath) else AsyncPath(relative)
    if path.is_absolute() or ".." in path.parts:
        msg = f"Unsafe path: {path!s}"
        raise ValueError(msg)

    root_resolved = await SETTINGS.obsidian_vault_path.resolve()
    resolved = AsyncPath((await (root_resolved / path).resolve()).as_posix())

    try:
        _ = resolved.relative_to(root_resolved)
    except ValueError as exc:
        msg = f"Path escapes root: {path!s}"
        raise ValueError(msg) from exc

    return resolved
