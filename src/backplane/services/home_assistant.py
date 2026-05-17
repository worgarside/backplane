"""Home Assistant service integration for Backplane."""

from __future__ import annotations

import aiohttp
from loguru import logger

from backplane import __version__
from backplane.utils.settings import SETTINGS

_TIMEOUT = aiohttp.ClientTimeout(total=10)


async def _call_ha_service(
    domain: str,
    service: str,
    data: dict[str, str],
) -> None:
    """POST to a Home Assistant service endpoint.

    Never raises — logs a warning on non-2xx or network error.
    """
    if not (SETTINGS.home_assistant_url and SETTINGS.home_assistant_token):
        logger.warning(
            "Skipping {domain}/{service} — HA settings not fully configured",
            domain=domain,
            service=service,
        )
        return

    url = SETTINGS.home_assistant_url / f"api/services/{domain}/{service}"
    headers = {"Authorization": f"Bearer {SETTINGS.home_assistant_token}"}

    async with (
        aiohttp.ClientSession(timeout=_TIMEOUT) as session,
        session.post(url, json=data, headers=headers) as response,
    ):
        if response.ok:
            logger.info("{}/{} → {}", domain, service, response.status)
        else:
            body = await response.text()
            logger.error(
                "{}/{} returned {} — {}",
                domain,
                service,
                response.status,
                body,
            )


async def reload_mcp_integration() -> None:
    """Trigger a reload of the Backplane MCP config entry in Home Assistant.

    No-ops silently if Home Assistant settings are not fully configured.
    """
    if not SETTINGS.home_assistant_mcp_entry_id:
        logger.debug("Skipping MCP integration reload — HA MCP entry ID not configured")
        return

    await _call_ha_service(
        "homeassistant",
        "reload_config_entry",
        {"entry_id": SETTINGS.home_assistant_mcp_entry_id},
    )


async def notify_startup(tools: list[str], resources: list[str]) -> None:
    """Create a persistent notification in Home Assistant with the running version.

    No-ops silently if Home Assistant URL or token are not configured.

    Args:
        tools: Names of registered MCP tools.
        resources: Display names of registered MCP resources and resource templates.
    """
    tool_lines = "\n".join(f"- `{t}`" for t in sorted(tools))
    resource_lines = "\n".join(f"- {r}" for r in sorted(resources))

    message = (
        f"MCP server started — v{__version__}\n\n"
        f"**Tools**\n{tool_lines}\n\n"
        f"**Resources**\n{resource_lines}"
    )

    await _call_ha_service(
        "persistent_notification",
        "create",
        {
            "title": "Backplane",
            "message": message,
            "notification_id": "backplane_startup",
        },
    )
