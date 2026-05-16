#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_NAME="backplane"
SERVICE_USER="${SUDO_USER:-$USER}"
VAULT_DIR="${VAULT_DIR:-/root/obsidian/vaults/my-vault}"
OB_BIN="$(command -v ob || echo /usr/local/bin/ob)"

# Install uv if not present
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Install Python 3.14 + sync dependencies
cd "$INSTALL_DIR"
uv python install 3.14
uv sync --frozen --no-dev

# Install systemd unit (substitute placeholders)
sed \
    -e "s|%%INSTALL_DIR%%|${INSTALL_DIR}|g" \
    -e "s|%%SERVICE_USER%%|${SERVICE_USER}|g" \
    "${INSTALL_DIR}/scripts/backplane.service" \
    >"/etc/systemd/system/${SERVICE_NAME}.service"

# Install obsidian-sync unit (substitute placeholders)
sed \
    -e "s|%%SERVICE_USER%%|${SERVICE_USER}|g" \
    -e "s|%%VAULT_DIR%%|${VAULT_DIR}|g" \
    -e "s|/usr/bin/ob|${OB_BIN}|g" \
    "${INSTALL_DIR}/scripts/obsidian-sync.service" \
    >"/etc/systemd/system/obsidian-sync.service"

systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}"
systemctl enable --now obsidian-sync

echo "Services running:"
echo "  systemctl status ${SERVICE_NAME}"
echo "  systemctl status obsidian-sync"
