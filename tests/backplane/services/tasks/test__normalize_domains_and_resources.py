"""Tests for domain/resource metadata normalization."""

from __future__ import annotations

from backplane.services.tasks import _normalize_domains_and_resources


def test__normalize_domains_and_resources_dedupes_within_lists() -> None:
    """Duplicate names in one list are collapsed case-insensitively."""
    domains, resources = _normalize_domains_and_resources(
        ["Automation", "automation"],
        ["MQTT", "mqtt"],
    )
    assert domains == ["Automation"]
    assert resources == ["MQTT"]


def test__normalize_domains_and_resources_prefers_resources_on_overlap() -> None:
    """The same name cannot appear as both domain and resource."""
    domains, resources = _normalize_domains_and_resources(
        ["Acme API", "Automation Platform"],
        ["Acme API"],
    )
    assert domains == ["Automation Platform"]
    assert resources == ["Acme API"]
