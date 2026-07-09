"""Unit tests for hardware diagnostics aggregation and CLI exit codes."""

from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

import check_hardware
from hardware.device_check import (
    HardwareCheckReport,
    HardwareCheckResult,
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
