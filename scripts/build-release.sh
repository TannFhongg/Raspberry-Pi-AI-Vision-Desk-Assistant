#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONTRACT_TOOL="${SCRIPT_DIR}/release_contract.py"
PYTHON_BIN="${PYTHON_BIN:-python3}"

REQUESTED_VERSION=""
GIT_REF="HEAD"
ALLOW_DIRTY=0
ALLOW_UNTAGGED=0
STAGING_DIR=""
ARCHIVE_TEMP=""

# Runtime and lifecycle files only. Development state, tests, documentation,
# source-control metadata, and local artifacts are intentionally excluded.
RELEASE_CONTENTS=(
  .env.example
  requirements.txt
  install.sh
  update.sh
  uninstall.sh
  factory-reset.sh
  ai
  camera
  config
  deployment
  gpio
  hardware
  pipeline
  qt_app
  system
  vision
  visiondesk
)

usage() {
  cat <<'EOF'
Usage:
  scripts/build-release.sh [--version <version>] [--git-ref <tag-or-commit>] [--allow-dirty] [--allow-untagged]

Builds dist/visiondesk-<version>.tar.gz from a Git commit. The default source is
HEAD and must have an exact Git tag matching the application version, for example
v1.0.0 -> 1.0.0. Use --git-ref v1.0.0 to package an existing tag.

Options:
  --version <version>    Expected application version; accepts 1.0.0 or v1.0.0.
  --git-ref <ref>        Git tag or commit to package (default: HEAD).
  --allow-dirty          Permit a dirty working tree. The archive still comes
                         only from --git-ref via git archive.
  --allow-untagged       Permit a commit without an exact matching Git tag.
  --help, -h             Show this help.
EOF
}

log() {
  printf '%s\n' "$*"
}

fail() {
  log "[FAIL] $*" >&2
  exit 1
}

cleanup() {
  if [[ -n "${STAGING_DIR}" && -d "${STAGING_DIR}" ]]; then
    rm -rf -- "${STAGING_DIR}"
  fi
  if [[ -n "${ARCHIVE_TEMP}" && -f "${ARCHIVE_TEMP}" ]]; then
    rm -f -- "${ARCHIVE_TEMP}"
  fi
}

normalize_version() {
  local value="${1#v}"
  [[ "${value}" =~ ^[0-9]+(\.[0-9]+){2}([-+][0-9A-Za-z.-]+)?$ ]] \
    || fail "Invalid version '${1}'. Expected MAJOR.MINOR.PATCH, optionally with -pre or +build."
  printf '%s\n' "${value}"
}

