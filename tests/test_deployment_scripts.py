"""Static checks for the commercial deployment shell scripts."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from system.readiness import write_readiness_marker


def test_install_script_includes_expected_flags_and_safety_guards() -> None:
    script_text = Path("install.sh").read_text(encoding="utf-8")

    assert "--non-interactive" in script_text
    assert "--skip-hardware-check" in script_text
    assert "--reset-config" in script_text
    assert "--force" in script_text
    assert "visiondesk.service" in script_text
    assert "NetworkManager" in script_text
    assert "49-visiondesk-networkmanager.rules" in script_text
    assert "install_networkmanager_policy" in script_text
    assert "ensure_path_within" in script_text
    assert "rollback_on_failure" in script_text
    assert '"${SCRIPT_DIR}/system/__init__.py"' in script_text
    assert '"${SCRIPT_DIR}/system/diagnostics.py"' in script_text
    assert "app_user_graphical_session_ready" in script_text
    assert "systemctl stop visiondesk.service" in script_text
    assert "Reboot required before the VisionDesk UI can start" in script_text
    assert 'LIGHTDM_MAIN_CONF="/etc/lightdm/lightdm.conf"' in script_text
    assert "LightDM loads its main configuration after lightdm.conf.d" in script_text
    assert "python3 -m compileall -q" in script_text
    assert '"${STAGING_RELEASE_DIR}/qt_app"' in script_text


def test_install_smoke_checks_run_from_staged_release() -> None:
    script_text = Path("install.sh").read_text(encoding="utf-8")
    smoke_check = script_text.split("run_smoke_checks() {", 1)[1].split("\n}", 1)[0]

    working_directory = 'cd "${FINAL_RELEASE_DIR}"'
    diagnostics_command = '"${FINAL_RELEASE_DIR}/.venv/bin/python" -m system.diagnostics'
    assert working_directory in smoke_check
    assert diagnostics_command in smoke_check
    assert smoke_check.index(working_directory) < smoke_check.index(diagnostics_command)


def test_diagnostics_module_does_not_load_twice() -> None:
    completed = subprocess.run(
        [sys.executable, "-W", "error::RuntimeWarning", "-m", "system.diagnostics", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


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
    assert "readiness.json" in script_text
    assert "wait_for_application_readiness" in script_text
    assert "wait_for_service_stability" in script_text
    assert "NRestarts" in script_text
    assert "MainPID" in script_text
    assert "Rollback service did not reach verified readiness" in script_text
    assert "switch_current_release" in script_text
    assert 'cd "${STAGING_RELEASE_DIR}"' in script_text
    assert 'activate_release_unit "${FINAL_RELEASE_DIR}"' in script_text
    assert 'activate_release_unit "${PREVIOUS_CURRENT_TARGET}"' in script_text
    assert 'activate_release_unit "${PREVIOUS_RELEASE}"' in script_text
    assert "systemctl daemon-reload" in script_text
    assert '"${PYTHON_BIN}" -m compileall -q' in script_text


@pytest.mark.skipif(
    os.name == "nt" or shutil.which("bash") is None or shutil.which("python3") is None,
    reason="the sourced-shell update integration harness requires a native Linux bash environment",
)
def test_update_readiness_validator_runs_safely_against_marker_fixtures(tmp_path) -> None:
    """Exercise update.sh marker validation without systemd, releases, or live symlinks."""
    marker_path = tmp_path / "runtime" / "readiness.json"
    write_readiness_marker(
        marker_path,
        version="1.0.1",
        state="READY",
        qml_loaded=True,
        pid=4321,
        now=datetime.now(timezone.utc),
    )
    command = (
        'source "$UPDATE_SCRIPT"; READINESS_FILE="$READINESS_MARKER"; READINESS_MAX_AGE_SECONDS=60; '
        'validate_readiness_marker "$EXPECTED_VERSION" "$EXPECTED_PID"'
    )
    environment = {
        **os.environ,
        "UPDATE_SCRIPT": str(Path("update.sh").resolve()),
        "READINESS_MARKER": str(marker_path),
        "EXPECTED_PID": "4321",
    }
    healthy = subprocess.run(
        ["bash", "-c", command],
        check=False,
        capture_output=True,
        text=True,
        env={**environment, "EXPECTED_VERSION": "1.0.1"},
    )
    wrong_version = subprocess.run(
        ["bash", "-c", command],
        check=False,
        capture_output=True,
        text=True,
        env={**environment, "EXPECTED_VERSION": "9.9.9"},
    )

    assert healthy.returncode == 0, healthy.stderr
    assert wrong_version.returncode != 0


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
    assert "49-visiondesk-networkmanager.rules" in script_text


def test_networkmanager_policy_is_limited_to_setup_actions_for_visiondesk_group() -> None:
    policy_text = Path("deployment/49-visiondesk-networkmanager.rules").read_text(encoding="utf-8")

    assert 'subject.isInGroup("visiondesk")' in policy_text
    assert "org.freedesktop.NetworkManager.network-control" in policy_text
    assert "org.freedesktop.NetworkManager.settings.modify.system" in policy_text
    assert "org.freedesktop.NetworkManager.wifi.scan" in policy_text
    assert "org.freedesktop.NetworkManager.wifi.share.protected" in policy_text


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
