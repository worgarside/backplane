"""Task creation service for structured task management from voice captures."""

from __future__ import annotations

import asyncio
import datetime as dt
import io
import operator
import pathlib
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Annotated, Final, cast, final

from loguru import logger
from pydantic import BaseModel, Field
from pydantic_ai import Agent, AgentRunResult
from rapidfuzz import fuzz

from backplane.services import ObsidianService
from backplane.utils import (
    SETTINGS,
    YAML_LOADER,
    MarkdownDocument,
    atomic_write_text,
    enums,
    resolve_under_root,
    safe_slug,
    today,
)
from backplane.utils.kanban import append_board_card

if TYPE_CHECKING:
    from pydantic_ai.usage import RunUsage

_TASKS_DIR: Final = pathlib.PurePath("Tasks")
_DOMAINS_DIR: Final = pathlib.PurePath("Domains")
_RESOURCES_DIR: Final = pathlib.PurePath("Resources")
_PEOPLE_DIR: Final = pathlib.PurePath("People")
_BOARD_PATH: Final = pathlib.PurePath("Tasks/Board.md")
_INBOX_DAYS: Final = 30
_SCORE_AUTO: Final = 70.0
_SCORE_CANDIDATE: Final = 60.0
_MIN_AUTO_GAP: Final = 10.0
_LOG_TEXT_MAX_LEN: Final = 80
_MATCH_TOP_CANDIDATES: Final = 3


@dataclass(frozen=True, slots=True)
class Capture:
    """A single timestamped entry from the voice capture inbox."""

    id: str
    date: str
    time: str
    text: str
    path: pathlib.PurePath


@dataclass(frozen=True, slots=True)
class MatchOutcome:
    """Result of best-effort inbox capture matching."""

    matched: Capture | None
    candidates: list[Capture]


class TaskMetadata(BaseModel):
    """LLM-extracted metadata for a task."""

    title: str
    domains: Annotated[
        list[str],
        Field(
            default_factory=list,
            description=(
                "Platforms or broad knowledge areas the task belongs under "
                "(e.g. a home automation stack), not integrations or APIs."
            ),
        ),
    ]
    resources: Annotated[
        list[str],
        Field(
            default_factory=list,
            description=(
                "Specific integrations, APIs, vendors, or services to touch "
                "(e.g. a named API or device integration), not parent platforms."
            ),
        ),
    ]
    people: Annotated[
        list[str],
        Field(
            default_factory=list,
            description=(
                "People named or clearly implied in the task, including from possessives "
                "(e.g. 'Jordan' from \"Jordan's laptop\") or pronouns when a name appears "
                "in the same sentence."
            ),
        ),
    ]
    priority: enums.Priority = enums.Priority.MEDIUM
    effort: enums.Effort = enums.Effort.MEDIUM
    next_action: Annotated[
        str,
        Field(
            description=(
                "One concrete first step as a short imperative sentence "
                "(e.g. 'Research available API authentication options')."
            ),
        ),
    ] = ""


@cache
def _metadata_agent() -> Agent[None, TaskMetadata]:
    """Return the pydantic-ai agent used for task metadata extraction."""
    return Agent(
        SETTINGS.task_metadata_model,
        output_type=TaskMetadata,
        system_prompt=(
            "Extract structured task metadata from the user's description. "
            "Return concise, actionable values. "
            "Domains are platforms or broad areas the work lives under "
            "(e.g. 'Home Assistant', 'Inventory'). "
            "Resources are specific integrations, APIs, vendors, or services you will "
            "configure or call (e.g. 'Acme API', 'MQTT'). "
            "Never put the same name in both domains and resources. "
            "If a task mentions adding or updating an integration inside a platform, "
            "put the platform in domains and the integration in resources only — "
            "e.g. 'Add the Acme API to the automation platform' → domains: "
            "['Home Assistant'], resources: ['Acme API']. "
            "For people: every person named or clearly implied in the task (e.g. 'Jordan' from "
            "\"Jordan's laptop\", or the person behind 'their' when a name appears in the same "
            "sentence). "
            "When the user message lists existing domains, resources, or people, prefer those "
            "exact spellings when they clearly apply; add new names when the task mentions someone "
            "not in the list. "
            "For title: a concise imperative phrase under 60 characters. "
            "For next_action: one concrete first step as an imperative sentence. "
            "For effort: 'small' under 1 hour, 'medium' 1-4 hours, 'large' over 4 hours."
        ),
    )


