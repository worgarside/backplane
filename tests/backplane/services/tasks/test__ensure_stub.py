"""Tests for task entity stub creation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backplane.services.tasks import _create_stubs, _ensure_stub
from backplane.utils import VAULT_PATHS
from backplane.utils.helpers.files import atomic_write_text

if TYPE_CHECKING:
    import anyio


async def test__ensure_stub_creates_missing_note(obsidian_vault: anyio.Path) -> None:
    """A missing entity note is created as a minimal stub."""
    created = await _ensure_stub(
        VAULT_PATHS.domains_dir,
        "Home Assistant",
        "domain",
        "review-home-assistant",
        "Review Home Assistant",
    )

    assert created is True
    assert await (obsidian_vault / "Domains/home-assistant.md").read_text(
        encoding="utf-8",
    ) == (
        "---\n"
        "type: domain\n"
        "status: active\n"
        "---\n\n"
        "# Home Assistant\n\n"
        "## Notes\n\n"
        "Created automatically from task intake for "
        "[[review-home-assistant|Review Home Assistant]].\n"
    )


async def test__ensure_stub_returns_false_for_existing_note(
    obsidian_vault: anyio.Path,
) -> None:
    """Existing entity notes are left unchanged."""
    domains = obsidian_vault / "Domains"
    await domains.mkdir(parents=True)
    existing = domains / "home-assistant.md"
    await atomic_write_text(existing, "# Existing\n")

    created = await _ensure_stub(
        VAULT_PATHS.domains_dir,
        "Home Assistant",
        "domain",
        "review-home-assistant",
        "Review Home Assistant",
    )

    assert created is False
    assert await existing.read_text(encoding="utf-8") == "# Existing\n"


async def test__create_stubs_returns_only_newly_created_names(
    obsidian_vault: anyio.Path,
) -> None:
    """Bulk stub creation reports names that were actually created."""
    domains = obsidian_vault / "Domains"
    await domains.mkdir(parents=True)
    await atomic_write_text(domains / "existing.md", "# Existing\n")

    created = await _create_stubs(
        ["Existing", "New Domain"],
        VAULT_PATHS.domains_dir,
        "domain",
        "review-home-assistant",
        "Review Home Assistant",
    )

    assert created == ["New Domain"]
