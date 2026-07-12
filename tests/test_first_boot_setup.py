"""App-level tests for the first-boot setup wizard."""

from __future__ import annotations

import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("ENABLE_GPIO_BUTTON", "0")
os.environ.setdefault("ENABLE_GPIO_LED", "0")
os.environ.setdefault("OFFLINE_RETRY_ENABLED", "0")
os.environ.setdefault("RELIABILITY_HEALTH_MONITOR_ENABLED", "0")

import app as app_module

from hardware.device_check import HardwareCheckResult


class FirstBootSetupTests(unittest.TestCase):
    """Verify the first-boot setup wizard behavior."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="first-boot-setup-test-"))
        self.private_dir = self.temp_dir / "private"
        self.quarantine_dir = self.private_dir / "quarantine"
        self.ui_state_path = self.temp_dir / "ui_state.json"
        self.setup_state_path = self.temp_dir / "setup_state.json"
        self.result_history_path = self.temp_dir / "result_history.json"
        self.health_status_path = self.temp_dir / "health_status.json"
        self.env_path = self.temp_dir / ".env"
        self.config_path = self.temp_dir / "device.yaml"
        self._write_config()

        self.original_setup_completed = app_module.SETTINGS.setup.completed
        self.original_setup_completed_at = app_module.SETTINGS.setup.completed_at
        self.original_setup_version = app_module.SETTINGS.setup.version
        self.original_config_path = app_module.SETTINGS.config_path
        self.original_locale = app_module.SETTINGS.localization.locale
        self.original_openai_key = os.environ.get("OPENAI_API_KEY")
        self.original_wifi_ssid = app_module.SETTINGS.network.wifi.ssid
        self.original_wifi_connection_name = app_module.SETTINGS.network.wifi.connection_name
        self.original_wifi_auto_connect = app_module.SETTINGS.network.wifi.auto_connect
        self.original_wifi_managed_by = app_module.SETTINGS.network.wifi.managed_by

        app_module.SETTINGS.setup.completed = False
        app_module.SETTINGS.setup.completed_at = ""
        app_module.SETTINGS.setup.version = 0
        app_module.SETTINGS.config_path = self.config_path
        app_module.SETTINGS.localization.locale = "en"
        app_module.SETTINGS.network.wifi.ssid = ""
        app_module.SETTINGS.network.wifi.connection_name = ""
        app_module.SETTINGS.network.wifi.auto_connect = True
        app_module.SETTINGS.network.wifi.managed_by = "nmcli"

        self.live_preview = _FakeLivePreview()
        self.patchers = [
            patch.object(app_module, "UI_STATE_PATH", self.ui_state_path),
            patch.object(app_module, "SETUP_STATE_PATH", self.setup_state_path),
            patch.object(app_module, "RESULT_HISTORY_PATH", self.result_history_path),
            patch.object(app_module, "HEALTH_STATUS_PATH", self.health_status_path),
            patch.object(app_module, "PRIVATE_DATA_PATH", self.private_dir),
            patch.object(app_module, "PRIVATE_QUARANTINE_PATH", self.quarantine_dir),
            patch.object(app_module, "ENV_FILE_PATH", self.env_path),
            patch.object(app_module, "LIVE_PREVIEW", self.live_preview),
        ]
        for patcher in self.patchers:
            patcher.start()

        app_module.app.config["TESTING"] = True
        app_module.RESULT_HISTORY_CACHE = None
        app_module.GPIO_TRIGGER = None
        app_module.SETUP_GPIO_VERIFIER = None
        app_module.HEALTH_MONITOR = None
        app_module.OFFLINE_RETRY_QUEUE = None
        app_module.RUNNING = False
        app_module.GPIO_START_ATTEMPTED = False
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        app_module._reset_ui_state(clear_saved_result=False)
        app_module._clear_setup_state()

    def tearDown(self) -> None:
        app_module._stop_setup_gpio_verifier(restart_main_listener=False)
        for patcher in reversed(self.patchers):
            patcher.stop()
        app_module.SETTINGS.setup.completed = self.original_setup_completed
        app_module.SETTINGS.setup.completed_at = self.original_setup_completed_at
        app_module.SETTINGS.setup.version = self.original_setup_version
        app_module.SETTINGS.config_path = self.original_config_path
        app_module.SETTINGS.localization.locale = self.original_locale
        if self.original_openai_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = self.original_openai_key
        app_module.SETTINGS.network.wifi.ssid = self.original_wifi_ssid
        app_module.SETTINGS.network.wifi.connection_name = self.original_wifi_connection_name
        app_module.SETTINGS.network.wifi.auto_connect = self.original_wifi_auto_connect
        app_module.SETTINGS.network.wifi.managed_by = self.original_wifi_managed_by

    def test_setup_gate_redirects_normal_routes_until_complete(self) -> None:
        client = app_module.app.test_client()

        root_response = client.get("/")
        history_response = client.get("/history")
        setup_response = client.get("/setup")

        self.assertEqual(root_response.status_code, 302)
        self.assertTrue(root_response.headers["Location"].endswith("/setup"))
        self.assertEqual(history_response.status_code, 302)
        self.assertTrue(history_response.headers["Location"].endswith("/setup"))
        self.assertEqual(setup_response.status_code, 200)
        self.assertIn(b"Device Setup", setup_response.data)

    def test_setup_screen_renders_first_boot_sections(self) -> None:
        client = app_module.app.test_client()

        response = client.get("/setup")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"1/ WIFI", response.data)
        self.assertIn(b"2/ OPENAI KEY", response.data)
        self.assertIn(b"Connect WIFI", response.data)
        self.assertIn(b"Save and verify the key", response.data)
        self.assertIn(b"FINISH SETUP AND RESTART", response.data)
        self.assertNotIn(b"Run Camera Test", response.data)
        self.assertNotIn(b"Start GPIO Test", response.data)

    def test_setup_screen_keeps_finish_disabled_until_wifi_and_key_pass(self) -> None:
        client = app_module.app.test_client()

        response = client.get("/setup")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"disabled>FINISH SETUP AND RESTART</button>", response.data)
        self.assertIn(b"Connect to Wi-Fi before finishing setup.", response.data)

    def test_services_do_not_start_until_setup_is_complete(self) -> None:
        fake_queue = Mock()
        app_module.OFFLINE_RETRY_QUEUE = fake_queue

        with patch.object(app_module, "ENABLE_GPIO_BUTTON", True), patch.object(
            app_module, "GPIOButtonTrigger"
        ) as gpio_trigger_class, patch.object(app_module, "HealthMonitor") as health_monitor_class:
            app_module._ensure_gpio_button_listener_started()
            app_module._ensure_health_monitor_started()
            app_module._ensure_offline_retry_started()

        gpio_trigger_class.assert_not_called()
        health_monitor_class.assert_not_called()
        fake_queue.start.assert_not_called()

    def test_wifi_scan_route_persists_available_networks(self) -> None:
        client = app_module.app.test_client()
        networks = [
            {"ssid": "Office", "signal": 84, "security": "WPA2"},
            {"ssid": "Guest", "signal": 42, "security": "open"},
        ]

        with patch.object(app_module, "scan_wifi_networks", return_value=networks):
            response = client.post("/setup/wifi/scan")

        self.assertEqual(response.status_code, 302)
        state = app_module._load_setup_state()
        self.assertEqual(state["wifi"]["scan_status"], "pass")
        self.assertEqual(len(state["wifi"]["available_networks"]), 2)
        self.assertEqual(state["wifi"]["available_networks"][0]["ssid"], "Office")

    def test_wifi_connect_route_uses_manual_hidden_ssid_and_updates_yaml(self) -> None:
        client = app_module.app.test_client()
        app_module._write_setup_state(
            {
                "wifi": {
                    "available_networks": [{"ssid": "Office", "signal": 84, "security": "WPA2"}],
                }
            }
        )

        captured_kwargs: dict[str, object] = {}

        def fake_connect_wifi_network(**kwargs):
            captured_kwargs.update(kwargs)
            return {
                "ssid": "HiddenLab",
                "connection_name": "HiddenLab",
                "auto_connect": True,
                "managed_by": "nmcli",
                "message": "Connected to Wi-Fi network 'HiddenLab'.",
            }

        with patch.object(app_module, "connect_wifi_network", side_effect=fake_connect_wifi_network):
            response = client.post(
                "/setup/wifi/connect",
                data={
                    "manual_ssid": "HiddenLab",
                    "password": "supersecret",
                    "connection_name": "",
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(bool(captured_kwargs.get("hidden")))
        state = app_module._load_setup_state()
        self.assertEqual(state["wifi"]["connect_status"], "pass")
        self.assertEqual(state["current_step"], "openai")
        config_text = self.config_path.read_text(encoding="utf-8")
        self.assertIn("ssid: HiddenLab", config_text)
        self.assertIn("connection_name: HiddenLab", config_text)

    def test_openai_key_route_saves_env_and_marks_pass(self) -> None:
        client = app_module.app.test_client()
        result = HardwareCheckResult(name="openai", status="pass", message="OpenAI API reachable.")

        with patch.object(app_module, "check_openai_reachable", return_value=result):
            response = client.post("/setup/openai-key", data={"openai_api_key": "sk-live-test"})

        self.assertEqual(response.status_code, 302)
        self.assertIn("OPENAI_API_KEY=sk-live-test", self.env_path.read_text(encoding="utf-8"))
        state = app_module._load_setup_state()
        self.assertEqual(state["openai"]["status"], "pass")
        self.assertTrue(state["openai"]["key_present"])
        self.assertEqual(state["current_step"], "openai")

    def test_openai_key_route_advances_to_finish_when_wifi_is_already_connected(self) -> None:
        client = app_module.app.test_client()
        result = HardwareCheckResult(name="openai", status="pass", message="OpenAI API reachable.")
        app_module._write_setup_state(
            {
                "wifi": {
                    "connect_status": "pass",
                    "ssid": "Office",
                    "connection_name": "Office",
                    "message": "Connected.",
                }
            }
        )

        with patch.object(app_module, "check_openai_reachable", return_value=result):
            response = client.post("/setup/openai-key", data={"openai_api_key": "sk-live-test"})

        self.assertEqual(response.status_code, 302)
        state = app_module._load_setup_state()
        self.assertEqual(state["current_step"], "finish")

    def test_camera_test_route_records_failure(self) -> None:
        client = app_module.app.test_client()
        result = HardwareCheckResult(name="camera", status="fail", message="Camera disconnected.")

        with patch.object(app_module, "check_camera", return_value=result):
            response = client.post("/setup/camera/test")

        self.assertEqual(response.status_code, 302)
        state = app_module._load_setup_state()
        self.assertEqual(state["camera"]["status"], "fail")
        self.assertEqual(state["current_step"], "camera")

    def test_gpio_test_stop_marks_success_when_all_buttons_pressed(self) -> None:
        client = app_module.app.test_client()

        class PassingVerifier:
            def __init__(self, required_pins, **kwargs) -> None:
                self.required = [{"label": label, "pin": pin, "pressed": False} for label, pin in required_pins.items()]

            def start(self) -> None:
                return None

            def snapshot(self):
                return {
                    "required": self.required,
                    "pressed_labels": [item["label"] for item in self.required],
                    "all_pressed": True,
                }

            def close(self) -> None:
                return None

        with patch.object(app_module, "GPIOSetupVerifier", PassingVerifier):
            start_response = client.post("/setup/gpio/test/start")
            stop_response = client.post("/setup/gpio/test/stop")

        self.assertEqual(start_response.status_code, 302)
        self.assertEqual(stop_response.status_code, 302)
        state = app_module._load_setup_state()
        self.assertEqual(state["gpio"]["status"], "pass")
        self.assertTrue(state["gpio"]["all_pressed"])
        self.assertEqual(state["current_step"], "finish")

    def test_gpio_test_stop_marks_failure_when_buttons_are_missing(self) -> None:
        client = app_module.app.test_client()

        class PartialVerifier:
            def __init__(self, required_pins, **kwargs) -> None:
                self.required = [{"label": label, "pin": pin, "pressed": False} for label, pin in required_pins.items()]

            def start(self) -> None:
                return None

            def snapshot(self):
                first_label = self.required[0]["label"]
                return {
                    "required": self.required,
                    "pressed_labels": [first_label],
                    "all_pressed": False,
                }

            def close(self) -> None:
                return None

        with patch.object(app_module, "GPIOSetupVerifier", PartialVerifier):
            client.post("/setup/gpio/test/start")
            client.post("/setup/gpio/test/stop")

        state = app_module._load_setup_state()
        self.assertEqual(state["gpio"]["status"], "fail")
        self.assertFalse(state["gpio"]["all_pressed"])
        self.assertEqual(state["current_step"], "gpio")

    def test_finish_requires_completed_wifi_and_verified_key(self) -> None:
        client = app_module.app.test_client()

        with patch.object(app_module, "_schedule_process_restart") as restart_mock:
            response = client.post("/setup/finish")

        self.assertEqual(response.status_code, 302)
        restart_mock.assert_not_called()
        state = app_module._load_setup_state()
        self.assertIn("Connect to Wi-Fi before finishing setup.", state["finish_message"])
        self.assertIn("completed: false", self.config_path.read_text(encoding="utf-8"))

    def test_finish_updates_yaml_clears_state_and_schedules_restart(self) -> None:
        client = app_module.app.test_client()
        app_module._write_setup_state(
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
                    "message": "OpenAI API reachable.",
                },
            }
        )

        with patch.object(app_module, "_schedule_process_restart") as restart_mock:
            response = client.post("/setup/finish")

        self.assertEqual(response.status_code, 302)
        restart_mock.assert_called_once()
        config_text = self.config_path.read_text(encoding="utf-8")
        self.assertIn("completed: true", config_text)
        self.assertIn("version: 1", config_text)
        self.assertIn("locale: en", config_text)
        self.assertFalse(self.setup_state_path.exists())
        self.assertTrue(app_module.SETTINGS.setup.completed)

    def test_manual_setup_reopen_masks_saved_key_and_keeps_root_on_home(self) -> None:
        client = app_module.app.test_client()
        app_module.SETTINGS.setup.completed = True
        app_module.SETTINGS.setup.completed_at = "2026-07-12T11:00:00"
        app_module.SETTINGS.setup.version = 1
        app_module.SETTINGS.network.wifi.ssid = "Office"
        app_module.SETTINGS.network.wifi.connection_name = "Office"
        os.environ["OPENAI_API_KEY"] = "sk-proj-secret-value"

        root_response = client.get("/")
        setup_response = client.get("/setup")

        self.assertEqual(root_response.status_code, 200)
        self.assertIn(b"What would you like to do?", root_response.data)
        self.assertEqual(setup_response.status_code, 200)
        self.assertIn(b"Saved key: sk-proj-", setup_response.data)
        self.assertNotIn(b"sk-proj-secret-value", setup_response.data)
        self.assertIn(b"data-setup-back", setup_response.data)

    def _write_config(self) -> None:
        self.config_path.write_text(
            textwrap.dedent(
                """
                camera:
                  backend: opencv
                  index: 0
                  resolution:
                    width: 1920
                    height: 1080
                  preview:
                    resolution:
                      width: 640
                      height: 360
                    target_fps: 30.0
                    force_mjpeg: true
                  autofocus_mode: continuous
                  exposure: auto
                  brightness: 0.0
                  capture_delay_seconds: 1.0
                  grayscale: false
                  max_dimension: 1600
                display:
                  size:
                    width: 480
                    height: 320
                  orientation: landscape
                button:
                  enabled: true
                  pin: 17
                  mode_button_1_pin: 5
                  mode_button_2_pin: 6
                  mode_button_3_pin: 13
                  mode_button_4_pin: 19
                  mode_button_5_pin: 26
                  back_button_pin: 22
                  debounce_seconds: 0.15
                  hold_seconds: 1.2
                led:
                  enabled: false
                  pin: 27
                  active_high: true
                app:
                  host: 127.0.0.1
                  port: 5000
                  debug: false
                ai:
                  default_mode: document_reader
                vision:
                  screen_optimization: auto
                startup:
                  behavior: kiosk
                  url: http://127.0.0.1:5000
                setup:
                  completed: false
                  completed_at: ""
                  version: 0
                network:
                  wifi:
                    ssid: ""
                    connection_name: ""
                    auto_connect: true
                    managed_by: nmcli
                localization:
                  locale: en
                reliability:
                  log_level: INFO
                  log_max_bytes: 1048576
                  log_backup_count: 5
                  health_monitor_enabled: true
                  health_check_interval_seconds: 60.0
                  camera_probe_interval_seconds: 300.0
                  openai_timeout_seconds: 30.0
                  openai_retry_attempts: 3
                  openai_retry_backoff_seconds: 2.0
                retention:
                  store_images: false
                  text_history_max_items: 100
                  text_history_retention_days: 30
                  retry_media_retention_hours: 24.0
                  purge_on_startup: true
                offline_retry:
                  enabled: false
                  max_items: 10
                  max_attempts: 3
                  initial_delay_seconds: 30.0
                  max_delay_seconds: 900.0
                  poll_interval_seconds: 5.0
                  min_free_mb: 128
                  max_storage_mb: 512
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )


class _FakeLivePreview:
    """Simple live-preview test double for the setup wizard."""

    def get_jpeg_frame(self, timeout_seconds: float = 1.0) -> bytes:
        return b"jpeg-data"

    def iter_mjpeg_stream(self, boundary: str = "frame", timeout_seconds: float = 1.0):
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\njpeg-data\r\n"

    def pause(self, timeout_seconds: float = 2.0) -> bool:
        return True

    def resume(self) -> None:
        return None

    def is_camera_active(self) -> bool:
        return False

    def has_recent_frame(self, max_age_seconds: float = 10.0) -> bool:
        return False

    def latest_error_message(self) -> str:
        return ""
