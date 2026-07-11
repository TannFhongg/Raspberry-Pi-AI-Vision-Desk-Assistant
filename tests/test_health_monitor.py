"""Unit tests for the Phase 14 system health monitor."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import system.health as health_module
from system.health import HealthMonitor, collect_health_snapshot, write_health_snapshot


class HealthSnapshotTests(unittest.TestCase):
    """Verify system health collection and persistence behavior."""

    def test_collect_health_snapshot_parses_cpu_and_memory(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="vision-health-test-"))
        cpu_path = temp_dir / "thermal_zone0_temp"
        meminfo_path = temp_dir / "meminfo"
        cpu_path.write_text("55000\n", encoding="utf-8")
        meminfo_path.write_text(
            "MemTotal:       1000 kB\nMemAvailable:    250 kB\n",
            encoding="utf-8",
        )

        with patch.object(health_module, "CPU_TEMPERATURE_PATH", cpu_path), patch.object(
            health_module,
            "MEMORY_INFO_PATH",
            meminfo_path,
        ), patch(
            "system.health.check_internet_connection",
            return_value=SimpleNamespace(status="pass", message="internet ok"),
        ), patch(
            "system.health.check_camera",
            return_value=SimpleNamespace(status="pass", message="camera ok"),
        ):
            snapshot = collect_health_snapshot(settings=object(), probe_camera=True)

        self.assertEqual(snapshot["overall_status"], "healthy")
        self.assertEqual(snapshot["cpu"]["temperature_c"], 55.0)
        self.assertEqual(snapshot["memory"]["used_percent"], 75.0)
        self.assertEqual(snapshot["network"]["status"], "pass")
        self.assertEqual(snapshot["camera"]["status"], "pass")

    def test_collect_health_snapshot_reuses_previous_camera_when_probe_is_skipped(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="vision-health-skip-"))
        cpu_path = temp_dir / "thermal_zone0_temp"
        meminfo_path = temp_dir / "meminfo"
        cpu_path.write_text("45000\n", encoding="utf-8")
        meminfo_path.write_text(
            "MemTotal:       1000 kB\nMemAvailable:    500 kB\n",
            encoding="utf-8",
        )
        previous_snapshot = {
            "camera": {
                "status": "pass",
                "message": "camera ok",
                "last_probe_at": "2026-07-09T22:00:00",
            }
        }

        with patch.object(health_module, "CPU_TEMPERATURE_PATH", cpu_path), patch.object(
            health_module,
            "MEMORY_INFO_PATH",
            meminfo_path,
        ), patch(
            "system.health.check_internet_connection",
            return_value=SimpleNamespace(status="pass", message="internet ok"),
        ):
            snapshot = collect_health_snapshot(
                settings=object(),
                previous_snapshot=previous_snapshot,
                probe_camera=False,
            )

        self.assertEqual(snapshot["camera"], previous_snapshot["camera"])
        self.assertEqual(snapshot["overall_status"], "healthy")

    def test_collect_health_snapshot_marks_network_failure_as_degraded(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="vision-health-network-"))
        cpu_path = temp_dir / "thermal_zone0_temp"
        meminfo_path = temp_dir / "meminfo"
        cpu_path.write_text("42000\n", encoding="utf-8")
        meminfo_path.write_text(
            "MemTotal:       1000 kB\nMemAvailable:    600 kB\n",
            encoding="utf-8",
        )

        with patch.object(health_module, "CPU_TEMPERATURE_PATH", cpu_path), patch.object(
            health_module,
            "MEMORY_INFO_PATH",
            meminfo_path,
        ), patch(
            "system.health.check_internet_connection",
            return_value=SimpleNamespace(status="fail", message="network down"),
        ), patch(
            "system.health.check_camera",
            return_value=SimpleNamespace(status="pass", message="camera ok"),
        ):
            snapshot = collect_health_snapshot(settings=object(), probe_camera=True)

        self.assertEqual(snapshot["overall_status"], "degraded")
        self.assertEqual(snapshot["network"]["status"], "fail")

    def test_write_health_snapshot_persists_json(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="vision-health-write-"))
        output_path = temp_dir / "health_status.json"
        snapshot = {
            "overall_status": "healthy",
            "updated_at": "2026-07-09T22:30:00",
            "cpu": {"status": "pass"},
            "memory": {"status": "pass"},
            "network": {"status": "pass"},
            "camera": {"status": "pass", "last_probe_at": "2026-07-09T22:30:00"},
        }

        write_health_snapshot(snapshot, output_path=output_path)

        self.assertTrue(output_path.is_file())
        self.assertIn('"overall_status": "healthy"', output_path.read_text(encoding="utf-8"))


class HealthMonitorTests(unittest.TestCase):
    """Verify the busy-safe camera probing policy."""

    def test_health_monitor_defers_camera_probe_until_device_is_idle(self) -> None:
        calls: list[bool] = []
        settings = _build_monitor_settings()
        monitor = HealthMonitor(
            settings=settings,
            is_busy=lambda: True,
            initial_camera_probe_delay_seconds=0.0,
        )

        def fake_collect(settings, previous_snapshot=None, probe_camera=True):
            calls.append(probe_camera)
            return _build_snapshot("unknown" if not probe_camera else "healthy")

        with patch("system.health.collect_health_snapshot", side_effect=fake_collect), patch(
            "system.health.write_health_snapshot"
        ):
            monitor.run_once()
            monitor.is_busy = lambda: False
            monitor.run_once()

        self.assertEqual(calls, [False, True])

    def test_health_monitor_defers_first_camera_probe_during_startup_grace_period(self) -> None:
        calls: list[bool] = []
        settings = _build_monitor_settings()
        monitor = HealthMonitor(
            settings=settings,
            is_busy=lambda: False,
            initial_camera_probe_delay_seconds=30.0,
        )

        def fake_collect(settings, previous_snapshot=None, probe_camera=True):
            calls.append(probe_camera)
            return _build_snapshot("unknown" if not probe_camera else "healthy")

        with patch("system.health.collect_health_snapshot", side_effect=fake_collect), patch(
            "system.health.write_health_snapshot"
        ):
            monitor.run_once()

        self.assertEqual(calls, [False])


def _build_monitor_settings() -> SimpleNamespace:
    """Return only the monitor settings needed by HealthMonitor."""
    return SimpleNamespace(
        reliability=SimpleNamespace(
            health_check_interval_seconds=60.0,
            camera_probe_interval_seconds=300.0,
        )
    )


def _build_snapshot(overall_status: str) -> dict[str, object]:
    """Create a minimal snapshot shape accepted by the monitor."""
    camera_status = "pass" if overall_status == "healthy" else "unknown"
    return {
        "overall_status": overall_status,
        "updated_at": "2026-07-09T22:30:00",
        "cpu": {"status": "pass"},
        "memory": {"status": "pass"},
        "network": {"status": "pass"},
        "camera": {
            "status": camera_status,
            "message": "camera ok" if camera_status == "pass" else "camera deferred",
            "last_probe_at": None,
        },
    }