parse_args() {
  while (($# > 0)); do
    case "$1" in
      --version)
        shift
        (($# > 0)) || fail "--version requires a value."
        REQUESTED_VERSION="$1"
        ;;
      --git-ref)
        shift
        (($# > 0)) || fail "--git-ref requires a tag or commit."
        GIT_REF="$1"
        ;;
      --allow-dirty)
        ALLOW_DIRTY=1
        ;;
      --allow-untagged)
        ALLOW_UNTAGGED=1
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

require_tooling() {
  local tool
  for tool in git tar gzip sha256sum sort find; do
    command -v "${tool}" >/dev/null 2>&1 || fail "Required tool is missing: ${tool}"
  done
  command -v "${PYTHON_BIN}" >/dev/null 2>&1 || fail "Python interpreter was not found: ${PYTHON_BIN}"
  [[ -f "${CONTRACT_TOOL}" ]] || fail "Release contract helper is missing: ${CONTRACT_TOOL}"
  git -C "${REPO_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || fail "build-release.sh must run from a Git working tree."
}

check_working_tree() {
  if (( ALLOW_DIRTY == 1 )); then
    log "[WARN] Building from ${GIT_REF} despite a dirty working tree."
    return 0
  fi
  [[ -z "$(git -C "${REPO_ROOT}" status --porcelain --untracked-files=normal)" ]] \
    || fail "Working tree is not clean. Commit/stash changes or pass --allow-dirty."
}

resolve_tag_for_commit() {
  local commit="$1"
  local explicit_tag=""
  if git -C "${REPO_ROOT}" show-ref --verify --quiet "refs/tags/${GIT_REF}"; then
    explicit_tag="${GIT_REF#refs/tags/}"
    printf '%s\n' "${explicit_tag}"
    return 0
  fi
  git -C "${REPO_ROOT}" describe --tags --exact-match "${commit}" 2>/dev/null || true
}

create_checksums() {
  local release_root="$1"
  (
    cd "${release_root}"
    while IFS= read -r -d '' path; do
      sha256sum -- "${path}"
    done < <(find . -type f ! -path './checksums.sha256' -print0 | LC_ALL=C sort -z)
  ) > "${release_root}/checksums.sha256"
}

validate_with_updater_contract() {
  local archive_path="$1"
  local release_root="$2"
  local validation_root="${STAGING_DIR}/updater-contract"
  local validation_log="${validation_root}/updater-contract.log"
  mkdir -p "${validation_root}/releases"
  if ! (
      # Sourcing defines the exact extraction, manifest, checksum, version, and
      # release-shape functions without invoking update.sh's system-changing main.
      # shellcheck disable=SC1090
      source "${release_root}/update.sh"
      ARCHIVE_PATH="${archive_path}"
      RELEASES_DIR="${validation_root}/releases"
      REQUESTED_VERSION="${BUILD_VERSION}"
      STAGING_PARENT=""
      STAGING_RELEASE_DIR=""
      FINAL_RELEASE_DIR=""
      extract_archive
      validate_manifest_and_checksums
      validate_release_shape
    ) > "${validation_log}" 2>&1; then
    cat "${validation_log}" >&2
    return 1
  fi
  rm -rf -- "${validation_root}"
}

parse_args "$@"
require_tooling
check_working_tree
trap cleanup EXIT

COMMIT="$(git -C "${REPO_ROOT}" rev-parse --verify "${GIT_REF}^{commit}")" \
  || fail "Could not resolve Git ref '${GIT_REF}'."
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git -C "${REPO_ROOT}" show -s --format=%ct "${COMMIT}")}" \
  || fail "Could not read commit timestamp."
[[ "${SOURCE_DATE_EPOCH}" =~ ^[0-9]+$ ]] || fail "SOURCE_DATE_EPOCH must be an integer timestamp."

STAGING_DIR="$(mktemp -d "${TMPDIR:-/tmp}/visiondesk-release.XXXXXX")"
SOURCE_ROOT="${STAGING_DIR}/source"
mkdir -p "${SOURCE_ROOT}"

log "[INFO] Exporting Git commit ${COMMIT}..."
git -C "${REPO_ROOT}" archive --format=tar "${COMMIT}" -- "${RELEASE_CONTENTS[@]}" \
  | tar -xf - -C "${SOURCE_ROOT}"

SOURCE_VERSION="$("${PYTHON_BIN}" "${CONTRACT_TOOL}" read-version --file "${SOURCE_ROOT}/visiondesk/version.py")" \
  || fail "Could not read application version from the selected source."
BUILD_VERSION="${SOURCE_VERSION}"
if [[ -n "${REQUESTED_VERSION}" ]]; then
  BUILD_VERSION="$(normalize_version "${REQUESTED_VERSION}")"
fi
[[ "${SOURCE_VERSION}" == "${BUILD_VERSION}" ]] \
  || fail "Source version ${SOURCE_VERSION} does not match requested version ${BUILD_VERSION}."

SOURCE_TAG="$(resolve_tag_for_commit "${COMMIT}")"
if [[ -n "${SOURCE_TAG}" ]]; then
  TAG_VERSION="$(normalize_version "${SOURCE_TAG}")"
  [[ "${TAG_VERSION}" == "${BUILD_VERSION}" ]] \
    || fail "Git tag ${SOURCE_TAG} does not match application version ${BUILD_VERSION}."
elif (( ALLOW_UNTAGGED == 0 )); then
  fail "Commit ${COMMIT} has no exact Git tag. Pass --allow-untagged only for non-production builds."
fi

RELEASE_DIR_NAME="visiondesk-${BUILD_VERSION}"
RELEASE_ROOT="${STAGING_DIR}/${RELEASE_DIR_NAME}"
mv "${SOURCE_ROOT}" "${RELEASE_ROOT}"

chmod 755 \
  "${RELEASE_ROOT}/install.sh" \
  "${RELEASE_ROOT}/update.sh" \
  "${RELEASE_ROOT}/uninstall.sh" \
  "${RELEASE_ROOT}/factory-reset.sh" \
  "${RELEASE_ROOT}/deployment/visiondesk-launch.sh"

cat > "${RELEASE_ROOT}/manifest.json" <<EOF
{
  "version": "${BUILD_VERSION}",
  "checksums_file": "checksums.sha256"
}
EOF
create_checksums "${RELEASE_ROOT}"

DIST_DIR="${REPO_ROOT}/dist"
ARCHIVE_PATH="${DIST_DIR}/visiondesk-${BUILD_VERSION}.tar.gz"
ARCHIVE_TEMP="${DIST_DIR}/.visiondesk-${BUILD_VERSION}.tar.gz.tmp"
mkdir -p "${DIST_DIR}"
rm -f -- "${ARCHIVE_TEMP}"

tar --create --sort=name --mtime="@${SOURCE_DATE_EPOCH}" --owner=0 --group=0 --numeric-owner \
  --pax-option=delete=atime,delete=ctime --file=- -C "${STAGING_DIR}" "${RELEASE_DIR_NAME}" \
  | gzip -n > "${ARCHIVE_TEMP}"

bash "${SCRIPT_DIR}/verify-release.sh" "${ARCHIVE_TEMP}" --expected-version "${BUILD_VERSION}"
validate_with_updater_contract "${ARCHIVE_TEMP}" "${RELEASE_ROOT}"
log "[OK] update.sh archive contract validated"
mv -f -- "${ARCHIVE_TEMP}" "${ARCHIVE_PATH}"
ARCHIVE_TEMP=""

ARCHIVE_SIZE="$(wc -c < "${ARCHIVE_PATH}" | tr -d '[:space:]')"
ARCHIVE_SHA256="$(sha256sum "${ARCHIVE_PATH}" | awk '{print $1}')"
log "[OK] Release archive created"
log "  Archive: ${ARCHIVE_PATH}"
log "  Size: ${ARCHIVE_SIZE} bytes"
log "  SHA-256: ${ARCHIVE_SHA256}"
log "  Version: ${BUILD_VERSION}"
log "  Git commit: ${COMMIT}"
if [[ -n "${SOURCE_TAG}" ]]; then
  log "  Git tag: ${SOURCE_TAG}"
else
  log "  Git tag: none (allowed explicitly)"
fi
