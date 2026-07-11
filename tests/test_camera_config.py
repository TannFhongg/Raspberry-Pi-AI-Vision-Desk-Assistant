"""Unit tests for camera capability resolution helpers."""

from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from config.settings import (
    AISettings,
    ButtonSettings,
    CameraSettings,
    DeviceSettings,
    DisplaySettings,
    LEDSettings,
    ReliabilitySettings,
    ResolutionSettings,
    StartupSettings,
    VisionSettings,
)
from hardware.camera_config import (
    CameraConfigError,
    build_camera_request,
    resolve_opencv_config,
)


class CameraConfigTests(unittest.TestCase):
    """Verify camera request merging and mode resolution."""

    def test_build_camera_request_uses_device_defaults(self) -> None:
        settings = _build_settings()
        with patch("hardware.camera_config.load_device_settings", return_value=settings):
            request = build_camera_request()

        self.assertEqual(request.backend, "opencv")
        self.assertEqual(request.camera_index, 0)
        self.assertEqual(request.width, 4608)
        self.assertEqual(request.height, 2592)
        self.assertEqual(request.autofocus_mode, "continuous")
        self.assertEqual(request.exposure, "auto")

    def test_build_camera_request_rejects_removed_non_opencv_backends(self) -> None:
        settings = _build_settings()
        with patch("hardware.camera_config.load_device_settings", return_value=settings):
            with self.assertRaises(CameraConfigError):
                build_camera_request(backend="auto")

    def test_resolve_opencv_config_adds_best_effort_warnings(self) -> None:
        settings = _build_settings()
        with patch("hardware.camera_config.load_device_settings", return_value=settings):
            request = build_camera_request(
                backend="opencv",
                autofocus_mode="auto",
                exposure=12000,
                brightness=0.5,
            )

        resolved = resolve_opencv_config(request)

        self.assertEqual(resolved.backend, "opencv")
        self.assertGreaterEqual(len(resolved.warnings), 3)


def _build_settings() -> DeviceSettings:
    """Create a test settings object."""
    return DeviceSettings(
        camera=CameraSettings(
            backend="opencv",
            index=0,
            resolution=ResolutionSettings(width=4608, height=2592),
            autofocus_mode="continuous",
            exposure="auto",
            brightness=0.0,
            capture_delay_seconds=1.0,
            grayscale=False,
            max_dimension=1600,
        ),
        display=DisplaySettings(
            size=ResolutionSettings(width=480, height=320),
            orientation="landscape",
        ),
        button=ButtonSettings(
            enabled=True,
            pin=17,
            mode_button_1_pin=5,
            mode_button_2_pin=6,
            mode_button_3_pin=13,
            mode_button_4_pin=19,
            mode_button_5_pin=26,
            back_button_pin=None,
            debounce_seconds=0.15,
            hold_seconds=1.2,
        ),
        led=LEDSettings(enabled=False, pin=27, active_high=True),
        ai=AISettings(default_mode="document_reader"),
        vision=VisionSettings(screen_optimization="auto"),
        startup=StartupSettings(behavior="kiosk", url="http://localhost:5000"),
        reliability=ReliabilitySettings(
            log_level="INFO",
            log_max_bytes=1_048_576,
            log_backup_count=5,
            health_monitor_enabled=True,
            health_check_interval_seconds=60.0,
            camera_probe_interval_seconds=300.0,
            openai_timeout_seconds=30.0,
            openai_retry_attempts=3,
            openai_retry_backoff_seconds=2.0,
        ),
        config_path=Path("config/device.yaml"),
    )
