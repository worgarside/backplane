"""Tests for vault entity path resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from backplane.services.vault_entities import VaultEntityService
from backplane.utils import exc
from backplane.utils.enums import VaultEntityKind
from backplane.utils.helpers.files import atomic_write_text

if TYPE_CHECKING:
    import anyio


async def test__resolve_entity_path_matches_slug(obsidian_vault: anyio.Path) -> None:
    """Entity names resolve via slugified filenames first."""
    domains = obsidian_vault / "Domains"
    await domains.mkdir(parents=True)
    note = domains / "home-assistant.md"
    await atomic_write_text(note, "# Home Assistant\n")

    resolved = await VaultEntityService.resolve_entity_path(
        VaultEntityKind.DOMAIN,
        "Home Assistant",
    )

    assert resolved == note


async def test__resolve_entity_path_falls_back_to_h1_title(
    obsidian_vault: anyio.Path,
) -> None:
    """Entity names resolve by H1 title when the slug filename differs."""
    domains = obsidian_vault / "Domains"
    await domains.mkdir(parents=True)
    note = domains / "custom-slug.md"
    await atomic_write_text(note, "# Home Assistant\n")

    resolved = await VaultEntityService.resolve_entity_path(
        VaultEntityKind.DOMAIN,
        "Home Assistant",
    )

    assert resolved == note


async def test__resolve_entity_path_returns_none_when_missing(
    obsidian_vault: anyio.Path,
) -> None:
    """Unknown entity names resolve to None."""
    _ = obsidian_vault
    assert (
        await VaultEntityService.resolve_entity_path(
            VaultEntityKind.DOMAIN,
            "Missing",
        )
        is None
    )


async def test__resolve_entity_path_raises_when_missing_entity_must_exist(
    obsidian_vault: anyio.Path,
) -> None:
    """Missing entity paths raise when existence is required."""
    _ = obsidian_vault
    with pytest.raises(exc.NotFoundError, match="not found"):
        _ = await VaultEntityService.resolve_entity_path(
            VaultEntityKind.DOMAIN,
            "Missing",
            must_exist=True,
        )
