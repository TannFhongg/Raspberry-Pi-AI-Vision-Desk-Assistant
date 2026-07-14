#!/usr/bin/env python3
"""Safe, reusable validation for VisionDesk appliance release archives."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


VERSION_PATTERN = re.compile(r"^[0-9]+(?:\.[0-9]+){2}(?:[-+][0-9A-Za-z.-]+)?$")
CHECKSUM_PATTERN = re.compile(r"^([0-9a-f]{64})  (\./[^\r\n]+)$")

# These paths are copied by build-release.sh. They are a stricter release layout
# than update.sh's minimal shape check, so a published appliance package contains
# every module and asset needed by the installed Qt application and lifecycle scripts.
RELEASE_TOP_LEVEL = frozenset(
    {
        ".env.example",
        "ai",
        "camera",
        "config",
        "deployment",
        "factory-reset.sh",
        "gpio",
        "hardware",
        "install.sh",
        "manifest.json",
        "pipeline",
        "qt_app",
        "requirements.txt",
        "system",
        "uninstall.sh",
        "update.sh",
        "vision",
        "visiondesk",
        "checksums.sha256",
    }
)

REQUIRED_PATHS = (
    ".env.example",
    "requirements.txt",
    "install.sh",
    "update.sh",
    "uninstall.sh",
    "factory-reset.sh",
    "ai/modes.py",
    "ai/openai_client.py",
    "camera/__init__.py",
    "config/__init__.py",
    "config/device.yaml",
    "deployment/49-visiondesk-networkmanager.rules",
    "deployment/visiondesk-launch.sh",
    "deployment/visiondesk.service",
    "gpio/__init__.py",
    "hardware/__init__.py",
    "pipeline/__init__.py",
    "qt_app/main.py",
    "qt_app/qml/Main.qml",
    "system/__init__.py",
    "system/diagnostics.py",
    "system/migrations.py",
    "vision/__init__.py",
    "visiondesk/__init__.py",
    "visiondesk/paths.py",
    "visiondesk/version.py",
)

FORBIDDEN_PARTS = frozenset(
    {
        ".git",
        ".pytest_cache",
        ".venv",
        "venv",
        "data",
        "debug",
        "dist",
        "logs",
        "tests",
        "__pycache__",
    }
)


class ReleaseContractError(ValueError):
    """Raised when an archive does not satisfy the publishable release contract."""


def normalize_version(value: str) -> str:
    """Normalize a Git-style vX.Y.Z reference to the application version."""
    normalized = str(value or "").strip()
    if normalized.startswith("v"):
        normalized = normalized[1:]
    if not VERSION_PATTERN.fullmatch(normalized):
        raise ReleaseContractError(
            "Version must use MAJOR.MINOR.PATCH with an optional -pre or +build suffix."
        )
    return normalized


def read_version_file(path: Path) -> str:
    """Read __version__ as a static string without importing untrusted release code."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise ReleaseContractError(f"Could not parse {path}: {exc}") from exc

    for node in tree.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        if value is None or not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        if any(isinstance(target, ast.Name) and target.id == "__version__" for target in targets):
            return normalize_version(value.value)

    raise ReleaseContractError(f"{path} must define __version__ as a string literal.")


def _safe_member_name(name: str) -> str:
    if not name or "\x00" in name or name.startswith(("/", "\\")) or "\\" in name:
        raise ReleaseContractError(f"Unsafe archive member path: {name!r}")
    path = PurePosixPath(name)
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ReleaseContractError(f"Unsafe archive member path: {name!r}")
    return path.as_posix()


def _safe_relative_path(value: str, *, description: str) -> PurePosixPath:
    if not value or "\x00" in value or value.startswith(("/", "\\")) or "\\" in value:
        raise ReleaseContractError(f"Unsafe {description}: {value!r}")
    path = PurePosixPath(value)
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ReleaseContractError(f"Unsafe {description}: {value!r}")
    return path


def _validate_tar_members(archive: tarfile.TarFile) -> tuple[list[tarfile.TarInfo], str]:
    members = archive.getmembers()
    if not members:
        raise ReleaseContractError("Release archive is empty.")

    seen: set[str] = set()
    top_levels: set[str] = set()
    for member in members:
        name = _safe_member_name(member.name)
        if name in seen:
            raise ReleaseContractError(f"Archive contains a duplicate member: {name}")
        seen.add(name)
        top_levels.add(PurePosixPath(name).parts[0])
        if member.issym() or member.islnk():
            raise ReleaseContractError(f"Archive contains a symlink or hard link: {name}")
        if not (member.isfile() or member.isdir()):
            raise ReleaseContractError(f"Archive contains an unsupported special file: {name}")
        if member.mode & 0o6000:
            raise ReleaseContractError(f"Archive contains setuid/setgid content: {name}")

    if len(top_levels) != 1:
        raise ReleaseContractError("Archive must contain exactly one top-level release directory.")
    return members, next(iter(top_levels))


def _extract_validated_archive(archive_path: Path) -> tuple[Path, Path]:
    workspace = Path(tempfile.mkdtemp(prefix="visiondesk-release-verify-"))
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            members, root_name = _validate_tar_members(archive)
            for member in members:
                if sys.version_info >= (3, 12):
                    archive.extract(member, path=workspace, set_attrs=False, filter="fully_trusted")
                else:
                    archive.extract(member, path=workspace, set_attrs=False)
        release_root = workspace / root_name
        if not release_root.is_dir():
            raise ReleaseContractError("Archive top-level entry is not a release directory.")
        return workspace, release_root
    except Exception:
        shutil.rmtree(workspace, ignore_errors=True)
        raise


