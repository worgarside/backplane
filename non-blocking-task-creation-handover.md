# Handover: Non-Blocking Task Creation

## Summary

This handover documents the completed work to make Backplane's `create_task` MCP tool impossible to block via ambiguous inbox-capture matching.

The original issue was discovered from a Home Assistant Assist debug trace stored in `src/backplane/sample.yaml`. The user tried to create a new task about a Home Assistant rain/roof-door alert. Backplane repeatedly failed with `Ambiguous match` errors because unrelated prior inbox captures shared generic words such as `notification`, `update`, and `Home Assistant`. The task was never created until the user changed course and asked to record it as an idea.

The implemented fix changes capture matching from a hard gate into a best-effort enhancement:

- `create_task` always creates a task when the task creation path itself is healthy.
- High-confidence capture matches are linked automatically.
- Borderline matches are returned as optional candidates, not errors.
- The caller can explicitly link a known capture at creation time with `link_capture_id`.
- A new follow-up MCP tool, `link_task_to_capture`, can link an already-created task to a confirmed capture.

## Original Failure

The relevant conversation was in `src/backplane/sample.yaml`, all under conversation ID `01KSR7Z0B04XPR9BYVXVG0W1FX` on the `GPT 5.4 Mini w Backplane` Assist pipeline.

The user asked for a new task:

```text
new task - the rain + roof door open alert notification should update to show the rain amount every time it changes
```

Backplane's MCP tool call was:

```yaml
tool_name: backplane__create_task
tool_args:
  description: >-
    the rain + roof door open alert notification should update to
    show the rain amount every time it changes
  title: Update rain + roof door open alert notification
  priority: medium
  due: null
```

The tool failed:

```text
Error calling tool 'create_task': Ambiguous match (score=57).
Did you mean one of these captures:
'2026-05-17T01:44': 'I need to create reminder notifications for the mood tracker';
'2026-05-17T23:04': 'When I do some kind of interaction with backplane, I should send myself notifications with deep links to that specific note.';
'2026-05-27T10:42': 'I need a guest or cleaner mode to disable all of the light timeouts.'?
Please clarify or supply the exact capture text.
```

Subsequent attempts produced the same class of failure with scores in the old 55-69 ambiguous band. Example false candidates included:

- `I need to create reminder notifications for the mood tracker`
- `Track LLM usage and cost in Home Assistant.`
- `Update the Open Banking integration in Home Assistant to include Vic's Amex card and send her notifications...`
- `When I do some kind of interaction with backplane, I should send myself notifications with deep links...`

None were semantically related to the requested rain-alert task.

## Root Cause

The root cause was in `src/backplane/services/tasks.py`, function `_find_match`.

Before this change:

- `_find_match(description, captures)` returned a `Capture | None`.
- Scores `>= 70` auto-linked a capture.
- Scores `< 55` were rejected and allowed task creation without a capture link.
- Scores `55-69` raised `ValueError("Ambiguous match...")`.

That `ValueError` propagated through `TaskService.create_task` and was re-raised by the MCP layer in `src/backplane/mcp/tasks.py`, which turned a weak optional inbox match into a hard user-facing failure.

The scorer uses RapidFuzz:

```python
token_set = fuzz.token_set_ratio(query, text)
partial = fuzz.partial_ratio(query, text)
score = max(token_set, partial)
```

Using `max(token_set_ratio, partial_ratio)` made generic overlap dangerous. A new task containing common terms like `notification`, `update`, or `Home Assistant` could score in the old ambiguous band against unrelated captures. That was enough to block the creation of a brand-new task.

Architecturally, this was backwards: capture matching is only useful to preserve provenance when converting an old idea/inbox capture into a task. It should not be allowed to decide whether the user can create a task.

## Decisions Made

### 1. Matching is Best-Effort Only

The central decision was:

```text
Task creation must never depend on inbox-capture matching.
```

If matching is uncertain, Backplane now creates the task unlinked and returns possible candidates for optional follow-up.

### 2. Borderline Matches Become Candidates