def _truncate_for_log(text: str, *, max_len: int = _LOG_TEXT_MAX_LEN) -> str:
    """Return a single-line snippet safe for debug logs."""
    normalized = " ".join(text.split())
    if len(normalized) <= max_len:
        return normalized
    return f"{normalized[: max_len - 1]}…"


def _log_metadata_agent_run(result: AgentRunResult[TaskMetadata]) -> None:
    """Log token usage and estimated cost for a metadata extraction run."""
    usage = cast("RunUsage", result.usage)
    model_name = result.response.model_name or SETTINGS.task_metadata_model
    logger.info(
        (
            "Task metadata agent usage (model={}): requests={} input_tokens={} "
            "output_tokens={} total_tokens={}"
        ),
        model_name,
        usage.requests,
        usage.input_tokens,
        usage.output_tokens,
        usage.total_tokens,
    )

    if usage.cache_read_tokens or usage.cache_write_tokens:
        logger.info(
            "Task metadata agent cache tokens: read={} write={}",
            usage.cache_read_tokens,
            usage.cache_write_tokens,
        )

    try:
        cost = result.response.cost()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Task metadata agent cost unavailable: {}", exc)
        return

    logger.info(
        "Task metadata agent cost (model={}): input=${} output=${} total=${}",
        model_name,
        cost.input_price,
        cost.output_price,
        cost.total_price,
    )


def _parse_inbox(doc: MarkdownDocument, days: int = _INBOX_DAYS) -> list[Capture]:
    """Parse recent captures from the inbox document.

    Args:
        doc: Loaded inbox MarkdownDocument.
        days: How many calendar days back to search.

    Returns:
        List of captures within the lookback window, in document order.
    """
    cutoff = today() - dt.timedelta(days=days)
    captures: list[Capture] = []

    for date_section in doc.body:
        try:
            section_date = dt.date.fromisoformat(date_section.heading)
        except ValueError:
            continue

        if section_date < cutoff:
            continue

        for time_section in date_section.sections:
            capture_text = _clean_capture_text(time_section.content)
            if not capture_text:
                continue

            captures.append(
                Capture(
                    id=f"{date_section.heading}T{time_section.heading}",
                    date=date_section.heading,
                    time=time_section.heading,
                    text=capture_text,
                    path=ObsidianService.IDEA_INBOX_PATH,
                ),
            )

    return captures


def _is_task_backlink_line(line: str) -> bool:
    """Return whether a line is an appended task back-link annotation."""
    normalized = line.strip().replace("\\", "")
    return normalized.startswith("↗ [[") and normalized.endswith("]]")


def _clean_capture_text(text: str | None) -> str:
    """Return capture text without generated task back-link annotations."""
    if text is None:
        return ""

    return "\n".join(
        line.rstrip()
        for line in text.strip().splitlines()
        if not _is_task_backlink_line(line)
    ).strip()


def _fuzzy_score_breakdown(query: str, text: str) -> tuple[float, float, float]:
    """Return token-set, partial, and combined fuzzy scores."""
    token_set = fuzz.token_set_ratio(query, text)
    partial = fuzz.partial_ratio(query, text)
    return token_set, partial, max(token_set, partial)


def _fuzzy_score(query: str, text: str) -> float:
    """Return a conservative fuzzy score between query and text."""
    _, _, score = _fuzzy_score_breakdown(query, text)
    return score


