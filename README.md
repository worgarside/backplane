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

### 3. Set up Obsidian Sync

Authenticate and do an initial sync before starting the service:

```bash
ob login
ob sync --vault "My Vault" /path/to/vault
```

By default `setup.sh` expects the vault at `/root/obsidian/vaults/my-vault`. Override with the `VAULT_DIR` environment variable if your path differs.

### 4. Run setup

```bash
sudo VAULT_DIR=/path/to/vault bash scripts/setup.sh
```

This will:

- Install [uv](https://docs.astral.sh/uv/) if not present
- Install Python 3.14 and sync dependencies
- Install and enable the `backplane` and `obsidian-sync` systemd services

To also enable the public ChatGPT-facing MCP service, run setup with
`INSTALL_PUBLIC_MCP=true`.

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

### Public MCP (ChatGPT)

Backplane can also run a separate public streamable HTTP MCP server:

```bash
python -m backplane.mcp.public
```

This starts the authenticated public streamable HTTP MCP server on port `8001`.
The MCP OAuth environment variables in `.env.example` are required; the server
refuses to start without them. It uses FastMCP's `OIDCProxy` against Authentik.
See `scripts/authentik-backplane-mcp.env.example` for Authentik provider setup.
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

**Authentik (unchanged from MCP Inspector):** upstream redirect URI stays a single fixed callback:

```text
https://backplane-mcp.example.com/auth/callback
```

ChatGPT redirect patterns (`https://chatgpt.com/connector/oauth/*` and
`https://chatgpt.com/connector_platform_oauth_redirect`) are already allowed by Backplane;
you do not add them in Authentik.

**Plan limits:** Plus / Pro custom connectors are often **read-only**. Tool calls that write to
Obsidian may require Business, Enterprise, or Edu.

**Verify after connecting:** ask ChatGPT to list available tools, or run
`journalctl -u backplane-public -f` while connecting — a healthy flow shows
`/authorize` → `/auth/callback` → `POST /token` **200**, then `POST /mcp` **200** with a Bearer
token (not 401 “missing Authorization header”).

**If ChatGPT says “There was a problem connecting to Backplane”:** check server logs.
A common failure (fixed in current `public.py`) was ChatGPT probing `GET /mcp` while the
server ran in stateless mode (`405 Method Not Allowed`). The public server now uses
session-based Streamable HTTP with `json_response=True` so `GET /mcp` returns a proper
`401` + `WWW-Authenticate` challenge instead. If OAuth completes but the next `POST /mcp`
has no `Authorization` header, delete the connector in ChatGPT and create it again — that
pattern is on OpenAI’s side after a successful `/token` response.
