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
              backend: auto
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
              url: http://localhost:5000
            """
        )

        settings = load_device_settings(config_path=config_path, env={})

        self.assertEqual(settings.camera.backend, "auto")
        self.assertEqual(settings.camera.resolution.width, 4608)
        self.assertEqual(settings.display.size.height, 320)
        self.assertTrue(settings.button.enabled)
        self.assertAlmostEqual(settings.button.debounce_seconds, 0.15)
        self.assertAlmostEqual(settings.button.hold_seconds, 1.2)
        self.assertFalse(settings.led.enabled)
        self.assertEqual(settings.led.pin, 27)
        self.assertTrue(settings.led.active_high)
        self.assertEqual(settings.ai.default_mode, "document_reader")
        self.assertEqual(settings.vision.screen_optimization, "auto")
        self.assertEqual(settings.startup.behavior, "kiosk")

    def test_environment_overrides_take_precedence(self) -> None:
        config_path = _write_temp_config(
            """
            camera:
              backend: auto
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
              url: http://localhost:5000
            """
        )

        settings = load_device_settings(
            config_path=config_path,
            env={
                "VISION_CAMERA_BACKEND": "opencv",
                "VISION_CAPTURE_WIDTH": "1280",
                "VISION_CAPTURE_HEIGHT": "720",
                "VISION_AUTOFOCUS_MODE": "off",
                "VISION_EXPOSURE": "12000",
                "VISION_BRIGHTNESS": "0.2",
                "VISION_CAPTURE_DELAY_SECONDS": "2.5",
                "ENABLE_GPIO_BUTTON": "0",
                "GPIO_BUTTON_PIN": "22",
                "GPIO_BUTTON_DEBOUNCE_SECONDS": "0.4",
                "GPIO_BUTTON_HOLD_SECONDS": "1.8",
                "ENABLE_GPIO_LED": "1",
                "GPIO_LED_PIN": "23",
                "GPIO_LED_ACTIVE_HIGH": "0",
                "AI_DEFAULT_MODE": "solve_problem",
                "SCREEN_OPTIMIZATION": "on",
                "STARTUP_BEHAVIOR": "manual",
            },
        )

        self.assertEqual(settings.camera.backend, "opencv")
        self.assertEqual(settings.camera.resolution.width, 1280)
        self.assertEqual(settings.camera.resolution.height, 720)
        self.assertEqual(settings.camera.autofocus_mode, "off")
        self.assertEqual(settings.camera.exposure, 12000)
        self.assertAlmostEqual(settings.camera.brightness, 0.2)
        self.assertAlmostEqual(settings.camera.capture_delay_seconds, 2.5)
        self.assertFalse(settings.button.enabled)
        self.assertEqual(settings.button.pin, 22)
        self.assertAlmostEqual(settings.button.debounce_seconds, 0.4)
        self.assertAlmostEqual(settings.button.hold_seconds, 1.8)
        self.assertTrue(settings.led.enabled)
        self.assertEqual(settings.led.pin, 23)
        self.assertFalse(settings.led.active_high)
        self.assertEqual(settings.ai.default_mode, "math_solver")
        self.assertEqual(settings.vision.screen_optimization, "on")
        self.assertEqual(settings.startup.behavior, "manual")

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
              url: http://localhost:5000
            """
        )

        with self.assertRaises(SettingsError):
            load_device_settings(config_path=config_path, env={})

    def test_invalid_screen_optimization_raises_settings_error(self) -> None:
        config_path = _write_temp_config(
            """
            camera:
              backend: auto
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
              url: http://localhost:5000
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
