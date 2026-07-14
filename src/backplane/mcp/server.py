"""FastMCP server factory for Backplane."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backplane.mcp.app_factory import build_backplane_mcp

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from fastmcp.server.auth import AuthProvider


def create_mcp_server(
    *,
    auth: AuthProvider | None = None,
    notify_home_assistant: bool = False,
    require_oauth: bool = False,
) -> FastMCP[None]:
    """Create a Backplane MCP server instance with all tools registered.

    Args:
        auth: Optional FastMCP auth provider.
        notify_home_assistant: Whether to trigger Home Assistant MCP integration
            notification and reload on startup.
        require_oauth: Whether to register tools and resources with OAuth metadata
            for ChatGPT-facing authentication.

    Returns:
        Configured FastMCP server instance.
    """
    return build_backplane_mcp(
        auth=auth,
        notify_home_assistant=notify_home_assistant,
        require_oauth=require_oauth,
    )
