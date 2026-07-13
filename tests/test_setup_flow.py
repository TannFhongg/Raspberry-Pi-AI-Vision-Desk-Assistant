"""Shared setup-flow and Qt setup controller tests."""

from __future__ import annotations

import importlib.util
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from system.device_setup import upsert_env_value
from system.setup_flow import finish_setup, run_setup_openai_key, run_setup_wifi_connect

PY_SIDE6_AVAILABLE = importlib.util.find_spec("PySide6") is not None

if PY_SIDE6_AVAILABLE:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QSignalSpy

    from qt_app.runtime import RuntimePaths, VisionDeskRuntime
    from qt_app.setup_controller import SetupController


if PY_SIDE6_AVAILABLE:

    @pytest.fixture(scope="session")
    def qapp():
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app


def build_runtime(tmp_path: Path, *, setup_completed: bool = False) -> VisionDeskRuntime:
    """Create an isolated runtime for setup-flow tests."""
    assert PY_SIDE6_AVAILABLE
    config_template = Path("config/device.yaml").read_text(encoding="utf-8")
    config_path = tmp_path / "device.yaml"
    config_path.write_text(config_template, encoding="utf-8")
    app_root = tmp_path / "app_root"
    (app_root / "config").mkdir(parents=True, exist_ok=True)
    (app_root / "config" / "device.yaml").write_text(config_template, encoding="utf-8")
    paths = RuntimePaths(
        path_mode="development",
        repo_root=tmp_path,
        releases_dir=tmp_path / "releases",
        setup_state_path=tmp_path / "setup_state.json",
        health_status_path=tmp_path / "health_status.json",
        latest_result_path=tmp_path / "latest_result.txt",
        result_history_path=tmp_path / "result_history.json",
        private_data_path=tmp_path / "private",
        env_file_path=tmp_path / ".env",
        config_path=config_path,
        logs_dir=tmp_path / "logs",
        app_root=app_root,
    )
    runtime = VisionDeskRuntime(
        mock_hardware=True,
        paths=paths,
        purge_on_startup=False,
    )
    runtime.settings.setup.completed = setup_completed
    runtime.settings.setup.completed_at = ""
    runtime.settings.setup.version = 1 if setup_completed else 0
    runtime.settings.config_path = tmp_path / "device.yaml"
    runtime.settings.retention.purge_on_startup = False
    return runtime


@pytest.mark.skipif(not PY_SIDE6_AVAILABLE, reason="PySide6 is not installed")
def test_setup_state_defaults_to_welcome_when_authoritative_file_is_missing(tmp_path) -> None:
    runtime = build_runtime(tmp_path)

    state = runtime.setup_state_store.load_state()

    assert state["setup_complete"] is False
    assert state["current_step"] == "welcome"
    runtime.shutdown()


@pytest.mark.skipif(not PY_SIDE6_AVAILABLE, reason="PySide6 is not installed")
def test_run_setup_wifi_connect_persists_network_metadata_and_advances_step(tmp_path) -> None:
    runtime = build_runtime(tmp_path)
    updated_configs: list[dict[str, object]] = []

    run_setup_wifi_connect(
        runtime.setup_state_store,
        selected_ssid="Office",
        manual_ssid="",
        password="topsecret",
        connection_name="Office",
        connect_wifi_network=lambda **kwargs: {
            "ssid": kwargs["ssid"],
            "connection_name": kwargs["connection_name"],
            "message": "Connected to Wi-Fi network 'Office'.",
        },
        update_device_config=updated_configs.append,
    )

    state = runtime.setup_state_store.load_state()
    assert state["current_step"] == "openai"
    assert state["wifi"]["connect_status"] == "pass"
    assert state["wifi"]["ssid"] == "Office"
    assert updated_configs == [
        {
            "network": {
                "wifi": {
                    "ssid": "Office",
                    "connection_name": "Office",
                    "auto_connect": True,
                    "managed_by": "nmcli",
                }
            }
        }
    ]
    runtime.shutdown()


@pytest.mark.skipif(not PY_SIDE6_AVAILABLE, reason="PySide6 is not installed")
def test_run_setup_openai_key_rejects_invalid_keys(tmp_path) -> None:
    runtime = build_runtime(tmp_path)

    run_setup_openai_key(
        runtime.setup_state_store,
        api_key="invalid-key",
        env_file_path=runtime.paths.env_file_path,
        upsert_env_value=upsert_env_value,
        check_openai_reachable=lambda: SimpleNamespace(passed=True, message="unused"),
    )

    state = runtime.setup_state_store.load_state()
    assert state["current_step"] == "openai"
    assert state["openai"]["status"] == "fail"
    assert "starting with sk-" in state["openai"]["message"]
    assert not runtime.paths.env_file_path.exists()
    runtime.shutdown()


