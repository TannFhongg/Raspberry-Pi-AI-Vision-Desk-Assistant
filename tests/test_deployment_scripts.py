"""Static checks for the commercial deployment shell scripts."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_install_script_includes_expected_flags_and_safety_guards() -> None:
    script_text = Path("install.sh").read_text(encoding="utf-8")

    assert "--non-interactive" in script_text
    assert "--skip-hardware-check" in script_text
    assert "--reset-config" in script_text
    assert "--force" in script_text
    assert "visiondesk.service" in script_text
    assert "NetworkManager" in script_text
    assert "ensure_path_within" in script_text
    assert "rollback_on_failure" in script_text


def test_update_script_uses_manifest_checks_lockfile_and_rollback_state() -> None:
    script_text = Path("update.sh").read_text(encoding="utf-8")

    assert "--check" in script_text
    assert "--version" in script_text
    assert "--local" in script_text
    assert "--rollback" in script_text
    assert "--dry-run" in script_text
    assert "manifest.json" in script_text
    assert "sha256sum -c" in script_text
    assert "update.lock" in script_text
    assert "update-rollback.env" in script_text
    assert "system.migrations" in script_text
    assert "system.diagnostics" in script_text


def test_uninstall_script_supports_preserve_by_default_and_purge_confirmation() -> None:
    script_text = Path("uninstall.sh").read_text(encoding="utf-8")

    assert "--purge" in script_text
    assert "--keep-logs" in script_text
    assert "--yes" in script_text
    assert "--dry-run" in script_text
    assert "PURGE VISIONDESK" in script_text
    assert "Preserve persistent data" in script_text
    assert "safe_remove_tree" in script_text
    assert "systemctl daemon-reload" in script_text


def test_factory_reset_script_wraps_shared_python_backend_and_restart() -> None:
    script_text = Path("factory-reset.sh").read_text(encoding="utf-8")

    assert "system.factory_reset" in script_text
    assert "--mode {configuration|user_data|factory_reset}" in script_text
    assert "--remove-wifi" in script_text
    assert "systemctl restart" in script_text


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is unavailable")
@pytest.mark.parametrize(
    "script_path",
    [
        "install.sh",
        "update.sh",
        "uninstall.sh",
        "factory-reset.sh",
        "deployment/visiondesk-launch.sh",
    ],
)
def test_shell_scripts_parse_with_bash_n(script_path: str) -> None:
    completed = subprocess.run(
        ["bash", "-n", script_path],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
