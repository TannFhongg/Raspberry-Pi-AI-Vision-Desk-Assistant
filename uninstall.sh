#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="/opt/visiondesk"
RELEASES_DIR="${APP_ROOT}/releases"
CURRENT_LINK="${APP_ROOT}/current"
CONFIG_DIR="/etc/visiondesk"
DATA_DIR="/var/lib/visiondesk"
LOG_DIR="/var/log/visiondesk"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_NAME="visiondesk.service"
SYSTEMD_UNIT="${SYSTEMD_DIR}/${SERVICE_NAME}"
POLKIT_RULE="/etc/polkit-1/rules.d/49-visiondesk-networkmanager.rules"
LIGHTDM_CONF="/etc/lightdm/lightdm.conf.d/99-visiondesk.conf"
LEGACY_UNITS=(
  "${SYSTEMD_DIR}/visiondesk-qt.service"
  "${SYSTEMD_DIR}/ai-vision-assistant.service"
  "${SYSTEMD_DIR}/visiondesk-browser.service"
)
AUTOSTART_LEFTOVERS=(
  "/etc/xdg/autostart/visiondesk.desktop"
  "/home/visiondesk/.config/autostart/visiondesk.desktop"
)

PURGE=0
KEEP_LOGS=0
YES=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage:
  sudo ./uninstall.sh [--purge] [--keep-logs] [--yes] [--dry-run]
EOF
}

log() {
  printf '%s\n' "$*"
}

fail() {
  log "[FAIL] $*"
  exit 1
}

resolve_path() {
  python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$1"
}

ensure_path_within() {
  local base_path="$1"
  local target_path="$2"
  local resolved_base resolved_target
  resolved_base="$(resolve_path "${base_path}")"
  resolved_target="$(resolve_path "${target_path}")"
  case "${resolved_target}" in
    "${resolved_base}"|"${resolved_base}"/*)
      return 0
      ;;
    *)
      fail "Refusing to operate on path outside ${resolved_base}: ${resolved_target}"
      ;;
  esac
}

safe_remove_tree() {
  local target_path="$1"
  local allowed_root="$2"
  [[ -n "${target_path}" ]] || fail "Refusing to remove an empty path."
  if [[ ! -e "${target_path}" && ! -L "${target_path}" ]]; then
    return 0
  fi
  ensure_path_within "${allowed_root}" "${target_path}"
  rm -rf -- "${target_path}"
}

safe_remove_file() {
  local target_path="$1"
  local allowed_root="$2"
  [[ -n "${target_path}" ]] || fail "Refusing to remove an empty path."
  if [[ ! -e "${target_path}" && ! -L "${target_path}" ]]; then
    return 0
  fi
  ensure_path_within "${allowed_root}" "${target_path}"
  rm -f -- "${target_path}"
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    fail "uninstall.sh must be run as root."
  fi
}

parse_args() {
  while (($# > 0)); do
    case "$1" in
      --purge)
        PURGE=1
        ;;
      --keep-logs)
        KEEP_LOGS=1
        ;;
      --yes)
        YES=1
        ;;
      --dry-run)
        DRY_RUN=1
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        fail "Unknown option: $1"
        ;;
    esac
    shift
  done
}

confirm_uninstall() {
  if (( YES == 1 )); then
    return 0
  fi
  if (( PURGE == 1 )); then
    log "[WARN] Purge will permanently delete:"
    log "  ${CONFIG_DIR}"
    log "  ${DATA_DIR}"
    if (( KEEP_LOGS == 0 )); then
      log "  ${LOG_DIR}"
    fi
    local confirmation
    read -r -p "Type PURGE VISIONDESK to continue: " confirmation
    [[ "${confirmation}" == "PURGE VISIONDESK" ]] || fail "Purge cancelled."
    return 0
  fi
  local confirmation
  read -r -p "Type REMOVE to uninstall VisionDesk and preserve config/data/logs: " confirmation
  [[ "${confirmation}" == "REMOVE" ]] || fail "Uninstall cancelled."
}

print_plan() {
  log "[INFO] VisionDesk uninstall plan"
  log "[INFO] Remove app/service:"
  log "  ${APP_ROOT}"
  log "  ${SYSTEMD_UNIT}"
  log "  ${POLKIT_RULE}"
  log "  ${LIGHTDM_CONF}"
  if (( PURGE == 1 )); then
    log "[INFO] Purge persistent data:"
    log "  ${CONFIG_DIR}"
    log "  ${DATA_DIR}"
    if (( KEEP_LOGS == 0 )); then
      log "  ${LOG_DIR}"
    else
      log "[INFO] Preserve logs: ${LOG_DIR}"
    fi
  else
    log "[INFO] Preserve persistent data:"
    log "  ${CONFIG_DIR}"
    log "  ${DATA_DIR}"
    log "  ${LOG_DIR}"
  fi
}

stop_and_disable_service() {
  systemctl disable --now "${SERVICE_NAME}" >/dev/null 2>&1 || true
  local legacy_unit
  for legacy_unit in "${LEGACY_UNITS[@]}"; do
    if [[ -f "${legacy_unit}" ]]; then
      systemctl disable --now "$(basename "${legacy_unit}")" >/dev/null 2>&1 || true
    fi
  done
}

remove_service_and_app() {
  safe_remove_file "${SYSTEMD_UNIT}" "${SYSTEMD_DIR}"
  safe_remove_file "${POLKIT_RULE}" "/etc/polkit-1/rules.d"
  local legacy_unit
  for legacy_unit in "${LEGACY_UNITS[@]}"; do
    safe_remove_file "${legacy_unit}" "${SYSTEMD_DIR}"
  done
  safe_remove_file "${LIGHTDM_CONF}" "/etc/lightdm"
  local autostart_file
  for autostart_file in "${AUTOSTART_LEFTOVERS[@]}"; do
    safe_remove_file "${autostart_file}" "$(dirname "${autostart_file}")"
  done
  safe_remove_tree "${APP_ROOT}" "/opt"
  systemctl daemon-reload
}

remove_persistent_data() {
  safe_remove_tree "${CONFIG_DIR}" "/etc"
  safe_remove_tree "${DATA_DIR}" "/var/lib"
  if (( KEEP_LOGS == 0 )); then
    safe_remove_tree "${LOG_DIR}" "/var/log"
  fi
}

main() {
  parse_args "$@"
  require_root
  print_plan

  if (( DRY_RUN == 1 )); then
    log "[OK] Dry run complete. No files were removed."
    exit 0
  fi

  confirm_uninstall
  stop_and_disable_service
  remove_service_and_app
  if (( PURGE == 1 )); then
    remove_persistent_data
  fi

  log "[OK] VisionDesk uninstalled."
  if (( PURGE == 0 )); then
    log "[OK] Preserved: ${CONFIG_DIR} ${DATA_DIR} ${LOG_DIR}"
  elif (( KEEP_LOGS == 1 )); then
    log "[OK] Preserved logs: ${LOG_DIR}"
  fi
}

main "$@"