@pytest.mark.skipif(not PY_SIDE6_AVAILABLE, reason="PySide6 is not installed")
def test_finish_setup_marks_config_and_persists_authoritative_setup_state(tmp_path) -> None:
    runtime = build_runtime(tmp_path)
    runtime.setup_state_store.write_state(
        {
            "current_step": "finish",
            "wifi": {
                "connect_status": "pass",
                "ssid": "Office",
                "connection_name": "Office",
                "message": "Connected.",
            },
            "openai": {
                "status": "pass",
                "key_present": True,
                "api_key_verified": True,
                "message": "OpenAI reachable.",
            },
            "camera": {
                "status": "pass",
                "message": "Camera ready.",
            },
            "gpio": {
                "status": "pass",
                "message": "GPIO ready.",
                "required": [{"label": "capture", "pin": 17, "pressed": True}],
                "pressed_labels": ["capture"],
                "all_pressed": True,
            },
        }
    )
    updated_configs: list[dict[str, object]] = []
    completions: list[str] = []

    succeeded = finish_setup(
        runtime.setup_state_store,
        update_device_config=updated_configs.append,
        on_completed=completions.append,
    )

    assert succeeded is True
    assert len(updated_configs) == 1
    assert updated_configs[0]["setup"]["completed"] is True
    assert updated_configs[0]["localization"]["locale"] == "en"
    assert len(completions) == 1
    persisted_state = runtime.setup_state_store.load_state()
    assert persisted_state["setup_complete"] is True
    assert persisted_state["app_version"] == runtime.app_version
    runtime.shutdown()


@pytest.mark.skipif(not PY_SIDE6_AVAILABLE, reason="PySide6 is not installed")
def test_setup_controller_scan_wifi_updates_model(qapp, qtbot, tmp_path, monkeypatch) -> None:
    runtime = build_runtime(tmp_path)
    controller = SetupController(runtime)
    monkeypatch.setattr(
        "qt_app.setup_controller.scan_wifi_networks",
        lambda: [
            {"ssid": "Office", "signal": 82, "security": "WPA2"},
            {"ssid": "Guest", "signal": 40, "security": "open"},
        ],
    )

    controller.scanWifi()

    qtbot.waitUntil(
        lambda: controller.wifiNetworksModel.count == 2 and controller.wifiScanStatus == "pass",
        timeout=3000,
    )
    assert "Found 2 Wi-Fi networks" in controller.wifiMessage
    controller.close()
    runtime.shutdown()


@pytest.mark.skipif(not PY_SIDE6_AVAILABLE, reason="PySide6 is not installed")
def test_setup_controller_verify_api_key_updates_state(qapp, qtbot, tmp_path, monkeypatch) -> None:
    runtime = build_runtime(tmp_path)
    controller = SetupController(runtime)
    monkeypatch.setattr(
        "qt_app.setup_controller.check_openai_reachable",
        lambda: SimpleNamespace(passed=True, message="OpenAI is reachable."),
    )

    controller.verifyApiKey("sk-test-key-123")

    qtbot.waitUntil(lambda: controller.openAiStatus == "pass", timeout=3000)
    assert "OpenAI is reachable." in controller.openAiMessage
    assert "OPENAI_API_KEY=sk-test-key-123" in runtime.paths.env_file_path.read_text(encoding="utf-8")
    controller.close()
    runtime.shutdown()


@pytest.mark.skipif(not PY_SIDE6_AVAILABLE, reason="PySide6 is not installed")
def test_setup_controller_finish_setup_emits_completion(qapp, qtbot, tmp_path, monkeypatch) -> None:
    runtime = build_runtime(tmp_path)
    controller = SetupController(runtime)
    setup_completed_spy = QSignalSpy(controller.setupCompleted)
    updated_configs: list[dict[str, object]] = []
    monkeypatch.setattr(
        "qt_app.setup_controller.update_device_config",
        lambda payload, config_path: updated_configs.append(payload),
    )
    runtime.setup_state_store.write_state(
        {
            "current_step": "finish",
            "wifi": {
                "connect_status": "pass",
                "ssid": "Office",
                "connection_name": "Office",
                "message": "Connected.",
            },
            "openai": {
                "status": "pass",
                "key_present": True,
                "api_key_verified": True,
                "message": "OpenAI is reachable.",
            },
            "camera": {
                "status": "pass",
                "message": "Camera ready.",
            },
            "gpio": {
                "status": "pass",
                "message": "GPIO ready.",
                "required": [{"label": "capture", "pin": 17, "pressed": True}],
                "pressed_labels": ["capture"],
                "all_pressed": True,
            },
        }
    )
    controller.refresh_state()

    controller.finishSetup()

    qtbot.waitUntil(lambda: setup_completed_spy.count() == 1, timeout=2000)
    assert runtime.settings.setup.completed is True
    assert len(updated_configs) == 1
    assert updated_configs[0]["setup"]["completed"] is True
    controller.close()
    runtime.shutdown()


