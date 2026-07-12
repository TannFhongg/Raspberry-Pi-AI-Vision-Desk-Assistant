"""Shared setup-flow and Qt setup controller tests."""

from __future__ import annotations

import importlib.util
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
    paths = RuntimePaths(
        setup_state_path=tmp_path / "setup_state.json",
        health_status_path=tmp_path / "health_status.json",
        latest_result_path=tmp_path / "latest_result.txt",
        result_history_path=tmp_path / "result_history.json",
        private_data_path=tmp_path / "private",
        env_file_path=tmp_path / ".env",
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
def test_finish_setup_marks_config_and_clears_setup_temp_state(tmp_path) -> None:
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
                "message": "OpenAI reachable.",
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
    assert not runtime.paths.setup_state_path.exists()
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
        "hardware.device_check.check_openai_reachable",
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
                "message": "OpenAI is reachable.",
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
