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
INSTALL_LOG="${LOG_DIR}/install.log"
SERVICE_TEMPLATE="${SCRIPT_DIR}/deployment/visiondesk.service"
LAUNCHER_TEMPLATE="${SCRIPT_DIR}/deployment/visiondesk-launch.sh"
POLKIT_RULE_TEMPLATE="${SCRIPT_DIR}/deployment/49-visiondesk-networkmanager.rules"
SYSTEMD_UNIT="/etc/systemd/system/visiondesk.service"
POLKIT_RULE="/etc/polkit-1/rules.d/49-visiondesk-networkmanager.rules"
LIGHTDM_CONF_DIR="/etc/lightdm/lightdm.conf.d"
LIGHTDM_CONF="${LIGHTDM_CONF_DIR}/99-visiondesk.conf"
MIN_FREE_MB=1024
SYSTEM_PACKAGES=(
  python3
  python3-pip
  python3-venv
  python3-opencv
  python3-rpi.gpio
  network-manager
  systemd
  v4l-utils
  fontconfig
  fonts-noto-core
  libdbus-1-3
  libegl1
  libgl1
  libopengl0
  libx11-xcb1
  libxcb-cursor0
  libxcb-keysyms1
  libxcb-icccm4
  libxcb-image0
  libxcb-randr0
  libxcb-render-util0
  libxcb-xfixes0
  libxcb-xinerama0
  libxkbcommon-x11-0
)

NON_INTERACTIVE=0
SKIP_HARDWARE_CHECK=0
RESET_CONFIG=0
FORCE_INSTALL=0

PREVIOUS_CURRENT_TARGET=""
PREVIOUS_SERVICE_BACKUP=""
PREVIOUS_POLKIT_RULE_BACKUP=""
PREVIOUS_FINAL_RELEASE_BACKUP=""
ENV_BACKUP=""
CONFIG_BACKUP=""
STAGING_RELEASE_DIR=""
FINAL_RELEASE_DIR=""
INSTALL_CHANGED_CURRENT=0
INSTALL_CHANGED_SERVICE=0
INSTALL_CHANGED_POLKIT_RULE=0

usage() {
  cat <<'EOF'
Usage:
  sudo ./install.sh [--non-interactive] [--skip-hardware-check] [--reset-config] [--force]
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
  local base_path target_path resolved_base resolved_target
  base_path="$1"
  target_path="$2"
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
    fail "install.sh must be run as root."
  fi
}

parse_args() {
  while (($# > 0)); do
    case "$1" in
      --non-interactive)
        NON_INTERACTIVE=1
        ;;
      --skip-hardware-check)
        SKIP_HARDWARE_CHECK=1
        ;;
      --reset-config)
        RESET_CONFIG=1
        ;;
      --force)
        FORCE_INSTALL=1
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

ensure_logging() {
  mkdir -p "${LOG_DIR}"
  touch "${INSTALL_LOG}"
  chmod 640 "${INSTALL_LOG}"
  exec > >(tee -a "${INSTALL_LOG}") 2>&1
}

confirm_continue() {
  if (( NON_INTERACTIVE == 1 )); then
    return 0
  fi
  printf 'Install VisionDesk to %s? [y/N]: ' "${APP_ROOT}"
  read -r response
  if [[ ! "${response}" =~ ^[Yy]$ ]]; then
    fail "Installation cancelled."
  fi
}

validate_project_shape() {
  local required_paths=(
    "${SCRIPT_DIR}/qt_app/main.py"
    "${SCRIPT_DIR}/visiondesk/version.py"
    "${SCRIPT_DIR}/requirements.txt"
    "${SERVICE_TEMPLATE}"
    "${LAUNCHER_TEMPLATE}"
    "${POLKIT_RULE_TEMPLATE}"
  )
  local path
  for path in "${required_paths[@]}"; do
    [[ -e "${path}" ]] || fail "Project source is missing required file: ${path}"
  done
}

