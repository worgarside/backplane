"""MCP tools for Obsidian task management."""

from __future__ import annotations

from typing import Annotated

from loguru import logger
from pydantic import Field

from backplane.services.tasks import TaskService
from backplane.utils import enums  # noqa: TC001

from .server import mcp


@mcp.tool(
    description=(
        "Save something as a task or action item.\n\n"
        "Use this when the user mentions something they need to do, want to remember "
        "to act on, or asks you to 'make a task', 'add to my list', 'remind me to', etc.\n\n"
        "Ask for a due date before calling if the request sounds time-sensitive "
        "(e.g. 'before the weekend', 'by Friday', 'i need to...')."
    ),
)
async def create_task(
    *,
    description: Annotated[
        str,
        Field(description="Natural-language task or idea description."),
    ],
    title: Annotated[
        str | None,
        Field(description="Task title. Inferred from the description if not provided."),
    ] = None,
    due: Annotated[
        str | None,
        Field(description="Due date in YYYY-MM-DD format."),
    ] = None,
    priority: Annotated[
        enums.Priority | None,
        Field(description="Priority: 'low', 'medium', or 'high'."),
    ] = None,
) -> str:
    """Create a structured task note from a voice capture or description.

    Args:
        description: Natural-language task description.
        title: Task title. Inferred via LLM if omitted.
        due: Due date in YYYY-MM-DD format.
        priority: Priority override: 'low', 'medium', or 'high'.

    Returns:
        Concise confirmation suitable for voice assistant output.
    """
    logger.info("create_task: description={!r}", description)

    result = await TaskService().create_task(
        description,
        title=title,
        due=due,
        priority=priority,
    )

    task_title = result["title"]
    slug = result["slug"]
    matched = result["matched_capture_id"]

    parts = [f"Task '{task_title}' created at Tasks/{slug}.md."]
    if matched:
        parts.append(f"Matched inbox capture from {matched}.")

    return " ".join(parts)
