"""Tests for HA MCP upstream mounting."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastmcp.server.auth.oidc_proxy import OIDCConfiguration
from starlette.routing import Route

from backplane.mcp.app_factory import build_backplane_mcp
from backplane.mcp.asgi import (
    _build_ha_mcp,
    compose_private_mcp_app,
    compose_public_mcp_app,
)
from backplane.mcp.upstreams.ha import (
    HomeAssistantMcpConfig,
    mount_home_assistant_upstream,
)
from backplane.utils.async_path import AsyncPath
from backplane.utils.exceptions import UserError
from backplane.utils.settings import Settings

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from pytest_mock import MockerFixture


@pytest.fixture
def ha_upstream_settings() -> Settings:
    """Return settings with HA MCP upstream enabled against a fake URL."""
    return Settings.model_validate(
        {
            "obsidian_vault_path": AsyncPath("/tmp/vault"),
            "ha_mcp_enabled": True,
            "ha_mcp_url": "http://fake-ha-mcp.example.com/mcp",
            "ha_mcp_namespace": "ha",
        },
    )


def test__mount_home_assistant_upstream__requires_url_when_enabled() -> None:
    """Mounting HA upstream fails fast when enabled without a URL."""
    mcp = build_backplane_mcp()
    config = HomeAssistantMcpConfig(
        enabled=True,
        url=None,
        namespace="ha",
        connect_timeout_seconds=5.0,
    )

    with pytest.raises(RuntimeError, match="BACKPLANE_HA_MCP_URL"):
        mount_home_assistant_upstream(mcp, config)


def test__require_ha_mcp_url__raises_when_compose_private_app_enabled_without_url(
    mocker: MockerFixture,
    ha_upstream_settings: Settings,
) -> None:
    """Composing the private app rejects enabled HA MCP without a URL."""
    settings = ha_upstream_settings.model_copy(update={"ha_mcp_url": None})
    mocker.patch("backplane.utils.settings.SETTINGS", settings)
    mocker.patch("backplane.mcp.asgi.SETTINGS", settings)

    with pytest.raises(UserError, match="BACKPLANE_HA_MCP_URL"):
        compose_private_mcp_app()


async def test__build_backplane_mcp__core_excludes_ha_tools() -> None:
    """The core Backplane MCP server does not expose namespaced HA tools."""
    mcp = build_backplane_mcp()
    tools = await mcp.list_tools()

    assert not any(tool.name.startswith("ha_") for tool in tools)


async def test__build_ha_mcp__includes_namespaced_tools(
    mocker: MockerFixture,
    ha_upstream_settings: Settings,
    sample_fake_ha_mcp: FastMCP[None],
) -> None:
    """The HA-augmented MCP server exposes namespaced upstream tools."""
    mocker.patch("backplane.utils.settings.SETTINGS", ha_upstream_settings)
    mocker.patch("backplane.mcp.asgi.SETTINGS", ha_upstream_settings)
    mocker.patch(
        "backplane.mcp.upstreams.ha.create_proxy",
        return_value=sample_fake_ha_mcp,
    )

    ha_app = _build_ha_mcp(auth=None, require_oauth=False)
    assert ha_app is not None
    tools = await ha_app.state.fastmcp_server.list_tools()
    tool_names = [tool.name for tool in tools]

    assert "ha_ha_get_state" in tool_names
    assert "ha_ha_call_service" in tool_names


def test__compose_private_mcp_app__registers_mcp_ha_route_when_enabled(
    mocker: MockerFixture,
    ha_upstream_settings: Settings,
    sample_fake_ha_mcp: FastMCP[None],
) -> None:
    """The private HTTP app exposes /mcp-ha when HA upstream is enabled."""
    mocker.patch("backplane.utils.settings.SETTINGS", ha_upstream_settings)
    mocker.patch("backplane.mcp.asgi.SETTINGS", ha_upstream_settings)
    mocker.patch("backplane.services.home_assistant.notify_startup")
    mocker.patch("backplane.services.home_assistant.reload_mcp_integration")
    mocker.patch(
        "backplane.mcp.upstreams.ha.create_proxy",
        return_value=sample_fake_ha_mcp,
    )

    app = compose_private_mcp_app()
    route_paths = [route.path for route in app.routes if isinstance(route, Route)]

    assert "/mcp" in route_paths
    assert "/mcp-ha" in route_paths


def test__compose_public_mcp_app__does_not_register_mcp_ha_when_disabled(
    mocker: MockerFixture,
    sample_oidc_configuration: OIDCConfiguration,
) -> None:
    """The public app exposes only /mcp when HA upstream is disabled."""
    settings = Settings.model_validate(
        {
            "obsidian_vault_path": AsyncPath("/tmp/vault"),
            "mcp_public_base_url": "https://backplane-mcp.example.com",
            "mcp_oidc_config_url": (
                "https://auth.example.com/application/o/backplane-mcp/"
                ".well-known/openid-configuration"
            ),
            "mcp_oidc_client_id": "client-id",
            "mcp_oidc_client_secret": "test-oauth-credential",
            "ha_mcp_enabled": False,
        },
    )
    mocker.patch("backplane.mcp.auth.SETTINGS", settings)
    mocker.patch("backplane.utils.settings.SETTINGS", settings)
    mocker.patch("backplane.mcp.asgi.SETTINGS", settings)
    mocker.patch(
        "backplane.mcp.auth.OIDCConfiguration.get_oidc_configuration",
        return_value=sample_oidc_configuration,
    )

    app = compose_public_mcp_app()
    route_paths = [route.path for route in app.routes if isinstance(route, Route)]

    assert "/mcp" in route_paths
    assert "/mcp-ha" not in route_paths


def test__mount_home_assistant_upstream__does_not_log_secret_url(
    mocker: MockerFixture,
    ha_upstream_settings: Settings,
) -> None:
    """Mounting HA upstream never logs the private add-on URL."""
    mock_logger = mocker.patch("backplane.mcp.upstreams.ha.logger")
    mocker.patch("backplane.mcp.upstreams.ha.create_proxy")
    mcp = build_backplane_mcp()
    config = HomeAssistantMcpConfig(
        enabled=True,
        url=ha_upstream_settings.ha_mcp_url,
        namespace=ha_upstream_settings.ha_mcp_namespace,
        connect_timeout_seconds=ha_upstream_settings.ha_mcp_connect_timeout_seconds,
    )

    mount_home_assistant_upstream(mcp, config)

    secret_url = ha_upstream_settings.ha_mcp_url
    assert secret_url is not None
    for call in mock_logger.info.call_args_list:
        assert secret_url not in str(call)