The old ambiguous error band became a candidate-offer band.

Current thresholds:

- `_SCORE_AUTO = 70.0`
- `_SCORE_CANDIDATE = 60.0`
- `_MIN_AUTO_GAP = 10.0`
- `_MATCH_TOP_CANDIDATES = 3`

The candidate floor was raised from `55.0` to `60.0` to reduce noisy suggestions.

### 3. Auto-Linking Requires a Clear Gap

Previously, any score `>= 70` was accepted as a match. Now the best score must be at least 70 and either:

- there is no runner-up, or
- the runner-up gap is at least `_MIN_AUTO_GAP`.

This prevents a close race between multiple generic captures from silently linking the wrong one.

### 4. Explicit Linking is Supported

The user selected the approach:

- Always create the task immediately.
- Include near-match candidate IDs in the confirmation.
- Keep an explicit way to link a task to a known capture.

That led to two explicit linking paths:

- `create_task(..., link_capture_id="YYYY-MM-DDTHH:MM")`
- `link_task_to_capture(task_slug="...", capture_id="YYYY-MM-DDTHH:MM")`

### 5. Unknown Explicit Capture IDs Do Not Block

If `link_capture_id` points to no known recent capture, task creation still proceeds unlinked. It logs a warning but does not fail.

This is consistent with the non-blocking principle.

## Implementation Details

### `src/backplane/services/tasks.py`

#### New Constants

```python
_SCORE_AUTO: Final = 70.0
_SCORE_CANDIDATE: Final = 60.0
_MIN_AUTO_GAP: Final = 10.0
```

`_SCORE_CANDIDATE` was raised from `55.0` to `60.0`.

#### New `MatchOutcome`

```python
@dataclass(frozen=True, slots=True)
class MatchOutcome:
    """Result of best-effort inbox capture matching."""

    matched: Capture | None
    candidates: list[Capture]
```

This replaces the previous `Capture | None` return from `_find_match`.

#### `_find_match` No Longer Raises

Current behavior:

- No captures: `MatchOutcome(matched=None, candidates=[])`
- High confidence and clear gap: `MatchOutcome(matched=best_capture, candidates=[])`
- Candidate band: `MatchOutcome(matched=None, candidates=top_candidates)`
- Weak match: `MatchOutcome(matched=None, candidates=[])`

The old `ValueError("Ambiguous match...")` branch is gone.

Logging changed accordingly:

- Accepted matches log `Fuzzy match accepted`.
- Candidate matches log `Fuzzy match candidates surfaced`.
- Weak matches log `Fuzzy match rejected`.

#### New Capture Helpers

Added:

```python
async def _load_recent_captures() -> list[Capture]
def _find_capture_by_id(captures: list[Capture], capture_id: str) -> Capture | None
def _capture_payload(capture: Capture) -> dict[str, str]
```

`_load_recent_captures` centralizes reading `Inbox/Ideas.md` through `MarkdownDocument` and parsing recent captures. If the inbox is missing, it logs and returns an empty list. Missing inboxes no longer complicate `create_task`.

`_find_capture_by_id` supports explicit links.

`_capture_payload` shapes return values for MCP confirmations:

```python
{"id": capture.id, "text": capture.text}
```

#### `TaskService.create_task`

Signature changed from:

```python
async def create_task(
    description: str,
    title: str | None = None,
    due: str | None = None,
    priority: enums.Priority | None = None,
) -> dict[str, object]:
```

to:

```python
async def create_task(
    description: str,
    title: str | None = None,
    due: str | None = None,
    priority: enums.Priority | None = None,
    link_capture_id: str | None = None,
) -> dict[str, object]:
```

Behavior:

1. Load recent captures.
2. If `link_capture_id` is provided, try to resolve that capture by ID.
3. If the explicit ID is unknown, log a warning and proceed unlinked.
4. If no explicit ID is provided, call `_find_match`.
5. Use `match.matched` for provenance/metadata source.
6. Carry `match.candidates` into the return payload.
7. Create the task note, append the Kanban board card, create stubs, and annotate only if a capture was actually matched.