validate_platform() {
  local os_id="" pretty_name="" arch="" python_version major minor
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    os_id="${ID:-}"
    pretty_name="${PRETTY_NAME:-}"
  fi

  if [[ "${os_id}" != "raspbian" && "${pretty_name}" != *"Raspberry Pi OS"* ]]; then
    if (( FORCE_INSTALL == 0 )); then
      fail "Unsupported platform. Raspberry Pi OS is required unless --force is supplied."
    fi
    log "[WARN] Continuing on unsupported platform because --force was supplied."
  fi

  arch="$(dpkg --print-architecture 2>/dev/null || uname -m)"
  case "${arch}" in
    arm64|armhf|aarch64)
      ;;
    *)
      if (( FORCE_INSTALL == 0 )); then
        fail "Unsupported CPU architecture '${arch}'. Use --force to continue anyway."
      fi
      log "[WARN] Continuing on unsupported CPU architecture '${arch}' because --force was supplied."
      ;;
  esac

  if ! command -v python3 >/dev/null 2>&1; then
    fail "python3 is required but was not found."
  fi

  python_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  major="${python_version%%.*}"
  minor="${python_version##*.}"
  if (( major < 3 )) || (( major == 3 && minor < 10 )); then
    fail "Python 3.10 or newer is required. Found ${python_version}."
  fi

  if ! dpkg-query -W -f='${Status}' lightdm 2>/dev/null | grep -q "install ok installed"; then
    if (( FORCE_INSTALL == 0 )); then
      fail "Graphical session prerequisites are missing. LightDM is required unless --force is supplied."
    fi
    log "[WARN] LightDM was not detected. Continuing because --force was supplied."
  fi

  local free_mb
  free_mb="$(df -Pm /opt | awk 'NR==2 {print $4}')"
  if [[ -z "${free_mb}" ]] || (( free_mb < MIN_FREE_MB )); then
    fail "At least ${MIN_FREE_MB} MB of free disk space is required on /opt."
  fi
}

install_system_packages() {
  local apt_args=(-y --no-install-recommends)
  if (( NON_INTERACTIVE == 1 )); then
    export DEBIAN_FRONTEND=noninteractive
  fi
  log "[INFO] Installing system packages..."
  apt-get update
  apt-get install "${apt_args[@]}" "${SYSTEM_PACKAGES[@]}"
  systemctl enable NetworkManager >/dev/null 2>&1 || true
}

verify_ui_font() {
  local selected_font
  if ! command -v fc-match >/dev/null 2>&1; then
    log "[WARN] fontconfig is unavailable; Qt will use its system font fallback."
    return 0
  fi
  selected_font="$(fc-match -f '%{family}\n' 'Noto Sans' 2>/dev/null | head -n 1 || true)"
  if [[ -n "${selected_font}" ]]; then
    log "[OK] UI body font available: ${selected_font}"
  else
    log "[WARN] Noto Sans was not matched; VisionDesk will fall back to Inter, DejaVu Sans, or bundled Roboto."
  fi
}

ensure_group() {
  local group_name="$1"
  if ! getent group "${group_name}" >/dev/null 2>&1; then
    groupadd --system "${group_name}"
  fi
}

ensure_user() {
  if ! getent group "${APP_GROUP}" >/dev/null 2>&1; then
    groupadd --system "${APP_GROUP}"
  fi
  if ! id -u "${APP_USER}" >/dev/null 2>&1; then
    useradd --system --create-home --gid "${APP_GROUP}" --shell /bin/bash "${APP_USER}"
  fi
  ensure_group gpio
  local groups=(video render input gpio dialout netdev)
  local group_name
  for group_name in "${groups[@]}"; do
    if getent group "${group_name}" >/dev/null 2>&1; then
      usermod -aG "${group_name}" "${APP_USER}"
    fi
  done
}

configure_autologin() {
  if ! dpkg-query -W -f='${Status}' lightdm 2>/dev/null | grep -q "install ok installed"; then
    log "[WARN] Skipping LightDM autologin because LightDM is not installed."
    return 0
  fi
  mkdir -p "${LIGHTDM_CONF_DIR}"
  cat > "${LIGHTDM_CONF}" <<EOF
[Seat:*]
autologin-user=${APP_USER}
autologin-user-timeout=0
EOF
  chmod 644 "${LIGHTDM_CONF}"
}

backup_file_if_exists() {
  local source_path="$1"
  local backup_path="$2"
  if [[ -f "${source_path}" ]]; then
    cp -p "${source_path}" "${backup_path}"
  fi
}

