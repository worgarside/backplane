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
    tail -f /tmp/backplane-mcp.log

# Checkout a branch, sync deps, and restart the MCP server
checkout branch:
    git fetch origin
    git checkout {{ branch }}
    uv sync
    just mcp-start