def _log_match_candidates(
    description: str,
    scored: list[tuple[Capture, float]],
) -> None:
    """Log top fuzzy-match candidates at DEBUG for investigation."""
    if not scored:
        return

    logger.debug(
        "Fuzzy match query (len={}): {}",
        len(description),
        _truncate_for_log(description),
    )
    for capture, score in scored[:_MATCH_TOP_CANDIDATES]:
        token_set, partial, _ = _fuzzy_score_breakdown(description, capture.text)
        logger.debug(
            "Fuzzy match candidate id={} score={:.0f} token_set={:.0f} partial={:.0f} text={}",
            capture.id,
            score,
            token_set,
            partial,
            _truncate_for_log(capture.text),
        )


def _runner_up_gap(scored: list[tuple[Capture, float]]) -> float | None:
    """Return score gap between best and second-best candidates."""
    if len(scored) <= 1:
        return None
    return scored[0][1] - scored[1][1]


def _find_match(description: str, captures: list[Capture]) -> MatchOutcome:
    """Return a best-effort inbox capture match.

    Args:
        description: Task description to match against.
        captures: Candidate captures to score.

    Returns:
        A match outcome. Borderline candidates are surfaced but never block
        task creation.
    """
    if not captures:
        logger.debug("Fuzzy match skipped: no inbox captures in lookback window")
        return MatchOutcome(matched=None, candidates=[])

    scored: list[tuple[Capture, float]] = sorted(
        ((c, _fuzzy_score(description, c.text)) for c in captures),
        key=operator.itemgetter(1),
        reverse=True,
    )
    _log_match_candidates(description, scored)
    best_capture, best_score = scored[0]
    gap = _runner_up_gap(scored)

    if best_score >= _SCORE_AUTO and (gap is None or gap >= _MIN_AUTO_GAP):
        gap_text = f"{gap:.0f}" if gap is not None else "n/a"
        logger.info(
            "Fuzzy match accepted (score={:.0f}, runner_up_gap={}): {}",
            best_score,
            gap_text,
            best_capture.id,
        )
        return MatchOutcome(matched=best_capture, candidates=[])

    if best_score >= _SCORE_CANDIDATE:
        candidates = [capture for capture, _ in scored[:_MATCH_TOP_CANDIDATES]]
        top_ids = [capture.id for capture in candidates]
        gap_text = f"{gap:.0f}" if gap is not None else "n/a"
        logger.info(
            "Fuzzy match candidates surfaced (score={:.0f}, runner_up_gap={}, candidates={}): {}",
            best_score,
            gap_text,
            top_ids,
            best_capture.id,
        )
        return MatchOutcome(matched=None, candidates=candidates)

    logger.info(
        "Fuzzy match rejected (best_score={:.0f}, best_id={})",
        best_score,
        best_capture.id,
    )
    return MatchOutcome(matched=None, candidates=[])


def _note_title_from_markdown(text: str) -> str | None:
    """Return the first level-1 heading text, skipping YAML frontmatter."""
    in_frontmatter = False
    frontmatter_closed = False
    for line in text.splitlines():
        stripped = line.strip()
        if not frontmatter_closed and stripped == "---":
            in_frontmatter = not in_frontmatter
            if not in_frontmatter:
                frontmatter_closed = True
            continue
        if in_frontmatter:
            continue
        if line.startswith("# ") and not line.startswith("## "):
            return line.removeprefix("# ").strip()
    return None


async def _load_recent_captures() -> list[Capture]:
    """Load recent inbox captures.

    Returns:
        Recent inbox captures, or an empty list when the inbox is absent.
    """
    try:
        async with MarkdownDocument(
            vault_path=ObsidianService.IDEA_INBOX_PATH,
            read_only=True,
        ) as inbox:
            captures = _parse_inbox(inbox)
    except FileNotFoundError:
        logger.error("Idea inbox not found; skipping capture matching")
        return []

    logger.info(
        "Parsed {} inbox captures (lookback_days={})",
        len(captures),
        _INBOX_DAYS,
    )
    return captures


