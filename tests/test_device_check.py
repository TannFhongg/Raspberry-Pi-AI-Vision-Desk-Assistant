"""Unit tests for device diagnostics and lightweight camera probing."""

from __future__ import annotations

from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch

import check_hardware
from config.settings import (
    AISettings,
    ButtonSettings,
    CameraSettings,
    DeviceSettings,
    DisplaySettings,
    LEDSettings,
    OfflineRetrySettings,
    ReliabilitySettings,
    RetentionSettings,
    ResolutionSettings,
    StartupSettings,
    VisionSettings,
)
from hardware.device_check import (
    HardwareCheckReport,
    HardwareCheckResult,
    _build_camera_probe_resolution,
    check_camera,
    run_device_checks,
)


class DeviceCheckTests(unittest.TestCase):
    """Verify hardware diagnostic aggregation behavior."""

    def test_run_device_checks_aggregates_results(self) -> None:
        fake_results = [
            HardwareCheckResult(name="camera", status="pass", message="ok"),
            HardwareCheckResult(name="display", status="pass", message="ok"),
            HardwareCheckResult(name="internet", status="pass", message="ok"),
            HardwareCheckResult(name="openai", status="pass", message="ok"),
            HardwareCheckResult(name="gpio", status="pass", message="ok"),
        ]

        with patch("hardware.device_check.load_device_settings", return_value=object()), patch(
            "hardware.device_check.check_camera", return_value=fake_results[0]
        ), patch(
            "hardware.device_check.check_display", return_value=fake_results[1]
        ), patch(
            "hardware.device_check.check_internet_connection", return_value=fake_results[2]
        ), patch(
            "hardware.device_check.check_openai_reachable", return_value=fake_results[3]
        ), patch(
            "hardware.device_check.check_gpio_available", return_value=fake_results[4]
        ):
            report = run_device_checks()

        self.assertTrue(report.all_required_passed)
        self.assertEqual(report.results, fake_results)

    def test_report_fails_when_required_check_fails(self) -> None:
        report = HardwareCheckReport(
            results=[
                HardwareCheckResult(name="camera", status="pass", message="ok"),
                HardwareCheckResult(name="display", status="fail", message="missing"),
            ]
        )

        self.assertFalse(report.all_required_passed)

    def test_check_hardware_main_returns_zero_when_all_checks_pass(self) -> None:
        report = HardwareCheckReport(
            results=[
                HardwareCheckResult(name="camera", status="pass", message="ok"),
            ]
        )
        settings = SimpleNamespace(
            config_path="config/device.yaml",
            startup=SimpleNamespace(behavior="kiosk"),
        )

        with patch("check_hardware.load_device_settings", return_value=settings), patch(
            "check_hardware.run_device_checks", return_value=report
        ):
            exit_code = check_hardware.main()

        self.assertEqual(exit_code, 0)

    def test_check_hardware_main_returns_one_on_failure(self) -> None:
        report = HardwareCheckReport(
            results=[
                HardwareCheckResult(name="camera", status="fail", message="bad"),
            ]
        )
        settings = SimpleNamespace(
            config_path="config/device.yaml",
            startup=SimpleNamespace(behavior="kiosk"),
        )

        with patch("check_hardware.load_device_settings", return_value=settings), patch(
            "check_hardware.run_device_checks", return_value=report
        ):
            exit_code = check_hardware.main()

        self.assertEqual(exit_code, 1)


class DeviceCameraProbeTests(unittest.TestCase):
    """Verify the camera health probe stays lightweight."""

    def test_camera_probe_resolution_scales_down_large_capture_defaults(self) -> None:
        settings = _build_settings()

        self.assertEqual(_build_camera_probe_resolution(settings), (1280, 720))

    def test_check_camera_uses_lightweight_resolution_and_zero_delay(self) -> None:
        settings = _build_settings()

        with patch("hardware.device_check.capture_image") as capture_image:
            capture_image.return_value = type(
                "CaptureResult",
                (),
                {
                    "backend_used": "opencv",
                    "resolution": (1280, 720),
                    "warnings": (),
                },
            )()

            result = check_camera(settings)

        self.assertEqual(result.status, "pass")
        capture_image.assert_called_once()
        self.assertEqual(capture_image.call_args.kwargs["width"], 1280)
        self.assertEqual(capture_image.call_args.kwargs["height"], 720)
        self.assertEqual(capture_image.call_args.kwargs["capture_delay_seconds"], 0.0)


def _build_settings() -> DeviceSettings:
    """Create a deterministic settings object for device checks."""
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
            back_button_pin=22,
            debounce_seconds=0.15,
            hold_seconds=1.2,
        ),
        led=LEDSettings(enabled=False, pin=27, active_high=True),
        ai=AISettings(default_mode="document_reader"),
        vision=VisionSettings(screen_optimization="auto"),
        startup=StartupSettings(behavior="kiosk"),
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
        retention=RetentionSettings(
            store_images=False,
            text_history_max_items=100,
            text_history_retention_days=30,
            retry_media_retention_hours=24.0,
            purge_on_startup=True,
        ),
        offline_retry=OfflineRetrySettings(
            enabled=True,
            max_items=10,
            max_attempts=3,
            initial_delay_seconds=30.0,
            max_delay_seconds=900.0,
            poll_interval_seconds=5.0,
            min_free_mb=128,
            max_storage_mb=512,
        ),
        config_path=Path("config/device.yaml"),
    )
