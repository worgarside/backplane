#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_NAME="backplane"
SERVICE_USER="${SUDO_USER:-$USER}"
LOG_DIR="${LOG_DIR:-/var/log/backplane}"
VAULT_DIR="${VAULT_DIR:-/root/obsidian/vaults/my-vault}"
OB_BIN="$(command -v ob || echo /usr/local/bin/ob)"

# Install uv if not present
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
UV_BIN="$(command -v uv 2>/dev/null || echo "$HOME/.local/bin/uv")"

# Install Python 3.14 + sync dependencies
cd "$INSTALL_DIR"
"$UV_BIN" python install 3.14
"$UV_BIN" sync --frozen --no-dev

install -d -o "${SERVICE_USER}" -m 0755 "${LOG_DIR}"

# Install systemd unit (substitute placeholders)
sed \
    -e "s|%%INSTALL_DIR%%|${INSTALL_DIR}|g" \
    -e "s|%%SERVICE_USER%%|${SERVICE_USER}|g" \
    -e "s|%%LOG_DIR%%|${LOG_DIR}|g" \
    "${INSTALL_DIR}/scripts/backplane.service.tmpl" \
    >"/etc/systemd/system/${SERVICE_NAME}.service"

# Install obsidian-sync unit (substitute placeholders)
sed \
    -e "s|%%INSTALL_DIR%%|${INSTALL_DIR}|g" \
    -e "s|%%SERVICE_USER%%|${SERVICE_USER}|g" \
    -e "s|%%LOG_DIR%%|${LOG_DIR}|g" \
    -e "s|%%VAULT_DIR%%|${VAULT_DIR}|g" \
    -e "s|/usr/bin/ob|${OB_BIN}|g" \
    "${INSTALL_DIR}/scripts/obsidian-sync.service.tmpl" \
    >"/etc/systemd/system/obsidian-sync.service"

# Install logrotate configs
sed \
    -e "s|%%LOG_DIR%%|${LOG_DIR}|g" \
    "${INSTALL_DIR}/scripts/backplane.logrotate.tmpl" \
    >"/etc/logrotate.d/${SERVICE_NAME}"
sed \
    -e "s|%%LOG_DIR%%|${LOG_DIR}|g" \
    "${INSTALL_DIR}/scripts/obsidian-sync.logrotate.tmpl" \
    >"/etc/logrotate.d/obsidian-sync"

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"
systemctl enable obsidian-sync
systemctl restart obsidian-sync

echo "Services running:"
echo "  systemctl status ${SERVICE_NAME}"
echo "  systemctl status obsidian-sync"
