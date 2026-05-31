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
`INSTALL_PUBLIC_MCP=true` after configuring the public OAuth environment variables.

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

### ChatGPT MCP Connector

Backplane can also run a separate public streamable HTTP MCP server for ChatGPT:

```bash
python -m backplane.mcp.public
```

This starts the Authentik-protected HTTP server on port `8001`. Keep the private SSE
server reachable only from your LAN, and expose only the public server through HTTPS
at your public MCP hostname, for example `https://backplane-mcp.example.com`.

Create an Authentik OAuth2/OpenID provider for Backplane with redirect URI:

```text
https://backplane-mcp.example.com/auth/callback
```

Set the public MCP environment variables from `.env.example`, confirming the exact
issuer, authorization, token, and JWKS URLs from Authentik's OpenID configuration.
If Authentik issues opaque access tokens, set the introspection endpoint as well
so Backplane can validate tokens with Authentik directly.
Then add the custom MCP connector in ChatGPT using the public MCP URL, typically:

```text
https://backplane-mcp.example.com/mcp
```
