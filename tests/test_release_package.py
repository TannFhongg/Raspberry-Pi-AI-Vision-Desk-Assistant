"""Release-package contract tests that run without Raspberry Pi hardware."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tarfile
from io import BytesIO
from pathlib import Path

import pytest


def _load_contract_module():
    module_path = Path("scripts/release_contract.py").resolve()
    spec = importlib.util.spec_from_file_location("visiondesk_release_contract", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


release_contract = _load_contract_module()


def _write_release_file(path: Path, relative: str, *, source_version: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if relative == "visiondesk/version.py":
        path.write_text(f'__version__ = "{source_version}"\n', encoding="utf-8")
    elif relative == "requirements.txt":
        path.write_text("PySide6==6.11.1\n", encoding="utf-8")
    elif relative == "config/device.yaml":
        path.write_text("setup:\n  completed: false\n", encoding="utf-8")
    elif relative == "qt_app/qml/Main.qml":
        path.write_text("import QtQuick\nItem {}\n", encoding="utf-8")
    elif relative == "update.sh":
        shutil.copy2(Path("update.sh"), path)
    elif relative.endswith(".sh"):
        path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    elif relative.endswith(".service"):
        path.write_text("[Service]\nExecStart=/bin/true\n", encoding="utf-8")
    else:
        path.write_text("# release fixture\n", encoding="utf-8")


def _write_checksums(release_root: Path) -> None:
    checksum_path = release_root / "checksums.sha256"
    files = sorted(
        path
        for path in release_root.rglob("*")
        if path.is_file() and path != checksum_path
    )
    lines = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  ./{path.relative_to(release_root).as_posix()}")
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _create_release_tree(
    tmp_path: Path,
    *,
    manifest_version: str = "1.0.0",
    source_version: str = "1.0.0",
) -> Path:
    release_root = tmp_path / f"visiondesk-{manifest_version}"
    for relative in release_contract.REQUIRED_PATHS:
        _write_release_file(release_root / relative, relative, source_version=source_version)
    (release_root / "manifest.json").write_text(
        json.dumps(
            {
                "version": manifest_version,
                "checksums_file": "checksums.sha256",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_checksums(release_root)
    return release_root


def _create_archive(release_root: Path, archive_path: Path) -> Path:
    with tarfile.open(archive_path, mode="w:gz") as archive:
        archive.add(release_root, arcname=release_root.name)
    return archive_path


def test_valid_manifest_checksum_and_layout_are_accepted(tmp_path: Path) -> None:
    release_root = _create_release_tree(tmp_path)
    archive = _create_archive(release_root, tmp_path / "visiondesk-1.0.0.tar.gz")

    result = release_contract.verify_archive(archive, expected_version="v1.0.0")

    assert result["version"] == "1.0.0"
    assert result["release_root"] == "visiondesk-1.0.0"
    assert int(result["checksummed_files"]) >= len(release_contract.REQUIRED_PATHS)


def test_checksum_mismatch_is_rejected(tmp_path: Path) -> None:
    release_root = _create_release_tree(tmp_path)
    (release_root / "requirements.txt").write_text("tampered\n", encoding="utf-8")
    archive = _create_archive(release_root, tmp_path / "tampered.tar.gz")

    with pytest.raises(release_contract.ReleaseContractError, match="Checksum mismatch"):
        release_contract.verify_archive(archive)


def test_missing_required_file_is_rejected(tmp_path: Path) -> None:
    release_root = _create_release_tree(tmp_path)
    (release_root / "qt_app" / "main.py").unlink()
    _write_checksums(release_root)
    archive = _create_archive(release_root, tmp_path / "missing-main.tar.gz")

    with pytest.raises(release_contract.ReleaseContractError, match="missing required file"):
        release_contract.verify_archive(archive)


def test_manifest_and_source_version_mismatch_is_rejected(tmp_path: Path) -> None:
    release_root = _create_release_tree(
        tmp_path,
        manifest_version="1.0.1",
        source_version="1.0.0",
    )
    archive = _create_archive(release_root, tmp_path / "version-mismatch.tar.gz")

    with pytest.raises(release_contract.ReleaseContractError, match="does not match manifest version"):
        release_contract.verify_archive(archive)


def test_path_traversal_member_is_rejected(tmp_path: Path) -> None:
    archive_path = tmp_path / "traversal.tar.gz"
    with tarfile.open(archive_path, mode="w:gz") as archive:
        payload = b"not allowed\n"
        info = tarfile.TarInfo("visiondesk-1.0.0/../../.env")
        info.size = len(payload)
        archive.addfile(info, BytesIO(payload))

    with pytest.raises(release_contract.ReleaseContractError, match="Unsafe archive member path"):
        release_contract.verify_archive(archive_path)


def test_dotenv_file_is_rejected_even_if_checksums_are_valid(tmp_path: Path) -> None:
    release_root = _create_release_tree(tmp_path)
    (release_root / ".env").write_text("OPENAI_API_KEY=not-a-real-key\n", encoding="utf-8")
    _write_checksums(release_root)
    archive = _create_archive(release_root, tmp_path / "contains-env.tar.gz")

    with pytest.raises(release_contract.ReleaseContractError, match="Forbidden release path"):
        release_contract.verify_archive(archive)


@pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="release build integration test requires bash and git",
)
def test_build_package_from_v100_tag_has_application_version_100(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    for relative in release_contract.REQUIRED_PATHS:
        _write_release_file(source_root / relative, relative, source_version="1.0.0")

    scripts_dir = source_root / "scripts"
    scripts_dir.mkdir()
    for name in ("build-release.sh", "verify-release.sh", "release_contract.py"):
        shutil.copy2(Path("scripts") / name, scripts_dir / name)

    subprocess.run(["git", "init"], cwd=source_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "release-test@example.invalid"],
        cwd=source_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Release Test"],
        cwd=source_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "core.filemode", "false"],
        cwd=source_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "core.autocrlf", "false"],
        cwd=source_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "add", "."], cwd=source_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "fixture"],
        cwd=source_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "tag", "v1.0.0"], cwd=source_root, check=True, capture_output=True, text=True)

    completed = subprocess.run(
        ["bash", "scripts/build-release.sh"],
        cwd=source_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    archive = source_root / "dist" / "visiondesk-1.0.0.tar.gz"
    assert archive.is_file()
    assert release_contract.verify_archive(archive)["version"] == "1.0.0"
