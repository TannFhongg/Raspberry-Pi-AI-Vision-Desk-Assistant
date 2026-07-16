#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="visiondesk"
APP_USER="visiondesk"
APP_GROUP="visiondesk"
PYTHON_BIN="${PYTHON_BIN:-python3}"
APP_ROOT="/opt/visiondesk"
RELEASES_DIR="${APP_ROOT}/releases"
CURRENT_LINK="${APP_ROOT}/current"
CONFIG_DIR="/etc/visiondesk"
CONFIG_FILE="${CONFIG_DIR}/device.yaml"
ENV_FILE="${CONFIG_DIR}/visiondesk.env"
DATA_DIR="/var/lib/visiondesk"
LOG_DIR="/var/log/visiondesk"
UPDATE_LOG="${LOG_DIR}/update.log"
SYSTEMD_UNIT="/etc/systemd/system/visiondesk.service"
SERVICE_NAME="visiondesk.service"
LOCK_DIR="${DATA_DIR}/update.lock"
ROLLBACK_STATE="${DATA_DIR}/update-rollback.env"
RUNTIME_DIR="${DATA_DIR}/runtime"
READINESS_FILE="${RUNTIME_DIR}/readiness.json"
UPDATE_STARTUP_TIMEOUT_SECONDS="${UPDATE_STARTUP_TIMEOUT_SECONDS:-60}"
UPDATE_STABILITY_SECONDS="${UPDATE_STABILITY_SECONDS:-20}"
READINESS_MAX_AGE_SECONDS="${READINESS_MAX_AGE_SECONDS:-0}"

CHECK_ONLY=0
ROLLBACK_ONLY=0
DRY_RUN=0
ARCHIVE_PATH=""
REQUESTED_VERSION=""
PREVIOUS_CURRENT_TARGET=""
FINAL_RELEASE_DIR=""
STAGING_PARENT=""
STAGING_RELEASE_DIR=""
PREVIOUS_FINAL_RELEASE_BACKUP=""
INSTALL_CHANGED_CURRENT=0

usage() {
  cat <<'EOF'
Usage:
  sudo ./update.sh --check
  sudo ./update.sh --local /path/to/archive.tar.gz [--version <version>] [--dry-run]
  sudo ./update.sh --rollback
EOF
}

python_compatible_path() {
  # The appliance runs Linux paths directly. During package verification from
  # Git Bash/Cygwin, however, python3 can be a native Windows interpreter and
  # cannot open a /tmp or /cygdrive path embedded by the shell.
  local path="$1"
  case "$(uname -s 2>/dev/null || true)" in
    MINGW*|MSYS*|CYGWIN*)
      if command -v cygpath >/dev/null 2>&1; then
        cygpath -w "${path}"
        return
      fi
      ;;
  esac
  printf '%s\n' "${path}"
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
  ensure_path_within "${allowed_root}" "${target_path}"
  rm -rf -- "${target_path}"
}

switch_current_release() {
  local target_release="$1"
  local temporary_link="${CURRENT_LINK}.new.$$"
  ensure_path_within "${RELEASES_DIR}" "${target_release}"
  rm -f -- "${temporary_link}"
  ln -s "${target_release}" "${temporary_link}"
  mv -Tf "${temporary_link}" "${CURRENT_LINK}"
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    fail "update.sh must be run as root."
  fi
}

ensure_logging() {
  mkdir -p "${LOG_DIR}"
  touch "${UPDATE_LOG}"
  chmod 640 "${UPDATE_LOG}"
  exec > >(tee -a "${UPDATE_LOG}") 2>&1
}

