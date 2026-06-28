"""Shared fixtures for HA MCP upstream tests."""

from __future__ import annotations

import pytest
from fastmcp import FastMCP

fake_ha_mcp = FastMCP("Fake HA MCP")


@fake_ha_mcp.tool
def ha_get_state(entity_id: str) -> dict[str, str]:
    """Return a fake entity state."""
    return {"entity_id": entity_id, "state": "off"}


@fake_ha_mcp.tool
def ha_call_service(
    domain: str,
    service: str,
    target: dict[str, object],
) -> dict[str, bool]:
    """Pretend to call a Home Assistant service."""
    _ = domain, service, target
    return {"changed": True}


@pytest.fixture
def sample_fake_ha_mcp() -> FastMCP[None]:
    """Return the in-process fake HA MCP server used by upstream tests."""
    return fake_ha_mcp