def _validate_no_forbidden_paths(release_root: Path) -> None:
    for path in release_root.rglob("*"):
        relative = path.relative_to(release_root)
        if path.name == ".env" or path.suffix == ".pyc" or any(
            part in FORBIDDEN_PARTS for part in relative.parts
        ):
            raise ReleaseContractError(f"Forbidden release path: {relative.as_posix()}")


def _load_manifest(release_root: Path) -> tuple[dict[str, Any], str, Path]:
    manifest_path = release_root / "manifest.json"
    if not manifest_path.is_file():
        raise ReleaseContractError("Release root is missing manifest.json.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseContractError(f"Could not read manifest.json: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ReleaseContractError("manifest.json must contain a JSON object.")

    raw_version = manifest.get("version")
    if not isinstance(raw_version, str) or not raw_version.strip():
        raise ReleaseContractError("manifest.json must contain a non-empty string version.")
    version = normalize_version(raw_version)
    if raw_version.strip() != version:
        raise ReleaseContractError("manifest.json version must not use a leading 'v'.")

    raw_checksums = manifest.get("checksums_file", "checksums.sha256")
    if not isinstance(raw_checksums, str) or not raw_checksums.strip():
        raise ReleaseContractError("manifest.json checksums_file must be a non-empty string.")
    checksum_relative = _safe_relative_path(
        raw_checksums.strip(), description="manifest checksums_file"
    )
    if checksum_relative.as_posix() != "checksums.sha256":
        raise ReleaseContractError("Published packages must use checksums.sha256 at the release root.")
    checksum_path = release_root.joinpath(*checksum_relative.parts)
    if not checksum_path.is_file():
        raise ReleaseContractError(f"Release root is missing checksum file: {checksum_relative}")
    return manifest, version, checksum_path


def _validate_layout(release_root: Path, version: str) -> None:
    if release_root.name != f"visiondesk-{version}":
        raise ReleaseContractError(
            f"Release directory must be visiondesk-{version}, found {release_root.name!r}."
        )

    top_level = {path.name for path in release_root.iterdir()}
    unexpected = sorted(top_level - RELEASE_TOP_LEVEL)
    if unexpected:
        raise ReleaseContractError("Unexpected release root path(s): " + ", ".join(unexpected))

    missing = [path for path in REQUIRED_PATHS if not (release_root / path).is_file()]
    if missing:
        raise ReleaseContractError("Release is missing required file(s): " + ", ".join(missing))

    source_version = read_version_file(release_root / "visiondesk" / "version.py")
    if source_version != version:
        raise ReleaseContractError(
            f"Release code version {source_version} does not match manifest version {version}."
        )


def _validate_checksums(release_root: Path, checksum_path: Path) -> int:
    try:
        lines = checksum_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ReleaseContractError(f"Could not read checksums.sha256: {exc}") from exc
    if not lines:
        raise ReleaseContractError("checksums.sha256 is empty.")

    declared: dict[str, str] = {}
    for line in lines:
        match = CHECKSUM_PATTERN.fullmatch(line)
        if match is None:
            raise ReleaseContractError("Invalid checksums.sha256 line format.")
        digest, raw_name = match.groups()
        relative = _safe_relative_path(raw_name[2:], description="checksum file path")
        normalized = relative.as_posix()
        if normalized == "checksums.sha256":
            raise ReleaseContractError("checksums.sha256 must not checksum itself.")
        if normalized in declared:
            raise ReleaseContractError(f"Duplicate checksum entry: {normalized}")
        declared[normalized] = digest

    actual_files = {
        path.relative_to(release_root).as_posix()
        for path in release_root.rglob("*")
        if path.is_file() and path != checksum_path
    }
    declared_files = set(declared)
    if declared_files != actual_files:
        missing = sorted(actual_files - declared_files)
        extra = sorted(declared_files - actual_files)
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise ReleaseContractError("checksums.sha256 must cover every release file: " + "; ".join(details))

    for relative, expected_digest in declared.items():
        digest = hashlib.sha256((release_root / relative).read_bytes()).hexdigest()
        if digest != expected_digest:
            raise ReleaseContractError(f"Checksum mismatch: {relative}")
    return len(declared)


def verify_archive(archive_path: str | Path, *, expected_version: str | None = None) -> dict[str, str | int]:
    """Validate a publishable appliance archive without installing anything."""
    archive = Path(archive_path).expanduser().resolve()
    if not archive.is_file():
        raise ReleaseContractError(f"Archive was not found: {archive}")

    workspace, release_root = _extract_validated_archive(archive)
    try:
        _validate_no_forbidden_paths(release_root)
        _manifest, version, checksum_path = _load_manifest(release_root)
        _validate_layout(release_root, version)
        checksum_count = _validate_checksums(release_root, checksum_path)
        if expected_version is not None and version != normalize_version(expected_version):
            raise ReleaseContractError(
                f"Archive version {version} does not match expected version {normalize_version(expected_version)}."
            )
        return {
            "archive": str(archive),
            "release_root": release_root.name,
            "version": version,
            "checksummed_files": checksum_count,
        }
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate VisionDesk release archive content.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify", help="Validate an archive without installing it.")
    verify.add_argument("--archive", required=True, help="Path to a .tar.gz release archive.")
    verify.add_argument("--expected-version", help="Expected application version, optionally prefixed with v.")

    read_version = subparsers.add_parser("read-version", help="Read a static __version__ literal.")
    read_version.add_argument("--file", required=True, help="Path to visiondesk/version.py.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "read-version":
            print(read_version_file(Path(args.file)))
            return 0
        result = verify_archive(args.archive, expected_version=args.expected_version)
    except ReleaseContractError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    print(
        "[OK] Release archive verified: "
        f"version={result['version']} root={result['release_root']} "
        f"checksummed_files={result['checksummed_files']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