def _find_capture_by_id(captures: list[Capture], capture_id: str) -> Capture | None:
    """Return a capture with the given stable ID."""
    return next((capture for capture in captures if capture.id == capture_id), None)


def _capture_payload(capture: Capture) -> dict[str, str]:
    """Return the public payload used to offer optional capture linking."""
    return {"id": capture.id, "text": capture.text}


async def _list_vault_entity_names(directory: pathlib.PurePath) -> list[str]:
    """List display names of notes in a vault subdirectory (from their H1 heading).

    Returns:
        Sorted unique note titles, or an empty list if the directory is missing.
    """
    dir_path = await resolve_under_root(directory)
    if not await dir_path.is_dir():
        return []

    names: list[str] = []
    async for entry in dir_path.iterdir():
        if entry.suffix != ".md" or not await entry.is_file():
            continue

        text = await entry.read_text(encoding="utf-8")

        if title := _note_title_from_markdown(text):
            names.append(title)

    return sorted({name.casefold(): name for name in names}.values(), key=str.casefold)


async def _metadata_catalog_prompt() -> str:
    """Build a user-prompt section listing existing vault entity names.

    Returns:
        Catalog lines for the metadata agent user prompt, or an empty string.
    """
    domains, resources, people = await asyncio.gather(
        _list_vault_entity_names(_DOMAINS_DIR),
        _list_vault_entity_names(_RESOURCES_DIR),
        _list_vault_entity_names(_PEOPLE_DIR),
    )

    lines: list[str] = []
    if domains:
        lines.append(
            "Existing domains (prefer exact spelling when applicable): "
            + ", ".join(domains),
        )

    if resources:
        lines.append(
            "Existing resources (prefer exact spelling when applicable): "
            + ", ".join(resources),
        )

    if people:
        lines.append(
            "Existing people (prefer exact spelling when applicable): "
            + ", ".join(people),
        )

    if not lines:
        logger.debug("Metadata catalog empty (no domain/resource/person notes)")
        return ""

    logger.debug(
        "Metadata catalog: domains={} resources={} people={}",
        len(domains),
        len(resources),
        len(people),
    )
    return "\n".join(lines)


def _dedupe_entity_names(names: list[str]) -> list[str]:
    """Return unique entity names, preserving first-seen order (case-insensitive)."""
    seen: set[str] = set()
    unique: list[str] = []
    for name in names:
        stripped = name.strip()
        if not stripped:
            continue
        key = stripped.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(stripped)
    return unique


def _normalize_domains_and_resources(
    domains: list[str],
    resources: list[str],
) -> tuple[list[str], list[str]]:
    """Dedupe lists and resolve cross-list duplicates in favour of resources.

    Integrations/APIs should not also appear as domains when the model assigns both.

    Returns:
        Normalized domain and resource name lists.
    """
    normalized_resources = _dedupe_entity_names(resources)
    resource_keys = {name.casefold() for name in normalized_resources}
    deduped_domains = _dedupe_entity_names(domains)
    normalized_domains = [
        name for name in deduped_domains if name.casefold() not in resource_keys
    ]
    removed_domains = [
        name for name in deduped_domains if name.casefold() in resource_keys
    ]
    if removed_domains:
        logger.info(
            "Metadata normalization removed domains also listed as resources: {}",
            removed_domains,
        )
    return normalized_domains, normalized_resources


def _log_task_metadata(metadata: TaskMetadata, *, context: str) -> None:
    """Log extracted task metadata fields at INFO."""
    logger.info(
        (
            "Task metadata {}: title={!r} domains={} resources={} people={} "
            "priority={} effort={} next_action_len={}"
        ),
        context,
        metadata.title,
        metadata.domains,
        metadata.resources,
        metadata.people,
        metadata.priority,
        metadata.effort,
        len(metadata.next_action),
    )


