#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this installer with sudo." >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="/opt/pi-avatar"
CONFIG_DIR="/etc/pi-avatar"
STATE_DIR="/var/lib/pi-avatar"
ENV_FILE="${CONFIG_DIR}/avatar.env"
CONFIG_FILE="${CONFIG_DIR}/avatar.yaml"
VENV_DIR="${INSTALL_DIR}/.venv"

mkdir -p "${INSTALL_DIR}" "${CONFIG_DIR}" "${STATE_DIR}"

cp -a "${ROOT_DIR}/pi_avatar" "${INSTALL_DIR}/"
cp -a "${ROOT_DIR}/assets" "${INSTALL_DIR}/"
cp "${ROOT_DIR}/monitor.py" "${ROOT_DIR}/renderer.py" "${ROOT_DIR}/web_preview.py" "${ROOT_DIR}/process_assets.py" "${ROOT_DIR}/validate_config.py" "${ROOT_DIR}/make_test_assets.py" "${ROOT_DIR}/requirements.txt" "${INSTALL_DIR}/"

if ! python3 -m venv "${VENV_DIR}"; then
  if command -v apt-get >/dev/null 2>&1; then
    echo "python3 venv support is unavailable; installing python3-venv with apt."
    apt-get update
    apt-get install -y python3-venv
    rm -rf "${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
  else
    echo "Could not create ${VENV_DIR}. Install Python venv support, then rerun this installer." >&2
    exit 1
  fi
fi

"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r "${INSTALL_DIR}/requirements.txt"

if [ ! -f "${ENV_FILE}" ]; then
  cat > "${ENV_FILE}" <<'EOF'
CONFIG_FILE=/etc/pi-avatar/avatar.yaml
EOF
fi

if [ ! -f "${CONFIG_FILE}" ]; then
  cat > "${CONFIG_FILE}" <<'EOF'
avatar:
  state_file: /var/lib/pi-avatar/state.json
  asset_dir: /opt/pi-avatar/assets
  default_state: idle
  states: [booting, idle, thinking, working, success, error, offline]

source:
  type: none

mode:
  type: routine
  strategy: sequence
  steps:
    - state: idle
      duration_seconds: 10
    - state: thinking
      duration_seconds: 4
EOF
fi

cp "${ROOT_DIR}/systemd/pi-avatar-monitor.service" /etc/systemd/system/
cp "${ROOT_DIR}/systemd/pi-avatar-renderer.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable pi-avatar-monitor.service pi-avatar-renderer.service

echo "Installed Pi Avatar. Edit ${CONFIG_FILE}, then run:"
echo "  sudo systemctl restart pi-avatar-monitor pi-avatar-renderer"
