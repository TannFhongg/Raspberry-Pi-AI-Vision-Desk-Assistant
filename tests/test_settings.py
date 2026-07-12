"""Unit tests for typed device settings loading."""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from config.settings import SettingsError, load_device_settings


class LoadDeviceSettingsTests(unittest.TestCase):
    """Verify YAML loading and environment override behavior."""

    def test_loads_yaml_defaults(self) -> None:
        config_path = _write_temp_config(
            """
            camera:
              backend: opencv
              index: 0
              resolution:
                width: 4608
                height: 2592
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
              back_button_pin: 21
            ai:
              default_mode: document_reader
            vision:
              screen_optimization: auto
            startup:
              behavior: kiosk
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
            """
        )

        settings = load_device_settings(config_path=config_path, env={})

        self.assertEqual(settings.camera.backend, "opencv")
        self.assertEqual(settings.camera.resolution.width, 4608)
        self.assertEqual(settings.camera.preview.resolution.width, 640)
        self.assertEqual(settings.camera.preview.resolution.height, 360)
        self.assertAlmostEqual(settings.camera.preview.target_fps, 30.0)
        self.assertTrue(settings.camera.preview.force_mjpeg)
        self.assertEqual(settings.display.size.height, 320)
        self.assertTrue(settings.button.enabled)
        self.assertEqual(settings.button.pin, 17)
        self.assertEqual(settings.button.mode_button_1_pin, 5)
        self.assertEqual(settings.button.mode_button_2_pin, 6)
        self.assertEqual(settings.button.mode_button_3_pin, 13)
        self.assertEqual(settings.button.mode_button_4_pin, 19)
        self.assertEqual(settings.button.mode_button_5_pin, 26)
        self.assertEqual(settings.button.back_button_pin, 21)
        self.assertAlmostEqual(settings.button.debounce_seconds, 0.15)
        self.assertAlmostEqual(settings.button.hold_seconds, 1.2)
        self.assertFalse(settings.led.enabled)
        self.assertEqual(settings.led.pin, 27)
        self.assertTrue(settings.led.active_high)
        self.assertEqual(settings.ai.default_mode, "document_reader")
        self.assertEqual(settings.vision.screen_optimization, "auto")
        self.assertEqual(settings.startup.behavior, "kiosk")
        self.assertEqual(settings.reliability.log_level, "INFO")
        self.assertEqual(settings.reliability.log_max_bytes, 1_048_576)
        self.assertEqual(settings.reliability.log_backup_count, 5)
        self.assertTrue(settings.reliability.health_monitor_enabled)
        self.assertAlmostEqual(settings.reliability.health_check_interval_seconds, 60.0)
        self.assertAlmostEqual(settings.reliability.camera_probe_interval_seconds, 300.0)
        self.assertAlmostEqual(settings.reliability.openai_timeout_seconds, 30.0)
        self.assertEqual(settings.reliability.openai_retry_attempts, 3)
        self.assertAlmostEqual(settings.reliability.openai_retry_backoff_seconds, 2.0)

    def test_environment_overrides_take_precedence(self) -> None:
        config_path = _write_temp_config(
            """
            camera:
              backend: opencv
              index: 0
              resolution:
                width: 4608
                height: 2592
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
              back_button_pin: 21
            ai:
              default_mode: document_reader
            vision:
              screen_optimization: auto
            startup:
              behavior: kiosk
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
            """
        )

        settings = load_device_settings(
            config_path=config_path,
            env={
                "VISION_CAMERA_BACKEND": "opencv",
                "VISION_CAPTURE_WIDTH": "1280",
                "VISION_CAPTURE_HEIGHT": "720",
                "LIVE_PREVIEW_WIDTH": "512",
                "LIVE_PREVIEW_HEIGHT": "288",
                "LIVE_PREVIEW_TARGET_FPS": "24",
                "LIVE_PREVIEW_FORCE_MJPEG": "0",
                "VISION_AUTOFOCUS_MODE": "off",
                "VISION_EXPOSURE": "12000",
                "VISION_BRIGHTNESS": "0.2",
                "VISION_CAPTURE_DELAY_SECONDS": "2.5",
                "ENABLE_GPIO_BUTTON": "0",
                "CAPTURE_BUTTON_PIN": "22",
                "MODE_BUTTON_1_PIN": "23",
                "MODE_BUTTON_2_PIN": "24",
                "MODE_BUTTON_3_PIN": "25",
                "MODE_BUTTON_4_PIN": "8",
                "MODE_BUTTON_5_PIN": "7",
                "BACK_BUTTON_PIN": "16",
                "GPIO_BUTTON_DEBOUNCE_SECONDS": "0.4",
                "GPIO_BUTTON_HOLD_SECONDS": "1.8",
                "ENABLE_GPIO_LED": "1",
                "GPIO_LED_PIN": "18",
                "GPIO_LED_ACTIVE_HIGH": "0",
                "AI_DEFAULT_MODE": "solve_problem",
                "SCREEN_OPTIMIZATION": "on",
                "STARTUP_BEHAVIOR": "manual",
                "RELIABILITY_LOG_LEVEL": "DEBUG",
                "RELIABILITY_LOG_MAX_BYTES": "4096",
                "RELIABILITY_LOG_BACKUP_COUNT": "2",
                "RELIABILITY_HEALTH_MONITOR_ENABLED": "0",
                "RELIABILITY_HEALTH_CHECK_INTERVAL_SECONDS": "30",
                "RELIABILITY_CAMERA_PROBE_INTERVAL_SECONDS": "120",
                "RELIABILITY_OPENAI_TIMEOUT_SECONDS": "12.5",
                "RELIABILITY_OPENAI_RETRY_ATTEMPTS": "4",
                "RELIABILITY_OPENAI_RETRY_BACKOFF_SECONDS": "1.5",
            },
        )

        self.assertEqual(settings.camera.backend, "opencv")
        self.assertEqual(settings.camera.resolution.width, 1280)
        self.assertEqual(settings.camera.resolution.height, 720)
        self.assertEqual(settings.camera.preview.resolution.width, 512)
        self.assertEqual(settings.camera.preview.resolution.height, 288)
        self.assertAlmostEqual(settings.camera.preview.target_fps, 24.0)
        self.assertFalse(settings.camera.preview.force_mjpeg)
        self.assertEqual(settings.camera.autofocus_mode, "off")
        self.assertEqual(settings.camera.exposure, 12000)
        self.assertAlmostEqual(settings.camera.brightness, 0.2)
        self.assertAlmostEqual(settings.camera.capture_delay_seconds, 2.5)
        self.assertFalse(settings.button.enabled)
        self.assertEqual(settings.button.pin, 22)
        self.assertEqual(settings.button.mode_button_1_pin, 23)
        self.assertEqual(settings.button.mode_button_2_pin, 24)
        self.assertEqual(settings.button.mode_button_3_pin, 25)
        self.assertEqual(settings.button.mode_button_4_pin, 8)
        self.assertEqual(settings.button.mode_button_5_pin, 7)
        self.assertEqual(settings.button.back_button_pin, 16)
        self.assertAlmostEqual(settings.button.debounce_seconds, 0.4)
        self.assertAlmostEqual(settings.button.hold_seconds, 1.8)
        self.assertTrue(settings.led.enabled)
        self.assertEqual(settings.led.pin, 18)
        self.assertFalse(settings.led.active_high)
        self.assertEqual(settings.ai.default_mode, "math_solver")
        self.assertEqual(settings.vision.screen_optimization, "on")
        self.assertEqual(settings.startup.behavior, "manual")
        self.assertEqual(settings.reliability.log_level, "DEBUG")
        self.assertEqual(settings.reliability.log_max_bytes, 4096)
        self.assertEqual(settings.reliability.log_backup_count, 2)
        self.assertFalse(settings.reliability.health_monitor_enabled)
        self.assertAlmostEqual(settings.reliability.health_check_interval_seconds, 30.0)
        self.assertAlmostEqual(settings.reliability.camera_probe_interval_seconds, 120.0)
        self.assertAlmostEqual(settings.reliability.openai_timeout_seconds, 12.5)
        self.assertEqual(settings.reliability.openai_retry_attempts, 4)
        self.assertAlmostEqual(settings.reliability.openai_retry_backoff_seconds, 1.5)

    def test_invalid_yaml_value_raises_settings_error(self) -> None:
        config_path = _write_temp_config(
            """
            camera:
              backend: invalid
              index: 0
              resolution:
                width: 4608
                height: 2592
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
            ai:
              default_mode: document_reader
            vision:
              screen_optimization: auto
            startup:
              behavior: kiosk
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
            """
        )

        with self.assertRaises(SettingsError):
            load_device_settings(config_path=config_path, env={})

    def test_invalid_screen_optimization_raises_settings_error(self) -> None:
        config_path = _write_temp_config(
            """
            camera:
              backend: opencv
              index: 0
              resolution:
                width: 4608
                height: 2592
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
            ai:
              default_mode: document_reader
            vision:
              screen_optimization: maybe
            startup:
              behavior: kiosk
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
            """
        )

        with self.assertRaises(SettingsError):
            load_device_settings(config_path=config_path, env={})

    def test_invalid_reliability_value_raises_settings_error(self) -> None:
        config_path = _write_temp_config(
            """
            camera:
              backend: opencv
              index: 0
              resolution:
                width: 4608
                height: 2592
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
            ai:
              default_mode: document_reader
            vision:
              screen_optimization: auto
            startup:
              behavior: kiosk
            reliability:
              log_level: nope
              log_max_bytes: 1048576
              log_backup_count: 5
              health_monitor_enabled: true
              health_check_interval_seconds: 60.0
              camera_probe_interval_seconds: 300.0
              openai_timeout_seconds: 30.0
              openai_retry_attempts: 3
              openai_retry_backoff_seconds: 2.0
            """
        )

        with self.assertRaises(SettingsError):
            load_device_settings(config_path=config_path, env={})

    def test_new_app_retention_and_retry_settings_load(self) -> None:
        config_path = _write_temp_config(
            """
            camera:
              backend: opencv
              index: 0
              resolution:
                width: 4608
                height: 2592
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
            ai:
              default_mode: document_reader
            vision:
              screen_optimization: auto
            startup:
              behavior: kiosk
            setup:
              completed: false
              completed_at: ""
              version: 0
            network:
              wifi:
                ssid: TestSSID
                connection_name: TestSSID
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
              enabled: true
              max_items: 10
              max_attempts: 3
              initial_delay_seconds: 30.0
              max_delay_seconds: 900.0
              poll_interval_seconds: 5.0
              min_free_mb: 128
              max_storage_mb: 512
            """
        )

        settings = load_device_settings(config_path=config_path, env={})

        self.assertFalse(settings.setup.completed)
        self.assertEqual(settings.setup.completed_at, "")
        self.assertEqual(settings.setup.version, 0)
        self.assertEqual(settings.network.wifi.ssid, "TestSSID")
        self.assertEqual(settings.network.wifi.connection_name, "TestSSID")
        self.assertTrue(settings.network.wifi.auto_connect)
        self.assertEqual(settings.network.wifi.managed_by, "nmcli")
        self.assertEqual(settings.localization.locale, "en")
        self.assertFalse(settings.retention.store_images)
        self.assertEqual(settings.retention.text_history_max_items, 100)
        self.assertEqual(settings.retention.text_history_retention_days, 30)
        self.assertAlmostEqual(settings.retention.retry_media_retention_hours, 24.0)
        self.assertTrue(settings.retention.purge_on_startup)
        self.assertTrue(settings.offline_retry.enabled)
        self.assertEqual(settings.offline_retry.max_items, 10)
        self.assertEqual(settings.offline_retry.max_attempts, 3)
        self.assertAlmostEqual(settings.offline_retry.initial_delay_seconds, 30.0)
        self.assertAlmostEqual(settings.offline_retry.max_delay_seconds, 900.0)
        self.assertAlmostEqual(settings.offline_retry.poll_interval_seconds, 5.0)
        self.assertEqual(settings.offline_retry.min_free_mb, 128)
        self.assertEqual(settings.offline_retry.max_storage_mb, 512)

    def test_duplicate_led_and_button_pins_raise_settings_error(self) -> None:
        config_path = _write_temp_config(
            """
            camera:
              backend: opencv
              index: 0
              resolution:
                width: 4608
                height: 2592
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
              mode_button_1_pin: 23
            led:
              enabled: true
              pin: 23
              active_high: true
            ai:
              default_mode: document_reader
            vision:
              screen_optimization: auto
            startup:
              behavior: kiosk
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
            """
        )

        with self.assertRaises(SettingsError):
            load_device_settings(config_path=config_path, env={})

    def test_legacy_config_marks_setup_complete_only_with_real_openai_key(self) -> None:
        config_path = _write_temp_config(
            """
            camera:
              backend: opencv
              index: 0
              resolution:
                width: 4608
                height: 2592
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
            ai:
              default_mode: document_reader
            vision:
              screen_optimization: auto
            startup:
              behavior: kiosk
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
            """
        )

        missing_key_settings = load_device_settings(config_path=config_path, env={})
        placeholder_settings = load_device_settings(
            config_path=config_path,
            env={"OPENAI_API_KEY": "your_openai_api_key_here"},
        )
        configured_settings = load_device_settings(
            config_path=config_path,
            env={"OPENAI_API_KEY": "sk-test-real"},
        )

        self.assertFalse(missing_key_settings.setup.completed)
        self.assertFalse(placeholder_settings.setup.completed)
        self.assertTrue(configured_settings.setup.completed)
        self.assertEqual(configured_settings.setup.version, 1)

    def test_invalid_locale_raises_settings_error(self) -> None:
        config_path = _write_temp_config(
            """
            camera:
              backend: opencv
              index: 0
              resolution:
                width: 1920
                height: 1080
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
            ai:
              default_mode: document_reader
            vision:
              screen_optimization: auto
            startup:
              behavior: kiosk
            localization:
              locale: vi
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
            """
        )

        with self.assertRaises(SettingsError):
            load_device_settings(config_path=config_path, env={})


def _write_temp_config(contents: str) -> Path:
    """Write a temporary YAML config file and return its path."""
    temp_dir = Path(tempfile.mkdtemp(prefix="vision-settings-test-"))
    config_path = temp_dir / "device.yaml"
    config_path.write_text(textwrap.dedent(contents).strip() + "\n", encoding="utf-8")
    return config_path
