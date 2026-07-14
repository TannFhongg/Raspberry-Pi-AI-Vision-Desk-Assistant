#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

usage() {
  cat <<'EOF'
Usage:
  scripts/verify-release.sh /path/to/visiondesk-<version>.tar.gz [--expected-version <version>]

Validates archive paths, symlinks, manifest.json, checksums.sha256, release
layout, and source version without installing or modifying the appliance.
EOF
}

if (($# == 0)); then
  usage >&2
  exit 1
fi

case "${1:-}" in
  --help|-h)
    usage
    exit 0
    ;;
esac

archive_path="$1"
shift

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  printf '[FAIL] Python interpreter was not found: %s\n' "${PYTHON_BIN}" >&2
  exit 1
fi

exec "${PYTHON_BIN}" "${SCRIPT_DIR}/release_contract.py" verify --archive "${archive_path}" "$@"
