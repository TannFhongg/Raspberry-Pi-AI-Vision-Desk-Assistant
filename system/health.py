"""Background system health monitoring for the Raspberry Pi device."""

from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from config import DeviceSettings, load_device_settings
from hardware.device_check import check_camera, check_internet_connection
from system.storage import atomic_write_json

DEFAULT_HEALTH_STATUS_PATH = Path("data/health_status.json")
CPU_TEMPERATURE_PATH = Path("/sys/class/thermal/thermal_zone0/temp")
MEMORY_INFO_PATH = Path("/proc/meminfo")
CPU_TEMPERATURE_FAIL_C = 80.0
MEMORY_USED_FAIL_PERCENT = 90.0
DEFAULT_INITIAL_CAMERA_PROBE_DELAY_SECONDS = 15.0
LOGGER = logging.getLogger(__name__)


def collect_health_snapshot(
    settings: DeviceSettings | None = None,
    *,
    previous_snapshot: dict[str, Any] | None = None,
    probe_camera: bool = True,
) -> dict[str, Any]:
    """Collect a point-in-time device health snapshot."""
    resolved_settings = settings or load_device_settings()
    updated_at = _timestamp()
    cpu = _collect_cpu_health()
    memory = _collect_memory_health()
    network = _collect_network_health()
    camera = _collect_camera_health(
        resolved_settings,
        previous_snapshot=previous_snapshot,
        probe_camera=probe_camera,
        probed_at=updated_at,
    )
    overall_status = _resolve_overall_status(cpu, memory, network, camera)

    return {
        "overall_status": overall_status,
        "updated_at": updated_at,
        "cpu": cpu,
        "memory": memory,
        "network": network,
        "camera": camera,
    }


def write_health_snapshot(
    snapshot: dict[str, Any],
    output_path: str | Path = DEFAULT_HEALTH_STATUS_PATH,
) -> Path:
    """Atomically persist the latest health snapshot to disk."""
    return atomic_write_json(output_path, snapshot, ensure_ascii=True, indent=2)


