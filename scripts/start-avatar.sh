#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="${CONFIG_FILE:-${ROOT_DIR}/examples/avatar.routine.yaml}"
HOST="${HOST:-}"
PORT="${PORT:-}"
LOG_DIR="${LOG_DIR:-${ROOT_DIR}/logs}"
PID_DIR="${PID_DIR:-${ROOT_DIR}/run}"
SERVICE_FILE="/etc/systemd/system/pi-avatar-startup.service"
MONITOR_SERVICE_FILE="/etc/systemd/system/pi-avatar-monitor.service"
WEB_SERVICE_FILE="/etc/systemd/system/pi-avatar-web.service"
RENDERER_SERVICE_FILE="/etc/systemd/system/pi-avatar-renderer.service"
PI_AVATAR_SERVICES="pi-avatar-monitor.service pi-avatar-web.service pi-avatar-renderer.service"
PYTHON_BIN="${PYTHON_BIN:-${ROOT_DIR}/.venv/bin/python}"

if [ ! -x "${PYTHON_BIN}" ]; then
  PYTHON_BIN="$(command -v python3)"
fi

usage() {
  printf 'Usage: %s [--config PATH] [--host HOST] [--port PORT] [--foreground] [--install-service]\n' "$0"
}

resolve_path() {
  case "$1" in
    /*)
      printf '%s\n' "$1"
      ;;
    *)
      printf '%s/%s\n' "$(cd "$(dirname "$1")" && pwd)" "$(basename "$1")"
      ;;
  esac
}

web_arg() {
  if [ -n "$2" ]; then
    printf '%s\n' "$1" "$2"
  fi
}

install_service() {
  if [ "$(id -u)" -ne 0 ]; then
    printf 'Run with sudo to install the startup service.\n' >&2
    exit 1
  fi

  cat > "${MONITOR_SERVICE_FILE}" <<EOF
[Unit]
Description=Pi Avatar monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${ROOT_DIR}
ExecStart=${PYTHON_BIN} ${ROOT_DIR}/monitor.py --config ${CONFIG_FILE}
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

  cat > "${WEB_SERVICE_FILE}" <<EOF
[Unit]
Description=Pi Avatar web renderer
After=network-online.target pi-avatar-monitor.service
Wants=network-online.target pi-avatar-monitor.service

[Service]
Type=simple
WorkingDirectory=${ROOT_DIR}
ExecStart=${PYTHON_BIN} ${ROOT_DIR}/web_preview.py --config ${CONFIG_FILE}
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

  cat > "${RENDERER_SERVICE_FILE}" <<EOF
[Unit]
Description=Pi Avatar renderer
After=local-fs.target

[Service]
Type=simple
Environment=XDG_RUNTIME_DIR=/run/pi-avatar
Environment=SDL_VIDEODRIVER=kmsdrm
WorkingDirectory=${ROOT_DIR}
ExecStartPre=-/usr/bin/timeout 2 /bin/sh -c '/usr/bin/setterm --cursor off --blank 0 --powerdown 0 </dev/tty1 >/dev/tty1'
ExecStart=${PYTHON_BIN} ${ROOT_DIR}/renderer.py --config ${CONFIG_FILE}
ExecStopPost=-/usr/bin/timeout 2 /bin/sh -c '/usr/bin/setterm --cursor on </dev/tty1 >/dev/tty1'
Restart=on-failure
RestartSec=2
TimeoutStartSec=15
RuntimeDirectory=pi-avatar
RuntimeDirectoryMode=0700
StandardInput=tty
TTYPath=/dev/tty1

[Install]
WantedBy=multi-user.target
EOF

  cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Pi Avatar startup
After=network-online.target local-fs.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/systemctl start pi-avatar-monitor.service pi-avatar-web.service
ExecStart=/usr/bin/systemctl start --no-block pi-avatar-renderer.service
ExecStop=/usr/bin/systemctl stop pi-avatar-renderer.service pi-avatar-web.service pi-avatar-monitor.service

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload >/dev/null
  systemctl enable pi-avatar-startup.service >/dev/null
  systemctl enable ${PI_AVATAR_SERVICES} >/dev/null
  systemctl restart pi-avatar-startup.service >/dev/null
}

stop_existing() {
  mkdir -p "${PID_DIR}"
  for name in monitor web renderer; do
    pid_file="${PID_DIR}/${name}.pid"
    if [ ! -f "${pid_file}" ]; then
      continue
    fi
    pid="$(cat "${pid_file}" 2>/dev/null || true)"
    if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
      for _ in 1 2 3 4 5 6 7 8 9 10; do
        kill -0 "${pid}" 2>/dev/null || break
        sleep 0.2
      done
    fi
    rm -f "${pid_file}"
  done
}

record_pid() {
  printf '%s\n' "$2" > "${PID_DIR}/$1.pid"
}

start_logged() {
  name="$1"
  shift
  "$@" >"${LOG_DIR}/${name}.log" 2>&1 </dev/null &
  record_pid "${name}" "$!"
}

cleanup() {
  stop_existing
  wait 2>/dev/null || true
}

prepare_runtime() {
  mkdir -p "${LOG_DIR}" "${PID_DIR}"
  cd "${ROOT_DIR}"
  stop_existing
}

start_foreground() {
  prepare_runtime
  trap cleanup EXIT INT TERM
  start_logged monitor "${PYTHON_BIN}" "${ROOT_DIR}/monitor.py" --config "${CONFIG_FILE}"
  start_logged web "${PYTHON_BIN}" "${ROOT_DIR}/web_preview.py" --config "${CONFIG_FILE}" $(web_arg --host "${HOST}") $(web_arg --port "${PORT}")
  start_logged renderer "${PYTHON_BIN}" "${ROOT_DIR}/renderer.py" --config "${CONFIG_FILE}"

  while true; do
    for name in monitor web; do
      pid="$(cat "${PID_DIR}/${name}.pid" 2>/dev/null || true)"
      if [ -z "${pid}" ] || ! kill -0 "${pid}" 2>/dev/null; then
        return 1
      fi
    done
    sleep 2
  done
}

start_quiet() {
  prepare_runtime
  nohup "${PYTHON_BIN}" "${ROOT_DIR}/monitor.py" --config "${CONFIG_FILE}" >"${LOG_DIR}/monitor.log" 2>&1 </dev/null &
  record_pid monitor "$!"
  nohup "${PYTHON_BIN}" "${ROOT_DIR}/web_preview.py" --config "${CONFIG_FILE}" $(web_arg --host "${HOST}") $(web_arg --port "${PORT}") >"${LOG_DIR}/web.log" 2>&1 </dev/null &
  record_pid web "$!"
  nohup "${PYTHON_BIN}" "${ROOT_DIR}/renderer.py" --config "${CONFIG_FILE}" >"${LOG_DIR}/renderer.log" 2>&1 </dev/null &
  record_pid renderer "$!"
}

foreground=0
install=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --config)
      CONFIG_FILE="$2"
      shift 2
      ;;
    --host)
      HOST="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --foreground)
      foreground=1
      shift
      ;;
    --install-service)
      install=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

CONFIG_FILE="$(resolve_path "${CONFIG_FILE}")"

if [ "${install}" -eq 1 ]; then
  install_service
  exit 0
fi

if [ "${foreground}" -eq 1 ]; then
  start_foreground
else
  start_quiet
fi
