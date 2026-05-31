"""FastMCP server factory for Backplane."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from backplane import __version__
from backplane.mcp.obsidian import register_obsidian_tools
from backplane.mcp.tasks import register_task_tools
from backplane.services.home_assistant import notify_startup, reload_mcp_integration

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastmcp.server.auth import AuthProvider

_INSTRUCTIONS = (
    "Backplane exposes tools for interacting with the user's personal homelab "
    "services — currently their Obsidian vault, with more integrations to follow.\n\n"
    "The user is typically speaking through a voice assistant, so keep tool "
    "outputs concise — a short confirmation is usually enough."
)


@lifespan
async def _home_assistant_lifespan(mcp: FastMCP[None]) -> AsyncGenerator[None]:
    raw_tools = await mcp.list_tools()
    raw_resources = await mcp.list_resources()
    raw_templates = await mcp.list_resource_templates()

    tools = [t.name for t in raw_tools]
    resources = [r.name for r in raw_resources] + [t.name for t in raw_templates]

    await notify_startup(tools, resources)
    await reload_mcp_integration()
    yield


def create_mcp_server(
    *,
    auth: AuthProvider | None = None,
    notify_home_assistant: bool = False,
) -> FastMCP[None]:
    """Create a Backplane MCP server instance with all tools registered.

    Args:
        auth: Optional FastMCP auth provider. Used by the public-facing
            streamable HTTP endpoint.
        notify_home_assistant: Whether startup should notify/reload the private
            Home Assistant MCP integration. Only the private SSE server should do this.

    Returns:
        Configured FastMCP server instance.
    """
    mcp: FastMCP[None] = FastMCP(
        "Backplane",
        instructions=_INSTRUCTIONS,
        version=__version__,
        auth=auth,
        lifespan=_home_assistant_lifespan if notify_home_assistant else None,
    )

    register_obsidian_tools(mcp)
    register_task_tools(mcp)

    return mcp