prepare_directories() {
  mkdir -p "${RELEASES_DIR}" "${DATA_DIR}" "${DATA_DIR}/private" "${DATA_DIR}/private/current" \
    "${DATA_DIR}/private/retry" "${DATA_DIR}/private/quarantine" "${DATA_DIR}/retry" \
    "${LOG_DIR}" "${CONFIG_DIR}"
  chown -R "${APP_USER}:${APP_GROUP}" "${DATA_DIR}" "${LOG_DIR}" "${CONFIG_DIR}"
  chmod 750 "${DATA_DIR}" "${DATA_DIR}/private" "${DATA_DIR}/private/current" "${DATA_DIR}/private/retry" "${DATA_DIR}/private/quarantine" "${CONFIG_DIR}"
  chmod 755 "${LOG_DIR}"
}

read_app_version() {
  python3 - <<PY
import sys
sys.path.insert(0, ${SCRIPT_DIR@Q})
from visiondesk.version import __version__
print(__version__)
PY
}

select_requirements_file() {
  if [[ -f "${SCRIPT_DIR}/requirements.lock" ]]; then
    printf '%s\n' "${SCRIPT_DIR}/requirements.lock"
  else
    printf '%s\n' "${SCRIPT_DIR}/requirements.txt"
  fi
}

seed_env_file() {
  local source_env="${SCRIPT_DIR}/.env.example"
  local target_env="$1"
  local temp_env
  temp_env="$(mktemp)"
  {
    printf 'VISIONDESK_PATH_MODE=production\n'
    printf 'VISIONDESK_APP_DIR=%s\n' "${CURRENT_LINK}"
    printf 'VISIONDESK_RELEASES_DIR=%s\n' "${RELEASES_DIR}"
    printf 'VISIONDESK_ENV_FILE=%s\n' "${ENV_FILE}"
    printf 'VISIONDESK_DATA_DIR=%s\n' "${DATA_DIR}"
    printf 'VISIONDESK_LOG_DIR=%s\n' "${LOG_DIR}"
    printf 'DEVICE_CONFIG_PATH=%s\n' "${CONFIG_FILE}"
    if [[ -f "${source_env}" ]]; then
      grep -Ev '^(VISIONDESK_PATH_MODE|VISIONDESK_APP_DIR|VISIONDESK_RELEASES_DIR|VISIONDESK_ENV_FILE|VISIONDESK_DATA_DIR|VISIONDESK_LOG_DIR|DEVICE_CONFIG_PATH)=' "${source_env}" || true
    fi
  } > "${temp_env}"
  install -o "${APP_USER}" -g "${APP_GROUP}" -m 600 "${temp_env}" "${target_env}"
  rm -f "${temp_env}"
}

seed_config_file() {
  install -o "${APP_USER}" -g "${APP_GROUP}" -m 640 "${SCRIPT_DIR}/config/device.yaml" "${CONFIG_FILE}"
}

stage_release() {
  local version requirements_file temp_dir backup_dir
  version="$(read_app_version)"
  requirements_file="$(select_requirements_file)"
  FINAL_RELEASE_DIR="${RELEASES_DIR}/${version}"
  STAGING_RELEASE_DIR="${RELEASES_DIR}/.staging-${version}-$$"
  mkdir -p "${STAGING_RELEASE_DIR}"

  tar -C "${SCRIPT_DIR}" \
    --exclude='.git' \
    --exclude='.pytest_cache' \
    --exclude='__pycache__' \
    --exclude='logs' \
    --exclude='data' \
    --exclude='debug' \
    -cf - . | tar -C "${STAGING_RELEASE_DIR}" -xf -

  python3 -m venv --system-site-packages "${STAGING_RELEASE_DIR}/.venv"
  "${STAGING_RELEASE_DIR}/.venv/bin/pip" install --upgrade pip setuptools wheel
  "${STAGING_RELEASE_DIR}/.venv/bin/pip" install --no-cache-dir -r "${requirements_file}"

  chmod 755 "${STAGING_RELEASE_DIR}/deployment/visiondesk-launch.sh"
  chown -R "${APP_USER}:${APP_GROUP}" "${STAGING_RELEASE_DIR}"

  if [[ -d "${FINAL_RELEASE_DIR}" ]]; then
    backup_dir="${FINAL_RELEASE_DIR}.backup.$(date +%s)"
    ensure_path_within "${RELEASES_DIR}" "${FINAL_RELEASE_DIR}"
    mv "${FINAL_RELEASE_DIR}" "${backup_dir}"
    PREVIOUS_FINAL_RELEASE_BACKUP="${backup_dir}"
  fi
  mv "${STAGING_RELEASE_DIR}" "${FINAL_RELEASE_DIR}"
  STAGING_RELEASE_DIR=""
}

