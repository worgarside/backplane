#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

git pull
uv sync --frozen --no-dev
sudo systemctl restart backplane

echo "Updated — $(git describe --tags --abbrev=0)"
