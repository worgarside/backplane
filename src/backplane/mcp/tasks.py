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
        Field(
            description=(
                "Natural-language task or idea description. This is fuzzy-matched "
                "against existing inbox captures, so include distinctive nouns, "
                "names, and phrases from the original capture when available. "
                "Exact wording is helpful but not required; keep extra context "
                "that may help extract task metadata."
            ),
        ),
    ],
    title: Annotated[
        str | None,
        Field(
            description=(
                "Optional task title override. Omit unless the user supplied a clear "
                "title; otherwise inferred from the matched capture or description."
            ),
        ),
    ] = None,
    due: Annotated[
        str | None,
        Field(
            description=(
                "Optional due date in YYYY-MM-DD format. Ask before setting if timing "
                "is implied but not explicit."
            ),
        ),
    ] = None,
    priority: Annotated[
        enums.Priority | None,
        Field(
            description=(
                "Optional priority override: 'low', 'medium', or 'high'. Omit unless "
                "the user explicitly indicates urgency or importance."
            ),
        ),
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
