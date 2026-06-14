"""Tests for entity wikilink rendering."""

from __future__ import annotations

from backplane.utils import build_entity_wikilink
from backplane.utils.enums import VaultEntityKind


def test__build_entity_wikilink_uses_path_and_display_alias() -> None:
    """Slash titles map to filename stems while keeping the alias unchanged."""
    link = build_entity_wikilink(VaultEntityKind.DOMAIN, "Home / Property")

    assert link == "[[Domains/Home - Property|Home / Property]]"


def test__build_entity_wikilink_supports_projects_and_people() -> None:
    """Project and person links use their respective vault directories."""
    assert (
        build_entity_wikilink(VaultEntityKind.PROJECT, "Rented Home Formal Complaint")
        == "[[Projects/Rented Home Formal Complaint|Rented Home Formal Complaint]]"
    )
    assert build_entity_wikilink(VaultEntityKind.PERSON, "Will") == "[[People/Will|Will]]"
