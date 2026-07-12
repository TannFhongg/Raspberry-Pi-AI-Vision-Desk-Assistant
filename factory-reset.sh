#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="/opt/visiondesk/current"
SERVICE_NAME="visiondesk.service"
PYTHON_BIN="${APP_ROOT}/.venv/bin/python"

usage() {
  cat <<'EOF'
Usage:
  sudo ./factory-reset.sh --mode {configuration|user_data|factory_reset} [--remove-wifi] [--yes] [--phrase "ERASE VISIONDESK"] [--dry-run]
EOF
}

log() {
  printf '%s\n' "$*"
}

fail() {
  log "[FAIL] $*"
  exit 1
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    fail "factory-reset.sh must be run as root."
  fi
}

ensure_python() {
  if [[ -x "${PYTHON_BIN}" ]]; then
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
    return 0
  fi
  fail "No usable Python runtime was found."
}

restart_service_if_needed() {
  if [[ ! -f "/etc/systemd/system/${SERVICE_NAME}" ]]; then
    return 0
  fi
  systemctl restart "${SERVICE_NAME}"
}

main() {
  if (($# == 0)); then
    usage
    exit 1
  fi

  case "${1:-}" in
    --help|-h)
      usage
      exit 0
      ;;
  esac

  require_root
  ensure_python
  "${PYTHON_BIN}" -m system.factory_reset "$@"

  for arg in "$@"; do
    if [[ "${arg}" == "--dry-run" ]]; then
      exit 0
    fi
  done

  restart_service_if_needed
  log "[OK] VisionDesk factory reset completed."
}

main "$@"