Return payload now includes:

```python
{
    "slug": slug,
    "path": "Tasks/<slug>.md",
    "title": metadata.title,
    "matched_capture_id": matched_capture.id if matched_capture else None,
    "candidate_captures": [{"id": "...", "text": "..."}],
    "domains_created": domains_created,
    "resources_created": resources_created,
    "people_created": people_created,
}
```

The `# noqa: PLR0914` on `create_task` is intentional. The function already orchestrates note creation, board update, metadata extraction, stub creation, matching, and annotation. A large refactor would have been disproportionate to this fix and could obscure the behavioral change.

#### New `TaskService.link_capture`

```python
@staticmethod
async def link_capture(task_slug: str, capture_id: str) -> str:
```

Behavior:

1. Load recent captures.
2. Find capture by ID.
3. If capture is missing: return safe no-op message.
4. Normalize the provided task slug with `safe_slug`.
5. Open `Tasks/<slug>.md` via `MarkdownDocument`.
6. Set `task.frontmatter["source_capture"] = capture.id`.
7. Annotate the capture using the existing `_annotate_capture`.
8. Return a concise confirmation.

Important detail: `_annotate_capture` uses `MarkdownDocument`, and mdformat escapes Obsidian wiki-link brackets in parsed content as `\[[...]\]` when rendered. Existing helper `_is_task_backlink_line` already strips backslashes before checking annotations, so this remains compatible.

### `src/backplane/mcp/tasks.py`

#### `create_task` Tool Description

The MCP tool description now explicitly states:

- This tool always creates the task.
- Capture matching is best-effort.
- High-confidence matches link automatically.
- Uncertain matches are returned as candidates.
- Use `link_capture_id` when the user confirms a candidate.
- Use `link_task_to_capture` for already-created tasks.

This is important because the Home Assistant conversation agent depends heavily on tool descriptions to decide how to recover from near matches.

#### New Parameter

Added:

```python
link_capture_id: str | None = None
```

Description:

```text
Optional confirmed inbox capture ID to link, e.g. '2026-05-25T21:15'.
Omit unless the user explicitly confirmed which candidate capture to attach.
```

#### Removed Ambiguous Re-Raise

The old MCP code caught `ValueError`, logged a warning, and re-raised. That path is gone because ambiguous matching is no longer exceptional.

Genuine I/O or orchestration errors can still surface normally. The non-blocking guarantee specifically applies to fuzzy capture matching, not all possible filesystem failures.

#### Candidate Confirmation

If no capture was matched but candidates are returned, the MCP confirmation includes the first candidate:

```text
Task '<title>' created at Tasks/<slug>.md. This looked similar to <capture_id> ('<snippet>'); say 'link it to <capture_id>' to connect that capture.
```

Only the first candidate is included in the voice-facing confirmation to keep speech concise. The service still returns up to three candidates internally.

Snippet length is capped at `_CANDIDATE_SNIPPET_MAX_LEN = 80`.

#### New MCP Tool: `link_task_to_capture`

Added:

```python
async def link_task_to_capture(
    *,
    task_slug: str,
    capture_id: str,
) -> str:
```

It wraps `TaskService().link_capture(task_slug, capture_id)`.

Use case:

1. User creates a task.
2. Backplane says it looked similar to a prior capture and offers an ID.
3. User says something like `link it to 2026-05-17T01:44`.
4. The conversation agent calls `link_task_to_capture`.

## Tests Added or Updated

### `tests/backplane/services/tasks/conftest.py`

Added fixture:

```python
rain_alert_unrelated_captures()
```

This contains the exact kind of unrelated captures from the original failure:

- mood tracker notifications
- Open Banking/Home Assistant notifications
- Backplane deep-link notifications

### `tests/backplane/services/tasks/test__find_match.py`

Updated tests for new `MatchOutcome` API:

- high-confidence match returns `outcome.matched`
- no candidates returns no match
- weak matches return empty candidates
- loose long captures are not accepted
- ambiguous scores return candidates without raising
- high scores with close runner-up are offered instead of auto-linked
- rain-alert regression does not raise

### `tests/backplane/services/tasks/test__find_match_logging.py`

Updated logging tests:

- weak matches log rejection
- ambiguous scores log candidate surfacing, not warnings before raise
- accepted matches still log runner-up gap

### `tests/backplane/services/tasks/test__create_task_orchestration.py`

Updated expected return dict to include:

```python
"candidate_captures": []
```

### `tests/backplane/services/tasks/test__create_task_linking.py`

New file. Covers:

- explicit `link_capture_id` links a capture and skips fuzzy matching
- unknown `link_capture_id` creates an unlinked task without raising
- borderline fuzzy matches return candidates while task creation succeeds

### `tests/backplane/services/tasks/test__link_capture.py`

New file. Covers:

- `TaskService.link_capture` updates `source_capture` frontmatter and annotates the inbox capture
- unknown capture ID returns a safe no-op confirmation

### `tests/backplane/mcp/tasks/test__create_task.py`

Updated and expanded:

- `create_task` forwards `link_capture_id`
- matched capture appears in confirmation
- candidate capture appears in confirmation without exception
- `link_task_to_capture` delegates to `TaskService.link_capture`

## Verification Performed

Commands run successfully:

```bash
uv run pytest tests/backplane/services/tasks tests/backplane/mcp/tasks
```

Result:

```text
48 passed
```

```bash
uv run ruff format <changed task files>
uv run ruff check <changed task files>
```

Result:

```text
All checks passed
```

`uv run basedpyright ...` was not available because `basedpyright` is not installed in the uv dev environment. The repo defines basedpyright through pre-commit, so the pre-commit hook was used instead:

```bash
uv run pre-commit run basedpyright --files \
  src/backplane/services/tasks.py \
  src/backplane/mcp/tasks.py \
  tests/backplane/services/tasks/test__find_match.py \
  tests/backplane/services/tasks/test__find_match_logging.py \
  tests/backplane/services/tasks/test__create_task_linking.py \
  tests/backplane/services/tasks/test__link_capture.py \
  tests/backplane/mcp/tasks/test__create_task.py
```

Result:

```text
basedpyright-src   Passed
basedpyright-tests Passed
```

Full test suite:

```bash
uv run pytest
```

Result:

```text
120 passed
```

IDE lint check:

```text
ReadLints: no linter errors found
```

## Current Working Tree Notes

At the time this handover was written, the relevant changed files were:

- `src/backplane/services/tasks.py`
- `src/backplane/mcp/tasks.py`
- `tests/backplane/mcp/tasks/test__create_task.py`
- `tests/backplane/services/tasks/conftest.py`
- `tests/backplane/services/tasks/test__create_task_orchestration.py`
- `tests/backplane/services/tasks/test__find_match.py`
- `tests/backplane/services/tasks/test__find_match_logging.py`
- `tests/backplane/services/tasks/test__create_task_linking.py`
- `tests/backplane/services/tasks/test__link_capture.py`

Pre-existing or unrelated dirty files observed during the work:

- `uv.lock` was already modified at conversation start. Its visible diff is the package version changing from `0.3.0` to `0.4.0`, apparently from dependency sync / project metadata state.
- `src/backplane/sample.yaml` was untracked and used as the HA debug trace source. It was not modified for the fix.

This handover file itself is new:

- `non-blocking-task-creation-handover.md`

No commit was created.

## Behavior After the Fix

### New Unmatched Task

If the user says:

```text
new task: update the roof door rain alert notification with current rain amount
```

and no high-confidence capture exists, Backplane creates:

```text
Tasks/<slug>.md
```

and updates:

```text
Tasks/Board.md
```

No fuzzy-match ambiguity can block the creation.

### Borderline Candidate

If a borderline capture exists, the task still gets created and the confirmation can include:

```text
This looked similar to 2026-05-17T01:44 ('I need to create reminder notifications for the mood tracker'); say 'link it to 2026-05-17T01:44' to connect that capture.
```

### Explicit Link at Creation Time

If the conversation agent knows the correct capture ID:

```python
create_task(
    description="backup logs",
    link_capture_id="2026-05-25T21:15",
)
```

then the task note is created with:

```yaml
source_capture: 2026-05-25T21:15
```

and the inbox capture receives a task backlink annotation.

### Follow-Up Link

If the task already exists:

```python
link_task_to_capture(
    task_slug="review-backup-logs",
    capture_id="2026-05-25T21:15",
)
```

then Backplane sets `source_capture` in `Tasks/review-backup-logs.md` and annotates the capture.

## Known Tradeoffs and Future Suggestions

### Candidate Confirmation Only Mentions One Candidate

The service returns up to three candidates, but the MCP confirmation only speaks the first one. This was intentional for voice UX. If a future UI or non-voice client consumes this, consider exposing structured content or listing all candidates.

### Matching is Still Fuzzy, Not Semantic

This fix prevents fuzzy matching from blocking the user. It does not make the fuzzy matching semantically smarter.

Future options:

- Use stricter token requirements for generic terms like `notification`, `update`, and `Home Assistant`.
- Add domain-specific stopwords or downweight common automation vocabulary.
- Add embedding/semantic matching for inbox capture conversion only.
- Add exact-capture selection UI in a dashboard.

None of these are necessary for the non-blocking guarantee.

### `TaskService.link_capture` Uses Recent Captures Only

Capture lookup still uses `_INBOX_DAYS = 30`. If the user wants to link an older capture by ID, the new follow-up tool will currently return a safe no-op. Consider adding an explicit long-lookback or all-time lookup for `link_capture`.

### Unknown Explicit Capture IDs Do Not Fail

This is intentional, but it means a typo in `link_capture_id` creates an unlinked task. That matches the stated priority: the user must never be blocked from task creation in their own app.

### `source_capture` Mutation is Minimal

`TaskService.link_capture` only updates frontmatter `source_capture` and appends a backlink to the capture. It does not update the task's `Original Capture` block to use the capture text after the fact. If desired later, a richer relinking operation could update both provenance metadata and note body.

### Board and Filesystem Failures Can Still Fail

This work makes capture matching non-blocking. It does not swallow genuine failures such as:

- unable to write `Tasks/<slug>.md`
- missing or malformed `Tasks/Board.md`
- permission errors
- filesystem concurrency errors

Those should still fail loudly because they mean task creation itself did not happen.

## Suggested Next Agent Checklist

1. Review `src/backplane/services/tasks.py` and `src/backplane/mcp/tasks.py` for the non-blocking matching flow.
2. Run `uv run pytest` if not already run in the target environment.
3. If preparing a commit, decide whether `uv.lock` belongs in the commit. It was dirty before this work and is not logically part of the task matching fix.
4. Decide whether to keep `src/backplane/sample.yaml` untracked as a local debug artifact or move/delete it. It was the HA trace source and not part of the implementation.
5. Optionally run the Home Assistant MCP integration and verify the tool descriptions now expose:
   - `create_task(..., link_capture_id=...)`
   - `link_task_to_capture(...)`
6. If testing via Assist, reproduce the rain-alert phrase. Expected result: task created, optional candidate offered, no `Ambiguous match` tool error.

## Files Most Worth Reading

- `src/backplane/services/tasks.py`: service-level match outcome, task creation, explicit linking.
- `src/backplane/mcp/tasks.py`: MCP tool schema/descriptions and voice-facing confirmations.
- `tests/backplane/services/tasks/test__find_match.py`: matching behavior and rain-alert regression.
- `tests/backplane/services/tasks/test__create_task_linking.py`: service-level explicit link and candidate behavior.
- `tests/backplane/services/tasks/test__link_capture.py`: follow-up linking behavior.
- `tests/backplane/mcp/tasks/test__create_task.py`: MCP contract and confirmations.