async def _extract_metadata(
    description: str,
    title: str | None,
    priority: enums.Priority | None,
) -> TaskMetadata:
    """Extract structured task metadata using PydanticAI.

    Args:
        description: Raw task description text.
        title: Pre-supplied title (skips extraction if provided).
        priority: Pre-supplied priority (skips extraction if provided).

    Returns:
        Extracted (or fallback) TaskMetadata.
    """
    prompt_parts = [f"Task description: {description}"]
    catalog = await _metadata_catalog_prompt()
    if catalog:
        prompt_parts.append(catalog)

    if title:
        prompt_parts.append(f"Title already provided: {title!r} - keep it unchanged.")
        logger.debug("Metadata extraction title override supplied")

    if priority:
        prompt_parts.append(
            f"Priority already provided: {priority!r} - keep it unchanged.",
        )
        logger.debug("Metadata extraction priority override supplied: {}", priority)

    prompt = "\n".join(prompt_parts)
    logger.debug(
        "Metadata extraction prompt: description_len={} catalog_present={} prompt_len={}",
        len(description),
        bool(catalog),
        len(prompt),
    )

    try:
        result = await _metadata_agent().run(prompt)
        _log_metadata_agent_run(result)
        metadata = result.output
        _log_task_metadata(metadata, context="extracted")
    except Exception:  # noqa: BLE001
        logger.exception("Metadata extraction failed; using defaults")
        fallback = TaskMetadata(
            title=title or description[:60],
            domains=[],
            resources=[],
            people=[],
        )
        _log_task_metadata(fallback, context="fallback")
        return fallback

    domains, resources = _normalize_domains_and_resources(
        metadata.domains,
        metadata.resources,
    )
    metadata = metadata.model_copy(update={"domains": domains, "resources": resources})

    if title:
        metadata = metadata.model_copy(update={"title": title})
    if priority:
        metadata = metadata.model_copy(update={"priority": priority})
    _log_task_metadata(metadata, context="final")
    return metadata


def _build_task_note(
    *,
    title: str,
    now: dt.datetime,
    metadata: TaskMetadata,
    capture: Capture | None,
    description: str,
    due: str | None,
) -> str:
    """Build the full markdown string for a new task note.

    Args:
        title: Task title.
        now: Creation timestamp (local time).
        metadata: Extracted task metadata.
        capture: Matched inbox capture, or None if unmatched.
        description: Original description (used when no capture matched).
        due: Optional due date string (YYYY-MM-DD).

    Returns:
        Complete markdown string including YAML frontmatter.
    """
    fm: dict[str, object] = {
        "id": f"task-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}",
        "type": "task",
        "status": "backlog",
        "created": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "updated": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "voice-capture",
        "source_capture": capture.id if capture else None,
        "domains": metadata.domains,
        "resources": metadata.resources,
        "people": metadata.people,
        "priority": metadata.priority,
        "effort": metadata.effort,
        "due": due,
        "completed": None,
        "tags": ["task"],
    }
    buf = io.StringIO()
    YAML_LOADER.dump(fm, buf)  # pyright: ignore[reportUnknownMemberType]
    frontmatter_str = buf.getvalue()

    original = (capture.text if capture else description).strip()
    blockquote = "\n".join(
        f"> {line}" if line.strip() else ">" for line in (original.splitlines() or [""])
    )
    next_action = metadata.next_action.strip()
    activity_ts = now.strftime("%Y-%m-%d %H:%M")

    body = (
        f"# {title}\n\n"
        f"## Original Capture\n\n{blockquote}\n\n"
        f"## Next Action\n\n{next_action}\n\n"
        "## Notes\n\n"
        "## Related\n\n"
        f"## Activity Log\n\n### {activity_ts}\n\nTask created from voice capture.\n"
    )
    return f"{frontmatter_str}---\n{body}"


