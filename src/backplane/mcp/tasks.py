"""MCP tools for Obsidian task management."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated

from loguru import logger
from pydantic import Field

from backplane.mcp.auth import OAuthToolRegistrationKwargs, oauth_tool_registration_kwargs
from backplane.services.tasks import TaskService
from backplane.utils import enums  # noqa: TC001

if TYPE_CHECKING:
    from fastmcp import FastMCP

_CANDIDATE_SNIPPET_MAX_LEN = 80
_CREATE_TASK_DESCRIPTION = (
    "Create a structured task note for something actionable.\n\n"
    "Use this when the user mentions something they need to do, want to remember "
    "to act on, or asks you to 'make a task', 'add to my list', 'remind me to', "
    "'I should...', 'I need to...', etc.\n\n"
    "This tool always creates the task. Matching against prior inbox captures is "
    "best-effort only: high-confidence matches are linked automatically, uncertain "
    "matches are returned as candidates to offer back to the user, and unmatched "
    "tasks are created normally.\n\n"
    "When the user confirms a specific prior capture, pass its ID as "
    "link_capture_id. For an already-created task, use link_task_to_capture.\n\n"
    "Do not use this for loose, non-committal ideas unless the user asks to turn "
    "one into a task. Use record_idea for speculative captures like 'maybe', "
    "'I could', 'I wonder if', or 'worth investigating'.\n\n"
    "Ask for a due date before calling if the request sounds time-sensitive "
    "(e.g. 'before the weekend', 'by Friday', 'i need to...')."
)
_LINK_TASK_TO_CAPTURE_DESCRIPTION = (
    "Link an existing task note to a confirmed prior inbox capture.\n\n"
    "Use this after create_task offered candidate captures and the user confirms "
    "which capture should be connected. Provide the task slug from the creation "
    "confirmation and the capture ID from the candidate list."
)


async def create_task(
    *,
    description: Annotated[
        str,
        Field(
            description=(
                "Natural-language task or action description. This is fuzzy-matched "
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
    link_capture_id: Annotated[
        str | None,
        Field(
            description=(
                "Optional confirmed inbox capture ID to link, e.g. "
                "'2026-05-25T21:15'. Omit unless the user explicitly confirmed "
                "which candidate capture to attach."
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
        link_capture_id: Explicit confirmed inbox capture ID to link.

    Returns:
        Concise confirmation suitable for voice assistant output.
    """
    logger.info(
        (
            "create_task called: description_len={} title={!r} due={!r} "
            "priority={!r} link_capture_id={!r}"
        ),
        len(description),
        title,
        due,
        priority,
        link_capture_id,
    )

    task = await TaskService().create_task(
        description,
        title=title,
        due=due,
        priority=priority,
        link_capture_id=link_capture_id,
    )

    parts = [f"Task '{task.title}' created at {task.path}."]
    if task.matched_capture_id:
        parts.append(f"Matched inbox capture from {task.matched_capture_id}.")
    elif task.candidate_captures:
        candidate = task.candidate_captures[0]
        snippet = " ".join(candidate.text.split())
        if len(snippet) > _CANDIDATE_SNIPPET_MAX_LEN:
            snippet = f"{snippet[: _CANDIDATE_SNIPPET_MAX_LEN - 3]}..."
        parts.append(
            (
                f"This looked similar to {candidate.id} ({snippet!r}); "
                f"say 'link it to {candidate.id}' to connect that capture."
            ),
        )

    response = " ".join(parts)
    logger.info(
        "create_task succeeded: slug={} matched_capture_id={} response={!r}",
        task.slug,
        task.matched_capture_id,
        response,
    )
    return response


async def link_task_to_capture(
    *,
    task_slug: Annotated[
        str,
        Field(description="Task note slug, e.g. 'review-backup-logs'."),
    ],
    capture_id: Annotated[
        str,
        Field(description="Inbox capture ID, e.g. '2026-05-25T21:15'."),
    ],
) -> str:
    """Link an existing task note to a confirmed inbox capture.

    Returns:
        Concise confirmation suitable for voice assistant output.
    """
    logger.info(
        "link_task_to_capture called: task_slug={!r} capture_id={!r}",
        task_slug,
        capture_id,
    )
    response = await TaskService().link_capture(task_slug, capture_id)
    logger.info("link_task_to_capture response={!r}", response)
    return response


def register_task_tools(mcp: FastMCP[None], *, require_oauth: bool = False) -> None:
    """Register task tools on a FastMCP server instance."""
    auth_kwargs: OAuthToolRegistrationKwargs = {}
    if require_oauth:
        auth_kwargs = oauth_tool_registration_kwargs()

    _ = mcp.tool(description=_CREATE_TASK_DESCRIPTION, **auth_kwargs)(create_task)
    _ = mcp.tool(description=_LINK_TASK_TO_CAPTURE_DESCRIPTION, **auth_kwargs)(
        link_task_to_capture,
    )