render_service() {
  local temp_unit
  PREVIOUS_CURRENT_TARGET="$(readlink -f "${CURRENT_LINK}" 2>/dev/null || true)"
  if [[ -f "${SYSTEMD_UNIT}" ]]; then
    PREVIOUS_SERVICE_BACKUP="${SYSTEMD_UNIT}.backup.$$"
    cp -p "${SYSTEMD_UNIT}" "${PREVIOUS_SERVICE_BACKUP}"
  fi

  ln -sfn "${FINAL_RELEASE_DIR}" "${CURRENT_LINK}"
  INSTALL_CHANGED_CURRENT=1

  temp_unit="$(mktemp)"
  install -m 644 "${SERVICE_TEMPLATE}" "${temp_unit}"
  install -m 644 "${temp_unit}" "${SYSTEMD_UNIT}"
  rm -f "${temp_unit}"
  INSTALL_CHANGED_SERVICE=1
  systemctl daemon-reload
  systemctl enable visiondesk.service
}

install_networkmanager_policy() {
  if [[ -f "${POLKIT_RULE}" ]]; then
    PREVIOUS_POLKIT_RULE_BACKUP="${POLKIT_RULE}.backup.$$"
    cp -p "${POLKIT_RULE}" "${PREVIOUS_POLKIT_RULE_BACKUP}"
  fi
  install -D -o root -g root -m 644 "${POLKIT_RULE_TEMPLATE}" "${POLKIT_RULE}"
  INSTALL_CHANGED_POLKIT_RULE=1
}

disable_legacy_unit() {
  local unit_name="$1"
  local unit_path="/etc/systemd/system/${unit_name}"
  if [[ -f "${unit_path}" ]] && grep -Eq 'visiondesk-qt|Chromium|flask|qt_app\.main' "${unit_path}"; then
    log "[INFO] Disabling legacy unit ${unit_name}"
    systemctl disable --now "${unit_name}" >/dev/null 2>&1 || true
  fi
}

run_smoke_checks() {
  local check_args=()
  if (( SKIP_HARDWARE_CHECK == 1 )); then
    check_args+=(--skip-hardware)
  fi
  runuser -u "${APP_USER}" -- env \
    VISIONDESK_PATH_MODE=production \
    VISIONDESK_APP_DIR="${FINAL_RELEASE_DIR}" \
    VISIONDESK_RELEASES_DIR="${RELEASES_DIR}" \
    VISIONDESK_ENV_FILE="${ENV_FILE}" \
    VISIONDESK_DATA_DIR="${DATA_DIR}" \
    VISIONDESK_LOG_DIR="${LOG_DIR}" \
    DEVICE_CONFIG_PATH="${CONFIG_FILE}" \
    "${FINAL_RELEASE_DIR}/.venv/bin/python" -m system.diagnostics "${check_args[@]}"
}

start_service() {
  systemctl restart visiondesk.service
}

cleanup_install_backups() {
  if [[ -n "${PREVIOUS_SERVICE_BACKUP}" && -f "${PREVIOUS_SERVICE_BACKUP}" ]]; then
    rm -f "${PREVIOUS_SERVICE_BACKUP}"
  fi
  if [[ -n "${PREVIOUS_POLKIT_RULE_BACKUP}" && -f "${PREVIOUS_POLKIT_RULE_BACKUP}" ]]; then
    rm -f "${PREVIOUS_POLKIT_RULE_BACKUP}"
  fi
  if [[ -n "${PREVIOUS_FINAL_RELEASE_BACKUP}" && -d "${PREVIOUS_FINAL_RELEASE_BACKUP}" ]]; then
    safe_remove_tree "${PREVIOUS_FINAL_RELEASE_BACKUP}" "${RELEASES_DIR}"
  fi
}

restore_backups() {
  if [[ -n "${ENV_BACKUP}" && -f "${ENV_BACKUP}" ]]; then
    install -o "${APP_USER}" -g "${APP_GROUP}" -m 600 "${ENV_BACKUP}" "${ENV_FILE}"
  fi
  if [[ -n "${CONFIG_BACKUP}" && -f "${CONFIG_BACKUP}" ]]; then
    install -o "${APP_USER}" -g "${APP_GROUP}" -m 640 "${CONFIG_BACKUP}" "${CONFIG_FILE}"
  fi
}

