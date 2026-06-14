# Backplane

AI-facing gateway for local services and smart home orchestration

[![License: MIT](https://img.shields.io/github/license/worgarside/backplane)](LICENSE)
[![Release](https://img.shields.io/github/v/release/worgarside/backplane)](https://github.com/worgarside/backplane/releases)
![Python](https://img.shields.io/badge/python-3.14%2B-blue)
[![Pre-Commit Hooks](https://img.shields.io/github/actions/workflow/status/worgarside/backplane/pre-commit-hooks.yml?branch=main&label=pre-commit)](https://github.com/worgarside/backplane/actions/workflows/pre-commit-hooks.yml)
[![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/worgarside/backplane?utm_source=oss&utm_medium=github&utm_campaign=worgarside%2Fbackplane&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)](https://coderabbit.ai)

## Installation

Backplane is designed to run as a persistent service on a Linux host (tested on Debian 13 in a Proxmox LXC).

### Prerequisites

- Git
- [Node.js 22+](https://nodejs.org/) and `obsidian-headless` (`npm install -g obsidian-headless`)
- An [Obsidian Sync](https://obsidian.md/sync) subscription

### 1. Clone the repo

```bash
git clone https://github.com/worgarside/backplane.git /opt/backplane
cd /opt/backplane
```

### 2. Configure environment

```bash
cp .env.example .env
$EDITOR .env
```

Set `OBSIDIAN_VAULT_PATH` to the local path where the vault will be synced.

If you plan to run the public ChatGPT-facing MCP service, also configure the
OAuth variables documented in `.env.example` before running setup with
`INSTALL_PUBLIC_MCP=true`. See `deploy/authentik-backplane-mcp.env.example`
for Authentik provider setup.

### 3. Set up Obsidian Sync

Authenticate and do an initial sync before starting the service:

```bash
ob login
ob sync --vault "My Vault" /path/to/vault
```

By default `setup.sh` expects the vault at `/root/obsidian/vaults/my-vault`. Override with the `VAULT_DIR` environment variable if your path differs.

### 4. Run setup

Install the private `backplane` and `obsidian-sync` systemd services:

```bash
sudo VAULT_DIR=/path/to/vault bash deploy/setup.sh
```

This will:

- Install [uv](https://docs.astral.sh/uv/) if not present
- Install Python 3.14 and sync dependencies
- Install and enable the `backplane` and `obsidian-sync` systemd services

#### Optional: public ChatGPT MCP service

The public MCP server refuses to start without OAuth configuration. Configure
these in `.env` **before** enabling the service:

- `MCP_PUBLIC_BASE_URL`
- `MCP_OIDC_CONFIG_URL`
- `MCP_OIDC_CLIENT_ID`
- `MCP_OIDC_CLIENT_SECRET`

See `deploy/authentik-backplane-mcp.env.example` for Authentik provider setup.

Then install and start the public service:

```bash
sudo INSTALL_PUBLIC_MCP=true VAULT_DIR=/path/to/vault bash deploy/setup.sh
```

`setup.sh` validates the OAuth variables before installing or starting
`backplane-public`. The public service unit and logrotate config are only
installed when `INSTALL_PUBLIC_MCP=true`.

### Updating

```bash
bash scripts/update.sh
```

Pulls the latest code, syncs dependencies, and restarts the service.

### Service management

```bash
systemctl status backplane
systemctl status backplane-public
systemctl status obsidian-sync
journalctl -u backplane -f
journalctl -u backplane-public -f
journalctl -u obsidian-sync -f
```

## Development

All tooling runs via `uv`:

```bash
uv sync                          # install dependencies
uv run ruff check src --fix      # lint
uv run ruff format src           # format
uv run basedpyright src          # type check
uv run yamllint .                # YAML lint
uv run codespell                 # spell check
```

Run the server locally:

```bash
python -m backplane.mcp
```

This starts the private Home Assistant-compatible SSE server on port `8000`.

<!-- backplane:mcp-catalog:start -->
## MCP tools and resources

This section is generated automatically from the registered MCP surface. Run `prek run update-readme-mcp-catalog` to refresh it after changing tools or resources.

**Server:** `Backplane` v0.4.3

### Server instructions

Backplane exposes tools for interacting with the user's personal homelab services — currently their Obsidian vault, with more integrations to follow.

The user is typically speaking through a voice assistant, so keep tool outputs concise — a short confirmation is usually enough.

### Tools

#### `add_to_daily_note`

Add content to a section of the user's Obsidian daily note. Use this when the user wants to capture something into their daily note.

The user's daily-note template defines this section structure (prefer these names verbatim):
- Summary
- Tasks
  - Work
  - Personal
- Journal
- Links
- Tomorrow

If the user explicitly asks for a section not listed above, set `create_section_if_not_exists=true` — this creates the section and is the correct and supported action in that case. Do not decline or ask for clarification; just call the tool with that flag set.

If the section is missing and `create_section_if_not_exists=false` (the default), the call returns the actual sections in today's note so you can either match an existing one or retry with the flag set to true.

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `content` | `string` | yes | — | The text to add to the section. |
| `create_section_if_not_exists` | `boolean` | no | `false` | Set to true to create the section (and any missing ancestors) when it doesn't exist. Set to false (default) to fail with a list of available sections so you can pick the right one. Use true when the user explicitly asks for a new section, or when retrying after a missing-section error and creation is the right resolution. |
| `date` | `date` (YYYY-MM-DD)? | no | `null` | The date of the daily note. Defaults to today's local date. |
| `heading_path` | `string`[] | yes | — | The headings to traverse to the section to update. Pick based on the content and the section structure provided in the tool description. The top-level date heading is added automatically — do not include it. |
| `mode` | `append` \| `prepend` \| `replace` | no | `append` | How to combine `content` with any existing section text. `append` is almost always the right choice for voice capture; use `replace` only when the user explicitly asks to overwrite. |

#### `create_task`

Create a structured task note for something actionable.

Use this when the user mentions something they need to do, want to remember to act on, or asks you to 'make a task', 'add to my list', 'remind me to', 'I should...', 'I need to...', etc.

This tool always creates the task. Matching against prior inbox captures is best-effort only: high-confidence matches are linked automatically, uncertain matches are returned as candidates to offer back to the user, and unmatched tasks are created normally.

When the user confirms a specific prior capture, pass its ID as link_capture_id. For an already-created task, use link_task_to_capture.

Do not use this for loose, non-committal ideas unless the user asks to turn one into a task. Use record_idea for speculative captures like 'maybe', 'I could', 'I wonder if', or 'worth investigating'.

Ask for a due date before calling if the request sounds time-sensitive (e.g. 'before the weekend', 'by Friday', 'i need to...').

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `description` | `string` | yes | — | Natural-language task or action description. This is fuzzy-matched against existing inbox captures, so include distinctive nouns, names, and phrases from the original capture when available. Exact wording is helpful but not required; keep extra context that may help extract task metadata. |
| `due` | `string`? | no | `null` | Optional due date in YYYY-MM-DD format. Ask before setting if timing is implied but not explicit. |
| `link_capture_id` | `string`? | no | `null` | Optional confirmed inbox capture ID to link, e.g. '2026-05-25T21:15'. Omit unless the user explicitly confirmed which candidate capture to attach. |
| `priority` | `low` \| `medium` \| `high`? | no | `null` | Optional priority override: 'low', 'medium', or 'high'. Omit unless the user explicitly indicates urgency or importance. |
| `title` | `string`? | no | `null` | Optional task title override. Omit unless the user supplied a clear title; otherwise inferred from the matched capture or description. |

#### `get_daily_note`

Read the user's Obsidian daily note. Use this when the user asks what's in their daily note, wants to review tasks/ideas/notes they've captured, or needs context about their day to answer a follow-up question.

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `date` | `date` (YYYY-MM-DD)? | no | `null` | The date of the daily note. Defaults to today's local date. |

#### `link_task_to_capture`

Link an existing task note to a confirmed prior inbox capture.

Use this after create_task offered candidate captures and the user confirms which capture should be connected. Provide the task slug from the creation confirmation and the capture ID from the candidate list.

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `capture_id` | `string` | yes | — | Inbox capture ID, e.g. '2026-05-25T21:15'. |
| `task_slug` | `string` | yes | — | Task note slug, e.g. 'review-backup-logs'. |

#### `record_idea`

Record a loose, non-actionable idea in the Obsidian idea inbox.

Use this for speculative captures such as:
- "maybe..."
- "I could..."
- "I wonder if..."
- "worth investigating..."
- a possible automation, improvement, or future project that the user has not committed to doing

Do not use this for tasks or action items. If the user says they need to do something,
should do something, want to remember to act on something, or asks for a task/reminder/list item,
use create_task instead.

Convert spoken phrasing to a written sentence, while preserving the user's original wording as closely
as possible.

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `idea` | `string` | yes | — | The loose, non-actionable idea to record. Preserve the user's wording as closely as possible. |

### Resources

#### `Today's Daily Note`

- **URI:** `obsidian://daily-note/today` (`text/markdown`)
- **Description:** The user's Obsidian daily note for today's date.

### Resource templates

#### `Daily Note by Date`

- **URI template:** `obsidian://daily-note/{date}` (`text/markdown`)
- **Description:** The user's Obsidian daily note for a given ISO date (YYYY-MM-DD), e.g. obsidian://daily-note/2026-05-16.

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `date` | `date` (YYYY-MM-DD) | yes | — |  |
<!-- backplane:mcp-catalog:end -->

### Public MCP (ChatGPT)

Backplane can also run a separate public streamable HTTP MCP server:

```bash
python -m backplane.mcp.public
```

This starts the authenticated public streamable HTTP MCP server on port `8001`.
The MCP OAuth environment variables in `.env.example` are required; the server
refuses to start without them. It uses FastMCP's `OIDCProxy` against Authentik.
See `deploy/authentik-backplane-mcp.env.example` for Authentik provider setup.
Terminate TLS at your reverse proxy (for example NGINX Proxy Manager) and forward
`backplane-mcp.example.com` to port `8001`.

Keep the private SSE server on your LAN only.

#### OAuth scope model (current)

The public MCP server requires authentication for all tools and resources. The
baseline OAuth scope is **`openid`** — there is no `mcp.read` / `mcp.write` split
yet. See the design note in `src/backplane/mcp/auth.py` for the deferred
read/write scope plan.

#### Public route policy (`:8001`)

| Route | Policy |
| --- | --- |
| `POST /mcp` | Bearer token required |
| `/.well-known/oauth-protected-resource/*` | Public |
| FastMCP OAuth routes (`/authorize`, `/token`, `/register`, `/auth/callback`, …) | Public (state/PKCE validated by FastMCP) |

The private SSE server on port `8000` is unauthenticated and must stay on your LAN.

#### Future: `mcp.read` / `mcp.write`

Per-tool read/write scopes may be added later. Before enabling them, verify the
live ChatGPT → FastMCP → Authentik flow and confirm which scopes are requested,
issued, preserved, and visible during tool execution. Do not configure
`mcp.read` or `mcp.write` in Authentik until that mapping is understood.

#### ChatGPT custom connector

Your server already exposes the discovery documents ChatGPT expects:

- `GET /.well-known/oauth-protected-resource/mcp`
- `GET /.well-known/oauth-authorization-server`
- `POST /register` (dynamic client registration)

**In ChatGPT (chat.openai.com):**

1. Enable **Developer mode** (Settings → Apps → Advanced, or equivalent for your plan).
2. **Create** a custom connector / app.
3. **MCP server URL:** `https://backplane-mcp.example.com/mcp` (no trailing spaces).
4. **Authentication:** OAuth with **server discovery** (let ChatGPT discover from the MCP URL).
   Do **not** paste the Authentik `MCP_OIDC_CLIENT_ID` / `MCP_OIDC_CLIENT_SECRET` here — those
   are only for Backplane’s upstream link to Authentik. ChatGPT registers its own client via
   `/register` and signs users in through Backplane → Authentik.
5. Complete the browser login when ChatGPT redirects you (Authentik must allow your user on the
   `backplane-mcp` application).

**Authentik:** upstream redirect URI stays a single fixed callback:

```text
https://backplane-mcp.example.com/auth/callback
```

On the **Backplane MCP** OAuth2/OpenID provider (`Applications` → `Providers` → edit),
include scopes **`openid`** and **`offline_access`**. ChatGPT custom connectors need a
`refresh_token` from the upstream IdP; without `offline_access` in Authentik, OAuth can
succeed in the browser but ChatGPT reports *"There was a problem connecting …"*. See
`deploy/authentik-backplane-mcp.env.example` for the full provider checklist.

ChatGPT redirect patterns (`https://chatgpt.com/connector/oauth/*` and
`https://chatgpt.com/connector_platform_oauth_redirect`) are already allowed by Backplane;
you do not add them in Authentik.

**Plan limits:** Plus / Pro custom connectors are often **read-only**. Tool calls that write to
Obsidian may require Business, Enterprise, or Edu.

**Verify after connecting:** ask ChatGPT to list available tools, or run
`journalctl -u backplane-public -f` while connecting — a healthy flow shows
`/authorize` → `/auth/callback` → `POST /token` **200** (with `refresh_token`), then
`POST /mcp` **200** with a Bearer token.

**If ChatGPT says “There was a problem connecting to Backplane”:** OAuth may succeed in
the browser but `/token` lacks a `refresh_token`. Add **`offline_access`** on the Authentik
provider (see above), delete the connector, and reconnect. Confirm the MCP URL has no
trailing space: `https://backplane-mcp.example.com/mcp`.