async def _ensure_stub(
    directory: pathlib.PurePath,
    name: str,
    note_type: str,
    source_task_slug: str,
    source_task_title: str,
) -> bool:
    """Create a minimal stub note if it does not already exist.

    Args:
        directory: Relative vault path for the note directory.
        name: Human-readable name (used as heading and for slug generation).
        note_type: Value for the ``type`` frontmatter field.
        source_task_slug: Slug of the task that caused this stub to be created.
        source_task_title: Human-readable title of the source task.

    Returns:
        True if the note was created, False if it already existed.
    """
    slug = safe_slug(name)
    path = await resolve_under_root(directory / f"{slug}.md")
    if await path.exists():
        logger.debug("Stub note already exists: {}/{}.md", directory, slug)
        return False
    content = (
        f"---\ntype: {note_type}\nstatus: active\n---\n\n"
        f"# {name}\n\n## Notes\n\n"
        "Created automatically from task intake for "
        f"[[{source_task_slug}|{source_task_title}]].\n"
    )
    await atomic_write_text(path, content)
    logger.info("Created stub note: {}/{}.md", directory, slug)
    return True


async def _create_stubs(
    names: list[str],
    directory: pathlib.PurePath,
    note_type: str,
    source_task_slug: str,
    source_task_title: str,
) -> list[str]:
    """Create stub notes for each name that doesn't exist.

    Args:
        names: Human-readable names to stub out.
        directory: Relative vault path for the note directory.
        note_type: Value for the ``type`` frontmatter field.
        source_task_slug: Slug of the task that caused these stubs to be created.
        source_task_title: Human-readable title of the source task.

    Returns:
        Names of notes that were newly created.
    """
    if not names:
        return []

    stubs_created = await asyncio.gather(
        *(
            _ensure_stub(
                directory,
                name,
                note_type,
                source_task_slug,
                source_task_title,
            )
            for name in names
        ),
    )
    created = [
        name
        for name, was_created in zip(names, stubs_created, strict=True)
        if was_created
    ]
    skipped = len(names) - len(created)
    logger.info(
        "Stub notes for {}: created={} skipped_existing={} names={}",
        note_type,
        len(created),
        skipped,
        created or names,
    )
    return created


async def _annotate_capture(match: Capture, slug: str) -> None:
    """Best-effort: append a task back-link to the matched inbox capture.

    Args:
        match: The inbox capture to annotate.
        slug: Task slug to link back to.
    """
    try:
        async with ObsidianService().idea_inbox() as inbox:
            section = inbox.get_section((match.date, match.time))
            section.append_content(f"\n↗ [[{slug}]]")
        logger.debug("Annotated inbox capture {} with task [[{}]]", match.id, slug)
    except (ValueError, FileNotFoundError) as exc:
        logger.warning("Could not annotate inbox capture: {}", exc)


