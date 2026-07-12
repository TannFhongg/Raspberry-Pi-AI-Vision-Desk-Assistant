#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="${VISIONDESK_APP_DIR:-/opt/visiondesk/current}"
APP_USER="${VISIONDESK_APP_USER:-visiondesk}"
WAIT_SECONDS="${VISIONDESK_SESSION_WAIT_SECONDS:-90}"
PYTHON_BIN="${APP_ROOT}/.venv/bin/python"

log() {
  printf '[visiondesk-launch] %s\n' "$*"
}

ensure_runtime_dir() {
  local user_uid
  user_uid="$(id -u "${APP_USER}")"
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/${user_uid}}"
}

configure_display_environment() {
  ensure_runtime_dir

  if [[ -z "${WAYLAND_DISPLAY:-}" ]]; then
    if [[ -S "${XDG_RUNTIME_DIR}/wayland-0" ]]; then
      export WAYLAND_DISPLAY="wayland-0"
    elif [[ -S "${XDG_RUNTIME_DIR}/wayland-1" ]]; then
      export WAYLAND_DISPLAY="wayland-1"
    fi
  fi

  if [[ -z "${DISPLAY:-}" ]] && [[ -S /tmp/.X11-unix/X0 ]]; then
    export DISPLAY=":0"
  fi

  if [[ -z "${XAUTHORITY:-}" ]]; then
    local user_home
    user_home="$(getent passwd "${APP_USER}" | cut -d: -f6)"
    if [[ -n "${user_home}" && -f "${user_home}/.Xauthority" ]]; then
      export XAUTHORITY="${user_home}/.Xauthority"
    fi
  fi

  if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
    export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland}"
    return 0
  fi

  if [[ -n "${DISPLAY:-}" ]]; then
    export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
    return 0
  fi

  return 1
}

wait_for_session() {
  local waited=0
  until configure_display_environment; do
    if (( waited >= WAIT_SECONDS )); then
      log "Timed out waiting for a graphical session."
      return 1
    fi
    sleep 1
    waited=$((waited + 1))
  done
  return 0
}

main() {
  if [[ ! -x "${PYTHON_BIN}" ]]; then
    log "Python runtime is missing: ${PYTHON_BIN}"
    return 1
  fi

  wait_for_session
  log "Launching VisionDesk with QT_QPA_PLATFORM=${QT_QPA_PLATFORM:-unset}"
  exec "${PYTHON_BIN}" -m qt_app.main
}

main "$@"