rollback_on_failure() {
  local exit_code="$1"
  log "[WARN] Installation failed. Rolling back partial changes..."
  restore_backups
  if (( INSTALL_CHANGED_SERVICE == 1 )); then
    if [[ -n "${PREVIOUS_SERVICE_BACKUP}" && -f "${PREVIOUS_SERVICE_BACKUP}" ]]; then
      install -m 644 "${PREVIOUS_SERVICE_BACKUP}" "${SYSTEMD_UNIT}"
    else
      rm -f "${SYSTEMD_UNIT}"
    fi
    systemctl daemon-reload || true
  fi
  if (( INSTALL_CHANGED_POLKIT_RULE == 1 )); then
    if [[ -n "${PREVIOUS_POLKIT_RULE_BACKUP}" && -f "${PREVIOUS_POLKIT_RULE_BACKUP}" ]]; then
      install -o root -g root -m 644 "${PREVIOUS_POLKIT_RULE_BACKUP}" "${POLKIT_RULE}"
    else
      rm -f "${POLKIT_RULE}"
    fi
  fi
  if (( INSTALL_CHANGED_CURRENT == 1 )); then
    if [[ -n "${PREVIOUS_CURRENT_TARGET}" ]]; then
      ln -sfn "${PREVIOUS_CURRENT_TARGET}" "${CURRENT_LINK}" || true
    else
      rm -f "${CURRENT_LINK}"
    fi
  fi
  if [[ -n "${STAGING_RELEASE_DIR}" && -d "${STAGING_RELEASE_DIR}" ]]; then
    safe_remove_tree "${STAGING_RELEASE_DIR}" "${RELEASES_DIR}"
  fi
  if [[ -n "${FINAL_RELEASE_DIR}" && -d "${FINAL_RELEASE_DIR}" && "${FINAL_RELEASE_DIR}" != "${PREVIOUS_CURRENT_TARGET}" ]]; then
    safe_remove_tree "${FINAL_RELEASE_DIR}" "${RELEASES_DIR}"
  fi
  if [[ -n "${PREVIOUS_FINAL_RELEASE_BACKUP}" && -d "${PREVIOUS_FINAL_RELEASE_BACKUP}" ]]; then
    mv "${PREVIOUS_FINAL_RELEASE_BACKUP}" "${FINAL_RELEASE_DIR}"
  fi
  exit "${exit_code}"
}

print_summary() {
  log "[OK] Python environment"
  log "[OK] Qt/QML runtime"
  log "[OK] Application files"
  log "[OK] Private storage"
  log "[OK] systemd service"
  if (( SKIP_HARDWARE_CHECK == 1 )); then
    log "[OK] Camera (skipped)"
    log "[OK] GPIO (skipped)"
  else
    log "[OK] Camera"
    log "[OK] GPIO"
  fi
  log "[OK] Installation complete"
}

main() {
  parse_args "$@"
  require_root
  ensure_logging
  log "[INFO] Starting VisionDesk installation from ${SCRIPT_DIR}"
  validate_project_shape
  validate_platform
  confirm_continue
  install_system_packages
  verify_ui_font
  ensure_user
  install_networkmanager_policy
  prepare_directories
  configure_autologin

  if (( RESET_CONFIG == 1 )); then
    ENV_BACKUP="$(mktemp)"
    CONFIG_BACKUP="$(mktemp)"
    backup_file_if_exists "${ENV_FILE}" "${ENV_BACKUP}"
    backup_file_if_exists "${CONFIG_FILE}" "${CONFIG_BACKUP}"
    seed_env_file "${ENV_FILE}"
    seed_config_file
  else
    [[ -f "${ENV_FILE}" ]] || seed_env_file "${ENV_FILE}"
    [[ -f "${CONFIG_FILE}" ]] || seed_config_file
  fi

  stage_release
  render_service
  disable_legacy_unit visiondesk-qt.service
  disable_legacy_unit ai-vision-assistant.service
  disable_legacy_unit visiondesk-browser.service
  run_smoke_checks
  start_service
  cleanup_install_backups
  print_summary
}

trap 'rc=$?; if (( rc != 0 )); then rollback_on_failure "${rc}"; fi' EXIT

main "$@"
