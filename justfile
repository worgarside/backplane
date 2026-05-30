set dotenv-load

# List available recipes
default:
    @just --list

# Restart the MCP server (systemd when installed, otherwise a local background process)
[private]
_mcp-restart:
    #!/usr/bin/env bash
    set -euo pipefail
    if systemctl cat backplane.service &>/dev/null; then
        systemctl restart backplane
        systemctl is-active --quiet backplane
        echo "MCP server restarted via systemd (backplane.service)"
    else
        pkill -f "backplane.mcp" || true
        nohup uv run python -m backplane.mcp >> /tmp/backplane-mcp.log 2>&1 &
        echo "MCP server started (PID $!), logging to /tmp/backplane-mcp.log"
    fi

# Start or restart the MCP server
mcp-start:
    just _mcp-restart

# Stop the MCP server
mcp-stop:
    #!/usr/bin/env bash
    if systemctl cat backplane.service &>/dev/null; then
        systemctl stop backplane
        echo "MCP server stopped (backplane.service)"
    elif pkill -f "backplane.mcp"; then
        echo "MCP server stopped"
    else
        echo "MCP server was not running"
    fi

# Tail MCP server logs
mcp-logs:
    #!/usr/bin/env bash
    if systemctl cat backplane.service &>/dev/null; then
        tail -f /var/log/backplane/backplane.log -n 100
    else
        tail -f /tmp/backplane-mcp.log -n 100
    fi

# Install systemd units, logrotate configs, and service dependencies
setup log_dir="/var/log/backplane":
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "$(id -u)" -eq 0 ]]; then
        env LOG_DIR="{{ log_dir }}" ./scripts/setup.sh
    else
        sudo env LOG_DIR="{{ log_dir }}" ./scripts/setup.sh
    fi

# Checkout a specific tag, sync deps, and restart via systemd — called by CI
deploy tag:
    git fetch --tags origin
    git checkout {{ tag }}
    uv sync --frozen --no-dev
    just _mcp-restart

# Checkout a branch, sync deps, and restart the MCP server
checkout branch="main":
    git fetch origin
    git checkout {{ branch }}
    git pull
    uv sync
    just _mcp-restart

# Pull the current branch, sync deps, and restart the MCP server
pull:
    #!/usr/bin/env bash
    set -euo pipefail
    branch="$(git branch --show-current)"
    if [[ -z "${branch}" ]]; then
        echo "Cannot pull: HEAD is detached"
        exit 1
    fi
    just checkout "${branch}"