@pytest.mark.skipif(not PY_SIDE6_AVAILABLE, reason="PySide6 is not installed")
def test_setup_state_store_concurrent_updates_preserve_both_fields(tmp_path) -> None:
    runtime = build_runtime(tmp_path)
    barrier = threading.Barrier(3)

    def write_wifi() -> None:
        barrier.wait()
        runtime.setup_state_store.update_state({"wifi": {"ssid": "Office"}})

    def write_camera() -> None:
        barrier.wait()
        runtime.setup_state_store.update_state({"camera": {"status": "pass"}})

    wifi_thread = threading.Thread(target=write_wifi)
    camera_thread = threading.Thread(target=write_camera)
    wifi_thread.start()
    camera_thread.start()
    barrier.wait()
    wifi_thread.join(timeout=2.0)
    camera_thread.join(timeout=2.0)

    state = runtime.setup_state_store.load_state()
    assert state["wifi"]["ssid"] == "Office"
    assert state["camera"]["status"] == "pass"
    runtime.shutdown()


@pytest.mark.skipif(not PY_SIDE6_AVAILABLE, reason="PySide6 is not installed")
def test_setup_controller_ignores_second_wifi_scan_while_active(qapp, qtbot, tmp_path, monkeypatch) -> None:
    runtime = build_runtime(tmp_path)
    controller = SetupController(runtime)
    started = threading.Event()
    release = threading.Event()
    calls: list[str] = []

    def scan() -> list[dict[str, object]]:
        calls.append("scan")
        started.set()
        assert release.wait(timeout=2.0)
        return [{"ssid": "Office", "signal": 80, "security": "WPA2"}]

    monkeypatch.setattr("qt_app.setup_controller.scan_wifi_networks", scan)

    controller.scanWifi()
    qtbot.waitUntil(started.is_set, timeout=1000)
    controller.scanWifi()

    assert calls == ["scan"]
    release.set()
    qtbot.waitUntil(lambda: not controller.setupBusy and controller.wifiScanStatus == "pass", timeout=3000)
    controller.close()
    runtime.shutdown()


@pytest.mark.skipif(not PY_SIDE6_AVAILABLE, reason="PySide6 is not installed")
def test_stale_api_verification_cannot_overwrite_newer_wifi_scan(qapp, qtbot, tmp_path, monkeypatch) -> None:
    runtime = build_runtime(tmp_path)
    controller = SetupController(runtime)
    api_started = threading.Event()
    release_api = threading.Event()

    def verify():
        api_started.set()
        assert release_api.wait(timeout=2.0)
        return SimpleNamespace(passed=True, message="OpenAI is reachable.")

    monkeypatch.setattr("qt_app.setup_controller.check_openai_reachable", verify)
    monkeypatch.setattr(
        "qt_app.setup_controller.scan_wifi_networks",
        lambda: [{"ssid": "Office", "signal": 80, "security": "WPA2"}],
    )

    controller.verifyApiKey("sk-test-key-123")
    qtbot.waitUntil(api_started.is_set, timeout=1000)
    controller.scanWifi()
    qtbot.waitUntil(lambda: controller.wifiScanStatus == "pass", timeout=3000)
    release_api.set()
    qtbot.waitUntil(lambda: not controller.setupBusy, timeout=3000)

    state = runtime.setup_state_store.load_state()
    assert state["current_step"] == "wifi"
    assert state["wifi"]["scan_status"] == "pass"
    assert state["openai"]["message"] != "OpenAI is reachable."
    controller.close()
    runtime.shutdown()


@pytest.mark.skipif(not PY_SIDE6_AVAILABLE, reason="PySide6 is not installed")
def test_setup_worker_exception_clears_busy_flag(qapp, qtbot, tmp_path, monkeypatch) -> None:
    runtime = build_runtime(tmp_path)
    controller = SetupController(runtime)

    def fail_scan() -> list[dict[str, object]]:
        raise RuntimeError("scan failed")

    monkeypatch.setattr("qt_app.setup_controller.scan_wifi_networks", fail_scan)

    controller.scanWifi()

    qtbot.waitUntil(lambda: not controller.setupBusy, timeout=3000)
    controller.close()
    runtime.shutdown()


@pytest.mark.skipif(not PY_SIDE6_AVAILABLE, reason="PySide6 is not installed")
def test_finish_setup_cannot_run_twice(qapp, qtbot, tmp_path, monkeypatch) -> None:
    runtime = build_runtime(tmp_path)
    controller = SetupController(runtime)
    started = threading.Event()
    release = threading.Event()
    calls: list[str] = []

    def finish(store, **kwargs) -> bool:
        del store, kwargs
        calls.append("finish")
        started.set()
        assert release.wait(timeout=2.0)
        return False

    monkeypatch.setattr("qt_app.setup_controller.finish_setup", finish)

    controller.finishSetup()
    qtbot.waitUntil(started.is_set, timeout=1000)
    controller.finishSetup()

    assert calls == ["finish"]
    release.set()
    qtbot.waitUntil(lambda: not controller.setupBusy, timeout=3000)
    controller.close()
    runtime.shutdown()
