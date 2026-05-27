"""Tests for domain/resource metadata normalization."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backplane.services.tasks import _normalize_domains_and_resources

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


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
        ["Acme API", "Home Assistant"],
        ["Acme API"],
    )
    assert domains == ["Home Assistant"]
    assert resources == ["Acme API"]


def test__normalize_domains_and_resources_logs_removed_domains(
    mocker: MockerFixture,
) -> None:
    """Overlapping domain names removed in favour of resources are logged."""
    mock_info = mocker.patch("backplane.services.tasks.logger.info")

    _normalize_domains_and_resources(
        ["Acme API", "Home Assistant"],
        ["Acme API"],
    )

    mock_info.assert_called_once()
    assert "Acme API" in str(mock_info.call_args.args[1])
