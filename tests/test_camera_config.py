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
    ResolutionSettings,
    StartupSettings,
    VisionSettings,
)
from hardware.camera_config import (
    build_camera_request,
    resolve_opencv_config,
    select_best_resolution,
)


class CameraConfigTests(unittest.TestCase):
    """Verify camera request merging and mode resolution."""

    def test_build_camera_request_uses_device_defaults(self) -> None:
        settings = _build_settings()
        with patch("hardware.camera_config.load_device_settings", return_value=settings):
            request = build_camera_request()

        self.assertEqual(request.backend, "auto")
        self.assertEqual(request.camera_index, 0)
        self.assertEqual(request.width, 4608)
        self.assertEqual(request.height, 2592)
        self.assertEqual(request.autofocus_mode, "continuous")
        self.assertEqual(request.exposure, "auto")

    def test_select_best_resolution_picks_closest_sensor_mode(self) -> None:
        sensor_modes = [
            {"size": (640, 480)},
            {"size": (1920, 1080)},
            {"size": (4608, 2592)},
        ]

        selected = select_best_resolution(sensor_modes, requested_width=4000, requested_height=2200)

        self.assertEqual(selected, (4608, 2592))

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
            backend="auto",
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
        button=ButtonSettings(enabled=True, pin=17),
        ai=AISettings(default_mode="read_text"),
        vision=VisionSettings(screen_optimization="auto"),
        startup=StartupSettings(behavior="kiosk", url="http://localhost:5000"),
        config_path=Path("config/device.yaml"),
    )
