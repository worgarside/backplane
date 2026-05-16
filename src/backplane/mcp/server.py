"""FastMCP server instance for Backplane."""

from __future__ import annotations

from fastmcp import FastMCP

from backplane import __version__

mcp: FastMCP[None] = FastMCP(
    "Backplane",
    instructions=(
        "Backplane exposes tools for interacting with the user's personal homelab "
        "services — currently their Obsidian vault, with more integrations to follow.\n\n"
        "The user is typically speaking through a voice assistant, so keep tool "
        "outputs concise — a short confirmation is usually enough."
    ),
    version=__version__,
)
