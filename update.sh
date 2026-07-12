#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="visiondesk"
APP_USER="visiondesk"
APP_GROUP="visiondesk"
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
  python3 - <<PY
import sys
sys.path.insert(0, ${release_dir@Q})
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
  local manifest_path manifest_version checksums_rel checksums_path release_version
  manifest_path="${STAGING_RELEASE_DIR}/manifest.json"
  [[ -f "${manifest_path}" ]] || fail "Archive is missing manifest.json."

  manifest_version="$(python3 - <<PY
import json
from pathlib import Path
manifest = json.loads(Path(${manifest_path@Q}).read_text(encoding="utf-8"))
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

wait_for_service_healthy() {
  local attempt
  for attempt in $(seq 1 20); do
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
      return 0
    fi
    sleep 2
  done
  return 1
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
  ln -sfn "${FINAL_RELEASE_DIR}" "${CURRENT_LINK}"
  INSTALL_CHANGED_CURRENT=1
  write_rollback_state "${PREVIOUS_CURRENT_TARGET}" "${FINAL_RELEASE_DIR}"
}

restart_service() {
  systemctl restart "${SERVICE_NAME}"
  wait_for_service_healthy || fail "VisionDesk service did not become healthy after the update."
}

rollback_update() {
  local exit_code="$1"
  if (( INSTALL_CHANGED_CURRENT == 1 )) && [[ -n "${PREVIOUS_CURRENT_TARGET}" ]]; then
    log "[WARN] Update failed. Rolling back to ${PREVIOUS_CURRENT_TARGET}..."
    ln -sfn "${PREVIOUS_CURRENT_TARGET}" "${CURRENT_LINK}" || true
    systemctl restart "${SERVICE_NAME}" >/dev/null 2>&1 || true
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
  ln -sfn "${PREVIOUS_RELEASE}" "${CURRENT_LINK}"
  systemctl restart "${SERVICE_NAME}"
  wait_for_service_healthy || fail "Rolled-back service did not become healthy."
  rm -f "${ROLLBACK_STATE}"
  log "[OK] Rolled back current release to ${PREVIOUS_RELEASE}"
}

main() {
  parse_args "$@"
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
  restart_service
  cleanup_success
  log "[OK] Update complete: ${REQUESTED_VERSION}"
}

trap 'rc=$?; release_lock; if (( rc != 0 )); then rollback_update "${rc}"; fi' EXIT

main "$@"
