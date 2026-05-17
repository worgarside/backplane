"""FastMCP server instance for Backplane."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from fastmcp import FastMCP

from backplane import __version__
from backplane.services.home_assistant import notify_startup, reload_mcp_integration


@asynccontextmanager
async def _lifespan(mcp: FastMCP[None]) -> AsyncGenerator[None]:
    raw_tools = await mcp.list_tools()
    raw_resources = await mcp.list_resources()
    raw_templates = await mcp.list_resource_templates()

    tools = [t.name for t in raw_tools]
    resources = [r.name for r in raw_resources] + [t.name for t in raw_templates]

    await notify_startup(tools, resources)
    await reload_mcp_integration()
    yield


mcp: FastMCP[None] = FastMCP(
    "Backplane",
    instructions=(
        "Backplane exposes tools for interacting with the user's personal homelab "
        "services — currently their Obsidian vault, with more integrations to follow.\n\n"
        "The user is typically speaking through a voice assistant, so keep tool "
        "outputs concise — a short confirmation is usually enough."
    ),
    version=__version__,
    lifespan=_lifespan,
)
