"""Tests for the shared VisionDesk factory-reset backend."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from config import load_device_settings, update_device_config
from system.factory_reset import (
    CONFIGURATION_RESET,
    FULL_FACTORY_RESET,
    USER_DATA_RESET,
    FactoryResetExecutionGuard,
    FactoryResetError,
    load_reset_marker,
    main,
    plan_factory_reset,
    perform_factory_reset,
    resume_pending_factory_reset,
)
from visiondesk.paths import VisionDeskPaths


def build_paths(tmp_path: Path) -> VisionDeskPaths:
    app_root = tmp_path / "current"
    releases_dir = tmp_path / "releases"
    config_dir = tmp_path / "etc"
    data_dir = tmp_path / "var" / "lib"
    logs_dir = tmp_path / "var" / "log"
    env_file = config_dir / "visiondesk.env"
    config_path = config_dir / "device.yaml"
    template_text = Path("config/device.yaml").read_text(encoding="utf-8")

    (app_root / "config").mkdir(parents=True, exist_ok=True)
    (app_root / "config" / "device.yaml").write_text(template_text, encoding="utf-8")
    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text(template_text, encoding="utf-8")

    return VisionDeskPaths(
        path_mode="production",
        repo_root=tmp_path,
        app_root=app_root,
        releases_dir=releases_dir,
        current_release_link=app_root,
        config_dir=config_dir,
        config_path=config_path,
        data_dir=data_dir,
        logs_dir=logs_dir,
        env_file_path=env_file,
    )


def seed_user_data(paths: VisionDeskPaths) -> None:
    paths.private_current_path.mkdir(parents=True, exist_ok=True)
    paths.private_retry_path.mkdir(parents=True, exist_ok=True)
    paths.private_cache_path.mkdir(parents=True, exist_ok=True)
    paths.private_quarantine_path.mkdir(parents=True, exist_ok=True)
    (paths.private_current_path / "capture.jpg").write_text("capture", encoding="utf-8")
    (paths.private_retry_path / "queued.json").write_text("retry", encoding="utf-8")
    (paths.private_cache_path / "preview.bin").write_text("cache", encoding="utf-8")
    (paths.private_quarantine_path / "bad.txt").write_text("quarantine", encoding="utf-8")
    paths.result_history_path.write_text("[]", encoding="utf-8")
    paths.latest_result_path.write_text("latest", encoding="utf-8")
    paths.offline_retry_queue_path.write_text("[]", encoding="utf-8")


def test_configuration_reset_clears_openai_and_restores_setup_state(tmp_path) -> None:
    paths = build_paths(tmp_path)
    paths.env_file_path.write_text("OPENAI_API_KEY=sk-test-123\nOTHER=1\n", encoding="utf-8")
    update_device_config(
        {
            "setup": {"completed": True, "completed_at": "2026-07-12T12:00:00", "version": 1},
            "network": {"wifi": {"ssid": "Office", "connection_name": "Office"}},
        },
        config_path=paths.config_path,
    )
    paths.setup_state_path.write_text('{"setup_complete": true}', encoding="utf-8")
    paths.result_history_path.write_text("[]", encoding="utf-8")

    summary = perform_factory_reset(mode=CONFIGURATION_RESET, paths=paths)

    assert summary.mode == CONFIGURATION_RESET
    assert summary.setup_required is True
    assert "OPENAI_API_KEY" not in paths.env_file_path.read_text(encoding="utf-8")
    restored_config = load_device_settings(config_path=paths.config_path)
    assert restored_config.setup.completed is False
    setup_state = json.loads(paths.setup_state_path.read_text(encoding="utf-8"))
    assert setup_state["setup_complete"] is False
    assert setup_state["current_step"] == "welcome"
    assert paths.result_history_path.exists()


def test_user_data_reset_preserves_setup_and_secrets(tmp_path) -> None:
    paths = build_paths(tmp_path)
    paths.env_file_path.write_text("OPENAI_API_KEY=sk-test-123\n", encoding="utf-8")
    update_device_config(
        {
            "setup": {"completed": True, "completed_at": "2026-07-12T12:00:00", "version": 1},
        },
        config_path=paths.config_path,
    )
    paths.setup_state_path.write_text('{"setup_complete": true, "current_step": "finish"}', encoding="utf-8")
    seed_user_data(paths)

    summary = perform_factory_reset(mode=USER_DATA_RESET, paths=paths)

    assert summary.mode == USER_DATA_RESET
    assert summary.setup_required is False
    assert "OPENAI_API_KEY=sk-test-123" in paths.env_file_path.read_text(encoding="utf-8")
    assert paths.setup_state_path.exists()
    assert not paths.latest_result_path.exists()
    assert not paths.result_history_path.exists()
    assert not paths.offline_retry_queue_path.exists()
    assert not paths.private_current_path.exists()
    assert not paths.private_retry_path.exists()
    assert not paths.private_cache_path.exists()
    assert list(paths.private_quarantine_path.iterdir()) == []


def test_full_factory_reset_can_remove_wifi_profile(tmp_path) -> None:
    paths = build_paths(tmp_path)
    update_device_config(
        {
            "network": {"wifi": {"ssid": "Office", "connection_name": "Office"}},
            "setup": {"completed": True, "completed_at": "2026-07-12T12:00:00", "version": 1},
        },
        config_path=paths.config_path,
    )
    seed_user_data(paths)
    settings = load_device_settings(config_path=paths.config_path)
    calls: list[list[str]] = []

    def fake_runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="deleted", stderr="")

    summary = perform_factory_reset(
        mode=FULL_FACTORY_RESET,
        paths=paths,
        settings=settings,
        remove_wifi_profile=True,
        runner=fake_runner,
    )

    assert summary.mode == FULL_FACTORY_RESET
    assert summary.removed_wifi_profile is True
    assert calls == [["nmcli", "connection", "delete", "Office"]]
    assert json.loads(paths.setup_state_path.read_text(encoding="utf-8"))["setup_complete"] is False
    assert not paths.result_history_path.exists()


def test_failed_reset_writes_recovery_marker_and_resume_clears_it(tmp_path) -> None:
    paths = build_paths(tmp_path)
    missing_template = paths.app_root / "config" / "device.yaml"
    missing_template.unlink()

    with pytest.raises(FactoryResetError):
        perform_factory_reset(mode=CONFIGURATION_RESET, paths=paths)

    marker = load_reset_marker(paths.reset_marker_path)
    assert marker is not None
    assert marker["status"] == "failed"

    template_text = Path("config/device.yaml").read_text(encoding="utf-8")
    missing_template.write_text(template_text, encoding="utf-8")
    summary = resume_pending_factory_reset(paths=paths)

    assert summary is not None
    assert summary.mode == CONFIGURATION_RESET
    assert load_reset_marker(paths.reset_marker_path) is None


def test_cli_rejected_confirmation_performs_no_reset(monkeypatch) -> None:
    reset = Mock()
    monkeypatch.setattr("system.factory_reset.perform_factory_reset", reset)
    monkeypatch.setattr("builtins.input", lambda _: "NO")

    assert main(["--mode", USER_DATA_RESET]) == 1

    reset.assert_not_called()


def test_cli_accepted_confirmation_performs_reset_once(monkeypatch) -> None:
    reset = Mock(return_value=plan_factory_reset(mode=USER_DATA_RESET))
    monkeypatch.setattr("system.factory_reset.perform_factory_reset", reset)
    monkeypatch.setattr("builtins.input", lambda _: "YES")

    assert main(["--mode", USER_DATA_RESET]) == 0

    reset.assert_called_once_with(mode=USER_DATA_RESET, remove_wifi_profile=False)


def test_cli_yes_performs_reset_once(monkeypatch) -> None:
    reset = Mock(return_value=plan_factory_reset(mode=USER_DATA_RESET))
    monkeypatch.setattr("system.factory_reset.perform_factory_reset", reset)

    assert main(["--mode", USER_DATA_RESET, "--yes"]) == 0

    reset.assert_called_once_with(mode=USER_DATA_RESET, remove_wifi_profile=False)


def test_cli_dry_run_performs_no_reset(monkeypatch) -> None:
    reset = Mock()
    monkeypatch.setattr("system.factory_reset.perform_factory_reset", reset)

    assert main(["--mode", USER_DATA_RESET, "--dry-run"]) == 0

    reset.assert_not_called()


def test_cli_eof_confirmation_performs_no_reset(monkeypatch) -> None:
    reset = Mock()
    monkeypatch.setattr("system.factory_reset.perform_factory_reset", reset)

    def raise_eof(_: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)

    assert main(["--mode", USER_DATA_RESET]) == 1

    reset.assert_not_called()


def test_factory_reset_execution_guard_rejects_duplicate_callback() -> None:
    summary = plan_factory_reset(mode=USER_DATA_RESET)
    callback = Mock(return_value=summary)
    guard = FactoryResetExecutionGuard()

    assert guard.execute(callback) is summary
    with pytest.raises(FactoryResetError, match="already requested"):
        guard.execute(callback)

    callback.assert_called_once_with()
