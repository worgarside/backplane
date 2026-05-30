set dotenv-load

# List available recipes
default:
    @just --list

# Start the MCP server (background, logs to /tmp/backplane-mcp.log)
mcp-start:
    #!/usr/bin/env bash
    pkill -f "backplane.mcp" || true
    nohup uv run python -m backplane.mcp >> /tmp/backplane-mcp.log 2>&1 &
    echo "MCP server started (PID $!), logging to /tmp/backplane-mcp.log"

# Stop the MCP server
mcp-stop:
    pkill -f "backplane.mcp" && echo "MCP server stopped" || echo "MCP server was not running"

# Tail MCP server logs
mcp-logs:
    tail -f /tmp/backplane-mcp.log -n 100

# Install systemd units, logrotate configs, and service dependencies
setup log_dir="/var/log/backplane":
    sudo env LOG_DIR="{{ log_dir }}" ./scripts/setup.sh

# Checkout a specific tag, sync deps, and restart via systemd — called by CI
deploy tag:
    git fetch --tags origin
    git checkout {{ tag }}
    uv sync --frozen --no-dev
    systemctl restart backplane
    systemctl is-active --quiet backplane

# Checkout a branch, sync deps, and restart the MCP server
checkout branch="main":
    git fetch origin
    git checkout {{ branch }}
    git pull
    uv sync
    just mcp-start