parse_args() {
  while (($# > 0)); do
    case "$1" in
      --check)
        CHECK_ONLY=1
        ;;
      --rollback)
        ROLLBACK_ONLY=1
        ;;
      --dry-run)
        DRY_RUN=1
        ;;
      --local)
        shift
        (($# > 0)) || fail "--local requires an archive path."
        ARCHIVE_PATH="$1"
        ;;
      --version)
        shift
        (($# > 0)) || fail "--version requires a value."
        REQUESTED_VERSION="$1"
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

  local mode_count=0
  (( CHECK_ONLY == 1 )) && mode_count=$((mode_count + 1))
  (( ROLLBACK_ONLY == 1 )) && mode_count=$((mode_count + 1))
  [[ -n "${ARCHIVE_PATH}" ]] && mode_count=$((mode_count + 1))
  (( mode_count == 1 )) || fail "Choose exactly one mode: --check, --rollback, or --local <archive>."
}

validate_timeout_configuration() {
  [[ "${UPDATE_STARTUP_TIMEOUT_SECONDS}" =~ ^[1-9][0-9]*$ ]] \
    || fail "UPDATE_STARTUP_TIMEOUT_SECONDS must be a positive integer."
  [[ "${UPDATE_STABILITY_SECONDS}" =~ ^[1-9][0-9]*$ ]] \
    || fail "UPDATE_STABILITY_SECONDS must be a positive integer."
  if [[ "${READINESS_MAX_AGE_SECONDS}" == "0" ]]; then
    READINESS_MAX_AGE_SECONDS=$((UPDATE_STARTUP_TIMEOUT_SECONDS + UPDATE_STABILITY_SECONDS + 30))
  fi
  [[ "${READINESS_MAX_AGE_SECONDS}" =~ ^[1-9][0-9]*$ ]] \
    || fail "READINESS_MAX_AGE_SECONDS must be a positive integer."
}

acquire_lock() {
  mkdir -p "${DATA_DIR}"
  if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
    fail "Another VisionDesk update is already in progress."
  fi
}

release_lock() {
  if [[ -d "${LOCK_DIR}" ]]; then
    safe_remove_tree "${LOCK_DIR}" "${DATA_DIR}"
  fi
}

require_existing_install() {
  [[ -L "${CURRENT_LINK}" ]] || fail "Current release link is missing: ${CURRENT_LINK}"
  [[ -f "${SYSTEMD_UNIT}" ]] || fail "VisionDesk systemd unit is missing: ${SYSTEMD_UNIT}"
  [[ -f "${ENV_FILE}" ]] || fail "VisionDesk environment file is missing: ${ENV_FILE}"
  [[ -f "${CONFIG_FILE}" ]] || fail "VisionDesk device config is missing: ${CONFIG_FILE}"
}

select_requirements_file() {
  local release_dir="$1"
  if [[ -f "${release_dir}/requirements.lock" ]]; then
    printf '%s\n' "${release_dir}/requirements.lock"
  else
    printf '%s\n' "${release_dir}/requirements.txt"
  fi
}

read_release_version() {
  local release_dir="$1"
  local python_release_dir
  python_release_dir="$(python_compatible_path "${release_dir}")"
  "${PYTHON_BIN}" - "${python_release_dir}" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from visiondesk.version import __version__
print(__version__)
PY
}

print_check_report() {
  local current_target current_version
  require_existing_install
  current_target="$(readlink -f "${CURRENT_LINK}")"
  current_version="$(read_release_version "${current_target}")"
  log "[INFO] Installed version: ${current_version}"
  log "[INFO] Current release: ${current_target}"
  log "[INFO] Config file: ${CONFIG_FILE}"
  log "[INFO] Data directory: ${DATA_DIR}"
  log "[INFO] Log directory: ${LOG_DIR}"
  if systemctl is-active --quiet "${SERVICE_NAME}"; then
    log "[OK] ${SERVICE_NAME} is active."
  else
    log "[WARN] ${SERVICE_NAME} is not active."
  fi
}

detect_release_root() {
  local extracted_dir="$1"
  if [[ -f "${extracted_dir}/visiondesk/version.py" ]]; then
    printf '%s\n' "${extracted_dir}"
    return 0
  fi

  local child
  child="$(find "${extracted_dir}" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  if [[ -n "${child}" && -f "${child}/visiondesk/version.py" ]]; then
    printf '%s\n' "${child}"
    return 0
  fi

  fail "Archive does not contain a VisionDesk release root with visiondesk/version.py."
}

extract_archive() {
  [[ -f "${ARCHIVE_PATH}" ]] || fail "Archive not found: ${ARCHIVE_PATH}"
  STAGING_PARENT="${RELEASES_DIR}/.update-staging-$$"
  mkdir -p "${STAGING_PARENT}"
  tar -xf "${ARCHIVE_PATH}" -C "${STAGING_PARENT}"
  STAGING_RELEASE_DIR="$(detect_release_root "${STAGING_PARENT}")"
}

validate_manifest_and_checksums() {
  local manifest_path python_manifest_path manifest_version checksums_rel checksums_path release_version
  manifest_path="${STAGING_RELEASE_DIR}/manifest.json"
  [[ -f "${manifest_path}" ]] || fail "Archive is missing manifest.json."
  python_manifest_path="$(python_compatible_path "${manifest_path}")"

  manifest_version="$("${PYTHON_BIN}" - "${python_manifest_path}" <<'PY'
import json
import sys
from pathlib import Path
manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
version = str(manifest.get("version", "")).strip()
checksums_file = str(manifest.get("checksums_file", "checksums.sha256")).strip() or "checksums.sha256"
if not version:
    raise SystemExit("manifest.json is missing 'version'.")
print(version)
print(checksums_file)
PY
)"
  REQUESTED_VERSION="${REQUESTED_VERSION:-$(printf '%s\n' "${manifest_version}" | sed -n '1p')}"
  checksums_rel="$(printf '%s\n' "${manifest_version}" | sed -n '2p')"
  manifest_version="$(printf '%s\n' "${manifest_version}" | sed -n '1p')"
  [[ -n "${REQUESTED_VERSION}" ]] || fail "Could not determine target version."
  [[ "${REQUESTED_VERSION}" == "${manifest_version}" ]] || fail "Requested version ${REQUESTED_VERSION} does not match manifest version ${manifest_version}."

  checksums_path="${STAGING_RELEASE_DIR}/${checksums_rel}"
  [[ -f "${checksums_path}" ]] || fail "Archive is missing checksum file: ${checksums_path}"
  (
    cd "${STAGING_RELEASE_DIR}"
    sha256sum -c "${checksums_rel}"
  )

  release_version="$(read_release_version "${STAGING_RELEASE_DIR}")"
  [[ "${release_version}" == "${REQUESTED_VERSION}" ]] || fail "Release code version ${release_version} does not match manifest version ${REQUESTED_VERSION}."
  FINAL_RELEASE_DIR="${RELEASES_DIR}/${REQUESTED_VERSION}"
}

validate_release_shape() {
  local required_paths=(
    "${STAGING_RELEASE_DIR}/qt_app/main.py"
    "${STAGING_RELEASE_DIR}/deployment/visiondesk-launch.sh"
    "${STAGING_RELEASE_DIR}/deployment/visiondesk.service"
  )
  local path
  for path in "${required_paths[@]}"; do
    [[ -e "${path}" ]] || fail "Release is missing required file: ${path}"
  done
  [[ -f "${STAGING_RELEASE_DIR}/requirements.txt" || -f "${STAGING_RELEASE_DIR}/requirements.lock" ]] \
    || fail "Release is missing requirements.txt or requirements.lock."

  "${PYTHON_BIN}" -m compileall -q \
    "${STAGING_RELEASE_DIR}/ai" \
    "${STAGING_RELEASE_DIR}/camera" \
    "${STAGING_RELEASE_DIR}/config" \
    "${STAGING_RELEASE_DIR}/gpio" \
    "${STAGING_RELEASE_DIR}/hardware" \
    "${STAGING_RELEASE_DIR}/pipeline" \
    "${STAGING_RELEASE_DIR}/qt_app" \
    "${STAGING_RELEASE_DIR}/system" \
    "${STAGING_RELEASE_DIR}/vision" \
    "${STAGING_RELEASE_DIR}/visiondesk"
}

build_release_environment() {
  local requirements_file
  requirements_file="$(select_requirements_file "${STAGING_RELEASE_DIR}")"
  python3 -m venv --system-site-packages "${STAGING_RELEASE_DIR}/.venv"
  "${STAGING_RELEASE_DIR}/.venv/bin/pip" install --upgrade pip setuptools wheel
  "${STAGING_RELEASE_DIR}/.venv/bin/pip" install --no-cache-dir -r "${requirements_file}"
  chmod 755 "${STAGING_RELEASE_DIR}/deployment/visiondesk-launch.sh"
  chown -R "${APP_USER}:${APP_GROUP}" "${STAGING_RELEASE_DIR}"
}

run_release_checks() {
  (
    cd "${STAGING_RELEASE_DIR}"
    runuser -u "${APP_USER}" -- env \
      VISIONDESK_PATH_MODE=production \
      VISIONDESK_APP_DIR="${STAGING_RELEASE_DIR}" \
      VISIONDESK_RELEASES_DIR="${RELEASES_DIR}" \
      VISIONDESK_ENV_FILE="${ENV_FILE}" \
      VISIONDESK_DATA_DIR="${DATA_DIR}" \
      VISIONDESK_LOG_DIR="${LOG_DIR}" \
      DEVICE_CONFIG_PATH="${CONFIG_FILE}" \
      "${STAGING_RELEASE_DIR}/.venv/bin/python" -m system.migrations

    runuser -u "${APP_USER}" -- env \
      VISIONDESK_PATH_MODE=production \
      VISIONDESK_APP_DIR="${STAGING_RELEASE_DIR}" \
      VISIONDESK_RELEASES_DIR="${RELEASES_DIR}" \
      VISIONDESK_ENV_FILE="${ENV_FILE}" \
      VISIONDESK_DATA_DIR="${DATA_DIR}" \
      VISIONDESK_LOG_DIR="${LOG_DIR}" \
      DEVICE_CONFIG_PATH="${CONFIG_FILE}" \
      "${STAGING_RELEASE_DIR}/.venv/bin/python" -m system.diagnostics
  )
}

write_rollback_state() {
  local previous_release="$1"
  local current_release="$2"
  cat > "${ROLLBACK_STATE}" <<EOF
PREVIOUS_RELEASE=${previous_release}
CURRENT_RELEASE=${current_release}
UPDATED_AT=$(date -Iseconds)
EOF
  chmod 600 "${ROLLBACK_STATE}"
}

clear_readiness_marker() {
  rm -f -- "${READINESS_FILE}"
}

service_property() {
  local property_name="$1"
  systemctl show "${SERVICE_NAME}" --property="${property_name}" --value 2>/dev/null | tr -d '\n'
}

validate_readiness_marker() {
  local expected_version="$1"
  local expected_pid="$2"
  python3 - "${READINESS_FILE}" "${expected_version}" "${expected_pid}" "${READINESS_MAX_AGE_SECONDS}" <<'PY'
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

marker_path = Path(sys.argv[1])
expected_version = sys.argv[2]
expected_pid = int(sys.argv[3])
max_age_seconds = float(sys.argv[4])
accepted_states = {"SETUP_REQUIRED", "READY", "HOME"}
sensitive_tokens = {"api_key", "token", "secret", "password", "credential"}

try:
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
except (OSError, ValueError):
    raise SystemExit(1)
if not isinstance(marker, dict):
    raise SystemExit(1)
if any(token in str(key).lower() for key in marker for token in sensitive_tokens):
    raise SystemExit(1)
if str(marker.get("version", "")).strip() != expected_version:
    raise SystemExit(1)
try:
    marker_pid = int(marker.get("pid", 0))
except (TypeError, ValueError):
    raise SystemExit(1)
if marker_pid <= 0 or marker_pid != expected_pid:
    raise SystemExit(1)
if str(marker.get("state", "")).strip() not in accepted_states:
    raise SystemExit(1)
if not all(marker.get(field) is True for field in ("qml_loaded", "config_loaded", "setup_state_loaded", "storage_writable")):
    raise SystemExit(1)
if marker.get("fatal_startup") is not False:
    raise SystemExit(1)
try:
    updated_at = datetime.fromisoformat(str(marker.get("updated_at", "")).replace("Z", "+00:00"))
except ValueError:
    raise SystemExit(1)
if updated_at.tzinfo is None:
    updated_at = updated_at.replace(tzinfo=timezone.utc)
age = datetime.now(timezone.utc) - updated_at.astimezone(timezone.utc)
if age < timedelta(0) or age > timedelta(seconds=max_age_seconds):
    raise SystemExit(1)
PY
}

log_readiness_diagnostics() {
  local active_state sub_state main_pid restart_count
  active_state="$(service_property ActiveState || true)"
  sub_state="$(service_property SubState || true)"
  main_pid="$(service_property MainPID || true)"
  restart_count="$(service_property NRestarts || true)"
  log "[INFO] Service diagnostics: ActiveState=${active_state:-unknown} SubState=${sub_state:-unknown} MainPID=${main_pid:-unknown} NRestarts=${restart_count:-unknown}"
  if [[ -f "${READINESS_FILE}" ]]; then
    python3 - "${READINESS_FILE}" <<'PY'
import json
import sys
from pathlib import Path

try:
    marker = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except (OSError, ValueError):
    raise SystemExit(0)
if isinstance(marker, dict):
    fields = ("version", "pid", "state", "qml_loaded", "config_loaded", "setup_state_loaded", "storage_writable", "fatal_startup", "updated_at")
    print("[INFO] Readiness diagnostics: " + " ".join(f"{field}={marker.get(field)!r}" for field in fields))
PY
  else
    log "[INFO] Readiness diagnostics: marker is absent."
  fi
}

wait_for_application_readiness() {
  local expected_version="$1"
  local restart_baseline="$2"
  local deadline=$((SECONDS + UPDATE_STARTUP_TIMEOUT_SECONDS))
  local main_pid restart_count

  while (( SECONDS < deadline )); do
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
      main_pid="$(service_property MainPID || true)"
      restart_count="$(service_property NRestarts || true)"
      if [[ "${main_pid}" =~ ^[1-9][0-9]*$ ]] \
        && [[ "${restart_count}" == "${restart_baseline}" ]] \
        && [[ "$(service_property SubState || true)" == "running" ]] \
        && validate_readiness_marker "${expected_version}" "${main_pid}"; then
        return 0
      fi
    fi
    sleep 1
  done
  return 1
}

wait_for_service_stability() {
  local expected_version="$1"
  local restart_baseline="$2"
  local attempt main_pid restart_count
  for attempt in $(seq 1 "${UPDATE_STABILITY_SECONDS}"); do
    systemctl is-active --quiet "${SERVICE_NAME}" || return 1
    main_pid="$(service_property MainPID || true)"
    restart_count="$(service_property NRestarts || true)"
    [[ "${main_pid}" =~ ^[1-9][0-9]*$ ]] || return 1
    [[ "${restart_count}" == "${restart_baseline}" ]] || return 1
    [[ "$(service_property SubState || true)" == "running" ]] || return 1
    validate_readiness_marker "${expected_version}" "${main_pid}" || return 1
    sleep 1
  done
  return 0
}

flip_current_release() {
  PREVIOUS_CURRENT_TARGET="$(readlink -f "${CURRENT_LINK}")"
  if [[ -d "${FINAL_RELEASE_DIR}" ]]; then
    ensure_path_within "${RELEASES_DIR}" "${FINAL_RELEASE_DIR}"
    PREVIOUS_FINAL_RELEASE_BACKUP="${FINAL_RELEASE_DIR}.backup.$(date +%s)"
    mv "${FINAL_RELEASE_DIR}" "${PREVIOUS_FINAL_RELEASE_BACKUP}"
  fi
  mv "${STAGING_RELEASE_DIR}" "${FINAL_RELEASE_DIR}"
  if [[ -n "${STAGING_PARENT}" && -d "${STAGING_PARENT}" && "${STAGING_PARENT}" != "${FINAL_RELEASE_DIR}" ]]; then
    rmdir "${STAGING_PARENT}" 2>/dev/null || true
  fi
  STAGING_RELEASE_DIR=""
  STAGING_PARENT=""
  switch_current_release "${FINAL_RELEASE_DIR}"
  INSTALL_CHANGED_CURRENT=1
  write_rollback_state "${PREVIOUS_CURRENT_TARGET}" "${FINAL_RELEASE_DIR}"
}

activate_release_unit() {
  local release_dir="$1"
  local unit_template="${release_dir}/deployment/visiondesk.service"
  [[ -f "${unit_template}" ]] || return 1
  install -o root -g root -m 644 "${unit_template}" "${SYSTEMD_UNIT}"
  systemctl daemon-reload
}

restart_service() {
  local expected_version="$1"
  local restart_baseline
  clear_readiness_marker
  systemctl restart "${SERVICE_NAME}"
  restart_baseline="$(service_property NRestarts || true)"
  [[ "${restart_baseline}" =~ ^[0-9]+$ ]] || return 1
  wait_for_application_readiness "${expected_version}" "${restart_baseline}" || return 1
  wait_for_service_stability "${expected_version}" "${restart_baseline}"
}

rollback_update() {
  local exit_code="$1"
  local rollback_version=""
  local rollback_ready=1
  if (( INSTALL_CHANGED_CURRENT == 1 )) && [[ -n "${PREVIOUS_CURRENT_TARGET}" ]]; then
    log "[WARN] Update failed. Rolling back to ${PREVIOUS_CURRENT_TARGET}..."
    rollback_version="$(read_release_version "${PREVIOUS_CURRENT_TARGET}" 2>/dev/null || true)"
    if [[ -z "${rollback_version}" ]] || ! switch_current_release "${PREVIOUS_CURRENT_TARGET}"; then
      rollback_ready=0
    elif ! activate_release_unit "${PREVIOUS_CURRENT_TARGET}"; then
      rollback_ready=0
    elif ! restart_service "${rollback_version}"; then
      rollback_ready=0
    fi
    if (( rollback_ready == 0 )); then
      log "[FAIL] Rollback service did not reach verified readiness."
      log_readiness_diagnostics
    else
      log "[OK] Rollback readiness verified for ${rollback_version}."
    fi
  fi
  if [[ -n "${FINAL_RELEASE_DIR}" && -d "${FINAL_RELEASE_DIR}" && "${FINAL_RELEASE_DIR}" != "${PREVIOUS_CURRENT_TARGET}" ]]; then
    safe_remove_tree "${FINAL_RELEASE_DIR}" "${RELEASES_DIR}"
  fi
  if [[ -n "${PREVIOUS_FINAL_RELEASE_BACKUP}" && -d "${PREVIOUS_FINAL_RELEASE_BACKUP}" ]]; then
    mv "${PREVIOUS_FINAL_RELEASE_BACKUP}" "${FINAL_RELEASE_DIR}"
  fi
  if [[ -n "${STAGING_RELEASE_DIR}" && -d "${STAGING_RELEASE_DIR}" ]]; then
    safe_remove_tree "${STAGING_RELEASE_DIR}" "${RELEASES_DIR}"
  fi
  if [[ -n "${STAGING_PARENT}" && -d "${STAGING_PARENT}" ]]; then
    safe_remove_tree "${STAGING_PARENT}" "${RELEASES_DIR}"
  fi
  if (( rollback_ready == 0 )); then
    exit 1
  fi
  exit "${exit_code}"
}

cleanup_success() {
  if [[ -n "${PREVIOUS_FINAL_RELEASE_BACKUP}" && -d "${PREVIOUS_FINAL_RELEASE_BACKUP}" ]]; then
    safe_remove_tree "${PREVIOUS_FINAL_RELEASE_BACKUP}" "${RELEASES_DIR}"
  fi
}

perform_manual_rollback() {
  [[ -f "${ROLLBACK_STATE}" ]] || fail "No rollback metadata is available."
  # shellcheck disable=SC1090
  source "${ROLLBACK_STATE}"
  [[ -n "${PREVIOUS_RELEASE:-}" ]] || fail "Rollback metadata is incomplete."
  [[ -d "${PREVIOUS_RELEASE}" ]] || fail "Rollback release is missing: ${PREVIOUS_RELEASE}"
  ensure_path_within "${RELEASES_DIR}" "${PREVIOUS_RELEASE}"
  if (( DRY_RUN == 1 )); then
    log "[INFO] Dry run: would switch ${CURRENT_LINK} to ${PREVIOUS_RELEASE}"
    return 0
  fi
  switch_current_release "${PREVIOUS_RELEASE}"
  activate_release_unit "${PREVIOUS_RELEASE}" \
    || fail "Could not restore the systemd unit from ${PREVIOUS_RELEASE}."
  local rollback_version
  rollback_version="$(read_release_version "${PREVIOUS_RELEASE}")"
  if ! restart_service "${rollback_version}"; then
    log_readiness_diagnostics
    fail "Rolled-back service did not reach verified readiness."
  fi
  rm -f "${ROLLBACK_STATE}"
  log "[OK] Rolled back current release to ${PREVIOUS_RELEASE}"
}

main() {
  parse_args "$@"
  validate_timeout_configuration
  require_root
  ensure_logging
  log "[INFO] Starting VisionDesk update workflow"

  if (( CHECK_ONLY == 1 )); then
    print_check_report
    exit 0
  fi

  acquire_lock
  require_existing_install

  if (( ROLLBACK_ONLY == 1 )); then
    perform_manual_rollback
    cleanup_success
    exit 0
  fi

  mkdir -p "${RELEASES_DIR}"
  extract_archive
  validate_manifest_and_checksums
  validate_release_shape

  log "[INFO] Target version: ${REQUESTED_VERSION}"
  log "[INFO] Staged release: ${STAGING_RELEASE_DIR}"
  log "[INFO] Preserving: ${CONFIG_DIR} ${DATA_DIR} ${LOG_DIR}"

  if (( DRY_RUN == 1 )); then
    log "[OK] Dry run complete. Archive, manifest, and checksums validated."
    exit 0
  fi

  build_release_environment
  run_release_checks
  flip_current_release
  activate_release_unit "${FINAL_RELEASE_DIR}"
  if ! restart_service "${REQUESTED_VERSION}"; then
    log_readiness_diagnostics
    fail "VisionDesk did not reach verified readiness after the update."
  fi
  cleanup_success
  log "[OK] Update complete: ${REQUESTED_VERSION}"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  trap 'rc=$?; release_lock; if (( rc != 0 )); then rollback_update "${rc}"; fi' EXIT
  main "$@"
fi