class HealthMonitor:
    """Background monitor that periodically writes device health snapshots."""

    def __init__(
        self,
        settings: DeviceSettings | None = None,
        *,
        output_path: str | Path = DEFAULT_HEALTH_STATUS_PATH,
        is_busy: Callable[[], bool] | None = None,
        initial_camera_probe_delay_seconds: float = DEFAULT_INITIAL_CAMERA_PROBE_DELAY_SECONDS,
    ) -> None:
        self.settings = settings or load_device_settings()
        self.output_path = Path(output_path)
        self.is_busy = is_busy or (lambda: False)
        self.initial_camera_probe_delay_seconds = max(0.0, initial_camera_probe_delay_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._latest_snapshot: dict[str, Any] | None = None
        self._last_camera_probe_monotonic: float | None = None
        self._started_monotonic = time.monotonic()

    @property
    def latest_snapshot(self) -> dict[str, Any] | None:
        """Return the most recent snapshot collected by the monitor."""
        return self._latest_snapshot

    def start(self) -> bool:
        """Start the monitor thread if it is not already running."""
        if self._thread is not None and self._thread.is_alive():
            return False

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="health-monitor",
        )
        self._thread.start()
        return True

    def stop(self, timeout: float = 5.0) -> None:
        """Request a clean shutdown and wait briefly for the thread to exit."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def run_once(self) -> dict[str, Any]:
        """Collect one snapshot, persist it, and log health transitions."""
        busy = bool(self.is_busy())
        should_probe_camera = self._should_probe_camera(busy)
        previous_snapshot = self._latest_snapshot
        snapshot = collect_health_snapshot(
            self.settings,
            previous_snapshot=previous_snapshot,
            probe_camera=should_probe_camera,
        )
        write_health_snapshot(snapshot, self.output_path)
        self._log_transitions(previous_snapshot, snapshot)
        self._latest_snapshot = snapshot
        if should_probe_camera:
            self._last_camera_probe_monotonic = time.monotonic()
        return snapshot

    def _run_loop(self) -> None:
        LOGGER.info("Health monitor started")
        interval_seconds = self.settings.reliability.health_check_interval_seconds

        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception:
                LOGGER.exception("Health monitor check failed")
            if self._stop_event.wait(interval_seconds):
                break

        LOGGER.info("Health monitor stopped")

    def _should_probe_camera(self, busy: bool) -> bool:
        """Return True when it is safe and due to run a real camera probe."""
        if busy:
            return False

        if self._last_camera_probe_monotonic is None:
            startup_elapsed = time.monotonic() - self._started_monotonic
            if startup_elapsed < self.initial_camera_probe_delay_seconds:
                return False
            return True

        elapsed = time.monotonic() - self._last_camera_probe_monotonic
        return elapsed >= self.settings.reliability.camera_probe_interval_seconds

    def _log_transitions(
        self,
        previous_snapshot: dict[str, Any] | None,
        snapshot: dict[str, Any],
    ) -> None:
        """Log health degradation and recovery as the aggregate status changes."""
        previous_status = None
        if previous_snapshot is not None:
            previous_status = previous_snapshot.get("overall_status")

        current_status = snapshot.get("overall_status")
        if previous_status == current_status:
            return

        if current_status == "degraded":
            LOGGER.warning("Health degraded: %s", snapshot)
        elif current_status == "healthy":
            LOGGER.info("Health recovered: %s", snapshot)
        else:
            LOGGER.info("Health status changed: %s", snapshot)


def _collect_cpu_health() -> dict[str, Any]:
    """Collect CPU temperature data when available."""
    temperature_c = _read_cpu_temperature_c()
    if temperature_c is None:
        return {
            "temperature_c": None,
            "status": "unknown",
            "message": "CPU temperature is unavailable on this system.",
        }

    status = "fail" if temperature_c >= CPU_TEMPERATURE_FAIL_C else "pass"
    message = f"CPU temperature is {temperature_c:.1f} C."
    if status == "fail":
        message = f"{message} Above recommended threshold."
    return {
        "temperature_c": round(temperature_c, 1),
        "status": status,
        "message": message,
    }


def _collect_memory_health() -> dict[str, Any]:
    """Collect memory usage details from /proc/meminfo."""
    memory_stats = _read_memory_stats()
    if memory_stats is None:
        return {
            "total_kb": None,
            "available_kb": None,
            "used_kb": None,
            "used_percent": None,
            "status": "unknown",
            "message": "Memory information is unavailable on this system.",
        }

    used_percent = memory_stats["used_percent"]
    status = "fail" if used_percent >= MEMORY_USED_FAIL_PERCENT else "pass"
    return {
        **memory_stats,
        "status": status,
        "message": f"Memory usage is {used_percent:.1f}%.",
    }


def _collect_network_health() -> dict[str, Any]:
    """Reuse the shared internet connectivity probe."""
    result = check_internet_connection()
    return {
        "status": result.status,
        "message": result.message,
    }


def _collect_camera_health(
    settings: DeviceSettings,
    *,
    previous_snapshot: dict[str, Any] | None,
    probe_camera: bool,
    probed_at: str,
) -> dict[str, Any]:
    """Reuse the shared camera check or keep the last known camera state."""
    if not probe_camera:
        previous_camera = None
        if previous_snapshot is not None:
            maybe_camera = previous_snapshot.get("camera")
            if isinstance(maybe_camera, dict):
                previous_camera = maybe_camera

        if previous_camera is not None:
            return {
                "status": str(previous_camera.get("status", "unknown")),
                "message": str(previous_camera.get("message", "Camera status unchanged.")),
                "last_probe_at": previous_camera.get("last_probe_at"),
            }

        return {
            "status": "unknown",
            "message": "Camera probe has not run yet.",
            "last_probe_at": None,
        }

    result = check_camera(settings)
    return {
        "status": result.status,
        "message": result.message,
        "last_probe_at": probed_at,
    }


def _resolve_overall_status(*components: dict[str, Any]) -> str:
    """Collapse component statuses into a simple overall health state."""
    statuses = [str(component.get("status", "unknown")).lower() for component in components]
    if any(status == "fail" for status in statuses):
        return "degraded"
    if statuses and all(status == "pass" for status in statuses):
        return "healthy"
    return "unknown"


def _read_cpu_temperature_c() -> float | None:
    """Read CPU temperature from sysfs or vcgencmd."""
    try:
        raw_value = CPU_TEMPERATURE_PATH.read_text(encoding="utf-8").strip()
        if raw_value:
            return int(raw_value) / 1000.0
    except (OSError, ValueError):
        pass

    try:
        result = subprocess.run(
            ["vcgencmd", "measure_temp"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    match = re.search(r"temp=([0-9.]+)", result.stdout)
    if not match:
        return None

    try:
        return float(match.group(1))
    except ValueError:
        return None


def _read_memory_stats() -> dict[str, Any] | None:
    """Parse basic memory usage values from /proc/meminfo."""
    try:
        lines = MEMORY_INFO_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    values: dict[str, int] = {}
    for line in lines:
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        parts = raw_value.strip().split()
        if not parts:
            continue
        try:
            values[key] = int(parts[0])
        except ValueError:
            continue

    total_kb = values.get("MemTotal")
    available_kb = values.get("MemAvailable")
    if total_kb is None or available_kb is None or total_kb <= 0:
        return None

    used_kb = max(0, total_kb - available_kb)
    used_percent = (used_kb / float(total_kb)) * 100.0
    return {
        "total_kb": total_kb,
        "available_kb": available_kb,
        "used_kb": used_kb,
        "used_percent": round(used_percent, 1),
    }


def _timestamp() -> str:
    """Return an ISO timestamp for health snapshots."""
    return datetime.now().isoformat(timespec="seconds")