@final
class TaskService:
    """Service for creating structured task notes from voice captures."""

    @staticmethod
    async def create_task(  # noqa: PLR0914
        description: str,
        title: str | None = None,
        due: str | None = None,
        priority: enums.Priority | None = None,
        link_capture_id: str | None = None,
    ) -> dict[str, object]:
        """Create a task note, update the Kanban board, and stub missing domain/resource notes.

        Args:
            description: Natural-language task description.
            title: Task title. Inferred via LLM if omitted.
            due: Due date in YYYY-MM-DD format.
            priority: Priority override: 'low', 'medium', or 'high'.
            link_capture_id: Explicit capture ID to link when the user has
                confirmed a prior inbox capture.

        Returns:
            Dict with keys: slug, path, title, matched_capture_id,
            candidate_captures, domains_created, resources_created, people_created.
        """
        captures = await _load_recent_captures()
        candidate_captures: list[Capture] = []

        if link_capture_id:
            matched_capture = _find_capture_by_id(captures, link_capture_id)
            if matched_capture is None:
                logger.warning(
                    "Requested capture link not found: {}; creating task unlinked",
                    link_capture_id,
                )
        elif captures:
            match = _find_match(description, captures)
            matched_capture = match.matched
            candidate_captures = match.candidates
        else:
            matched_capture = None

        metadata_source = (
            matched_capture.text if matched_capture is not None else description
        )
        if matched_capture is not None:
            logger.info(
                "Task metadata source: capture {} (description_len={} capture_len={})",
                matched_capture.id,
                len(description),
                len(matched_capture.text),
            )
        else:
            logger.info(
                "Task metadata source: description only (len={})",
                len(description),
            )
        metadata = await _extract_metadata(metadata_source, title, priority)

        base_slug = safe_slug(metadata.title)
        slug = base_slug
        counter = 2
        while await (await resolve_under_root(_TASKS_DIR / f"{slug}.md")).exists():
            logger.debug(
                "Task slug collision: {} already exists, trying {}",
                slug,
                f"{base_slug}-{counter}",
            )
            slug = f"{base_slug}-{counter}"
            counter += 1

        now = dt.datetime.now(tz=dt.UTC).astimezone()
        note_content = _build_task_note(
            title=metadata.title,
            now=now,
            metadata=metadata,
            capture=matched_capture,
            description=description,
            due=due,
        )
        task_path = await resolve_under_root(_TASKS_DIR / f"{slug}.md")
        await atomic_write_text(task_path, note_content)
        logger.info("Created task note: {}", task_path)

        board_path = await resolve_under_root(_BOARD_PATH)
        await append_board_card(board_path, slug)

        domains_created = await _create_stubs(
            metadata.domains,
            _DOMAINS_DIR,
            "domain",
            slug,
            metadata.title,
        )
        resources_created = await _create_stubs(
            metadata.resources,
            _RESOURCES_DIR,
            "resource",
            slug,
            metadata.title,
        )
        people_created = await _create_stubs(
            metadata.people,
            _PEOPLE_DIR,
            "person",
            slug,
            metadata.title,
        )

        if matched_capture is not None:
            await _annotate_capture(matched_capture, slug)

        logger.info(
            (
                "Task intake complete: slug={} matched_capture_id={} "
                "domains_created={} resources_created={} people_created={}"
            ),
            slug,
            matched_capture.id if matched_capture else None,
            domains_created,
            resources_created,
            people_created,
        )

        return {
            "slug": slug,
            "path": str(_TASKS_DIR / f"{slug}.md"),
            "title": metadata.title,
            "matched_capture_id": matched_capture.id if matched_capture else None,
            "candidate_captures": [
                _capture_payload(capture) for capture in candidate_captures
            ],
            "domains_created": domains_created,
            "resources_created": resources_created,
            "people_created": people_created,
        }

    @staticmethod
    async def link_capture(task_slug: str, capture_id: str) -> str:
        """Link an existing task to a confirmed inbox capture.

        Args:
            task_slug: Slug of the task note in ``Tasks``.
            capture_id: Stable capture ID, e.g. ``2026-05-25T21:15``.

        Returns:
            Concise confirmation of the linking outcome.
        """
        captures = await _load_recent_captures()
        capture = _find_capture_by_id(captures, capture_id)
        if capture is None:
            logger.warning(
                "Capture {} not found; task {} unchanged",
                capture_id,
                task_slug,
            )
            return (
                f"Capture {capture_id} was not found; task {task_slug} was not changed."
            )

        slug = safe_slug(task_slug)
        task_path = _TASKS_DIR / f"{slug}.md"
        try:
            async with MarkdownDocument(vault_path=task_path) as task:
                task.frontmatter["source_capture"] = capture.id
        except FileNotFoundError:
            logger.warning("Task {} not found while linking capture {}", slug, capture_id)
            return f"Task {slug} was not found; capture {capture_id} was not linked."

        await _annotate_capture(capture, slug)
        logger.info("Linked task {} to capture {}", slug, capture_id)
        return f"Task {slug} linked to capture {capture_id}."
