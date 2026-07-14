"""Home Assistant MCP add-on upstream proxy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastmcp.server import create_proxy
from loguru import logger

if TYPE_CHECKING:
    from fastmcp import FastMCP


@dataclass(frozen=True)
class HomeAssistantMcpConfig:
    """Configuration for the Home Assistant MCP upstream.

    Callers must validate that the upstream is enabled and that ``url`` is set
    (for example via ``Settings.require_ha_mcp_url``) before mounting.
    """

    url: str
    namespace: str


def mount_home_assistant_upstream(
    mcp: FastMCP[None],
    config: HomeAssistantMcpConfig,
) -> None:
    """Mount the Home Assistant MCP add-on as a namespaced upstream proxy.

    Args:
        mcp: Backplane MCP server to augment with HA tools.
        config: Validated HA MCP upstream configuration.
    """
    logger.info(
        "Mounting Home Assistant MCP upstream with namespace {}",
        config.namespace,
    )
    ha_proxy = create_proxy(
        config.url,
        name="Home Assistant MCP",
    )
    mcp.mount(ha_proxy, namespace=config.namespace)
