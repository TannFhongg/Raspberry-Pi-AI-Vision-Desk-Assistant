"""Shared runtime bootstrap for the native VisionDesk Qt frontend."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Callable

from dotenv import load_dotenv

from ai.modes import get_mode
from camera.live_preview import LivePreviewService
from config import load_device_settings
from hardware import LEDIndicator
from system import (
    HealthMonitor,
    OfflineRetryQueue,
    configure_logging,
    safe_rmtree,
    safe_unlink,
)
from system.device_setup import has_configured_openai_key
from system.factory_reset import resume_pending_factory_reset
from system.result_history import ResultHistoryStore
from system.setup_flow import SetupStateStore
from system.ui_catalog import (
    MODE_LABELS,
    READY_DETAIL,
    SETUP_STEPS,
    UI_MODE_TO_INTERNAL_MODE,
    default_ui_mode_for_internal,
    resolve_mode_pair,
)
from visiondesk.paths import VisionDeskPaths, resolve_visiondesk_paths
from visiondesk.version import __version__

from qt_app.mock_backend import MockLivePreviewService

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RuntimePaths:
    """Filesystem paths used by the Qt frontend runtime."""

    path_mode: str = field(default_factory=lambda: resolve_visiondesk_paths().path_mode)
    repo_root: Path = field(default_factory=lambda: resolve_visiondesk_paths().repo_root)
    releases_dir: Path = field(default_factory=lambda: resolve_visiondesk_paths().releases_dir)
    setup_state_path: Path = field(default_factory=lambda: resolve_visiondesk_paths().setup_state_path)
    health_status_path: Path = field(default_factory=lambda: resolve_visiondesk_paths().health_status_path)
    latest_result_path: Path = field(default_factory=lambda: resolve_visiondesk_paths().latest_result_path)
    result_history_path: Path = field(default_factory=lambda: resolve_visiondesk_paths().result_history_path)
    private_data_path: Path = field(default_factory=lambda: resolve_visiondesk_paths().private_data_path)
    env_file_path: Path = field(default_factory=lambda: resolve_visiondesk_paths().env_file_path)
    config_path: Path = field(default_factory=lambda: resolve_visiondesk_paths().config_path)
    logs_dir: Path = field(default_factory=lambda: resolve_visiondesk_paths().logs_dir)
    app_root: Path = field(default_factory=lambda: resolve_visiondesk_paths().app_root)

    @property
    def private_current_path(self) -> Path:
        return self.private_data_path / "current"

    @property
    def private_retry_path(self) -> Path:
        return self.private_data_path / "retry"

    @property
    def private_quarantine_path(self) -> Path:
        return self.private_data_path / "quarantine"

    @property
    def private_cache_path(self) -> Path:
        return self.private_data_path / "cache"

    @property
    def offline_retry_queue_path(self) -> Path:
        return self.private_data_path / "retry_queue.json"

    @property
    def data_dir(self) -> Path:
        return self.private_data_path.parent

    @property
    def reset_marker_path(self) -> Path:
        return self.data_dir / "factory_reset_state.json"

    def to_visiondesk_paths(self) -> VisionDeskPaths:
        """Convert the runtime-specific view into the shared path resolver schema."""
        current_release_link = self.app_root if self.path_mode == "production" else self.repo_root
        return VisionDeskPaths(
            path_mode=self.path_mode,
            repo_root=self.repo_root,
            app_root=self.app_root,
            releases_dir=self.releases_dir,
            current_release_link=current_release_link,
            config_dir=self.config_path.parent,
            config_path=self.config_path,
            data_dir=self.data_dir,
            logs_dir=self.logs_dir,
            env_file_path=self.env_file_path,
        )

    @classmethod
    def from_environment(cls) -> "RuntimePaths":
        """Build runtime paths from the active environment."""
        paths = resolve_visiondesk_paths()
        return cls(
            path_mode=paths.path_mode,
            repo_root=paths.repo_root,
            releases_dir=paths.releases_dir,
            setup_state_path=paths.setup_state_path,
            health_status_path=paths.health_status_path,
            latest_result_path=paths.latest_result_path,
            result_history_path=paths.result_history_path,
            private_data_path=paths.private_data_path,
            env_file_path=paths.env_file_path,
            config_path=paths.config_path,
            logs_dir=paths.logs_dir,
            app_root=paths.app_root,
        )


class VisionDeskRuntime:
    """Own shared settings, services, and persistence used by the Qt app."""

    RESTART_EXIT_CODE = 75

    def __init__(
        self,
        *,
        mock_hardware: bool = False,
        paths: RuntimePaths | None = None,
        settings=None,
        purge_on_startup: bool | None = None,
    ) -> None:
        self.mock_hardware = bool(mock_hardware)
        initial_paths = paths or RuntimePaths.from_environment()
        load_dotenv(initial_paths.env_file_path, override=False)
        self.paths = paths or RuntimePaths.from_environment()
        self.settings = settings or load_device_settings(config_path=self.paths.config_path)
        recovered_reset = resume_pending_factory_reset(
            paths=self.paths.to_visiondesk_paths(),
            settings=self.settings,
        )
        if recovered_reset is not None:
            self.settings = load_device_settings(config_path=self.paths.config_path)
        configure_logging(settings=self.settings, logs_dir=self.paths.logs_dir)
        self.app_version = __version__
        self._requested_exit_code = 0
        self.default_capture_internal_mode = self.settings.ai.default_mode
        self.default_capture_mode = default_ui_mode_for_internal(
            self.default_capture_internal_mode,
            "read_text",
        )
        self.ready_detail = READY_DETAIL
        self.result_history_limit = self.settings.retention.text_history_max_items
        self.text_history_retention_days = self.settings.retention.text_history_retention_days
        self.preview_refresh_ms = max(
            33,
            int(round(1000.0 / max(1.0, self.settings.camera.preview.target_fps))),
        )
        self.health_refresh_ms = 5000
        self.cpu_warning_threshold = 70.0
        self.cpu_error_threshold = 80.0
        self.memory_warning_threshold = 75.0
        self.memory_error_threshold = 90.0
        self.screen_width, self.screen_height = self._resolve_screen_size()

        self.paths.private_data_path.mkdir(parents=True, exist_ok=True)
        self.paths.private_quarantine_path.mkdir(parents=True, exist_ok=True)

        self.led_indicator = LEDIndicator.create(
            pin=self.settings.led.pin,
            enabled=self.settings.led.enabled and not self.mock_hardware,
            active_high=self.settings.led.active_high,
        )
        self.live_preview = self._build_live_preview_service()
        self.setup_state_store = SetupStateStore(
            state_path=self.paths.setup_state_path,
            quarantine_dir=self.paths.private_quarantine_path,
            timestamp_provider=self.timestamp,
            app_version=self.app_version,
            setup_steps=SETUP_STEPS,
            build_gpio_requirements=self.build_setup_gpio_requirements,
            legacy_setup_is_complete=self._legacy_setup_is_complete,
            legacy_setup_completed_at=lambda: self.settings.setup.completed_at,
            current_wifi_ssid=lambda: self.settings.network.wifi.ssid,
            current_wifi_connection_name=lambda: self.settings.network.wifi.connection_name,
            current_wifi_auto_connect=lambda: self.settings.network.wifi.auto_connect,
            current_wifi_managed_by=lambda: self.settings.network.wifi.managed_by,
            has_configured_openai_key=has_configured_openai_key,
            current_openai_key=lambda: os.getenv("OPENAI_API_KEY"),
        )
        self.result_history_store = ResultHistoryStore(
            history_path=self.paths.result_history_path,
            quarantine_dir=self.paths.private_quarantine_path,
            retention_days=self.text_history_retention_days,
            result_limit=self.result_history_limit,
            resolve_mode_pair=lambda selected_mode, selected_mode_internal: resolve_mode_pair(
                selected_mode,
                selected_mode_internal,
                default_capture_mode=self.default_capture_mode,
                default_capture_internal_mode=self.default_capture_internal_mode,
            ),
            mode_label_resolver=self.history_mode_label,
            timestamp_provider=self.timestamp,
        )
        self.offline_retry_queue = self._build_offline_retry_queue()
        self.health_monitor: HealthMonitor | None = None

        should_purge_on_startup = (
            self.settings.retention.purge_on_startup
            if purge_on_startup is None
            else bool(purge_on_startup)
        )
        if should_purge_on_startup:
            self.purge_runtime_artifacts(delete_all=False)

    @property
    def offline_retry_enabled(self) -> bool:
        """Return True when deferred retry is enabled for this runtime."""
        return self.offline_retry_queue is not None

    def timestamp(self) -> str:
        """Return an ISO timestamp matching the shared persistence format."""
        from datetime import datetime

        return datetime.now().isoformat(timespec="seconds")

    def _legacy_setup_is_complete(self) -> bool:
        return bool(getattr(self.settings.setup, "completed", False))

    def setup_is_complete(self) -> bool:
        """Return True when first-boot setup is complete."""
        if hasattr(self, "setup_state_store"):
            return self.setup_state_store.is_setup_complete()
        return self._legacy_setup_is_complete()

    def resolve_mode_pair(self, selected_mode: Any, selected_mode_internal: Any = None) -> tuple[str, str]:
        """Resolve the UI mode id plus internal pipeline mode."""
        return resolve_mode_pair(
            selected_mode,
            selected_mode_internal,
            default_capture_mode=self.default_capture_mode,
            default_capture_internal_mode=self.default_capture_internal_mode,
        )

    def history_mode_label(self, selected_mode: str, selected_mode_internal: str) -> str:
        """Return the stored user-facing label for a history entry."""
        if selected_mode in MODE_LABELS:
            return MODE_LABELS[selected_mode]
        if selected_mode_internal:
            return get_mode(selected_mode_internal).name
        return "Saved Result"

    def build_setup_gpio_requirements(self) -> list[dict[str, Any]]:
        """Return the GPIO buttons that setup verification should track."""
        required: list[dict[str, Any]] = [
            {"label": "capture", "pin": self.settings.button.pin, "pressed": False},
        ]
        mode_button_pairs = [
            ("mode_read_text", self.settings.button.mode_button_1_pin),
            ("mode_summarize_document", self.settings.button.mode_button_2_pin),
            ("mode_analyze_image", self.settings.button.mode_button_3_pin),
            ("mode_professional_assistant", self.settings.button.mode_button_4_pin),
            ("mode_solve_problem", self.settings.button.mode_button_5_pin),
        ]
        for label, pin in mode_button_pairs:
            if pin is None:
                continue
            required.append({"label": label, "pin": pin, "pressed": False})
        if self.settings.button.back_button_pin is not None:
            required.append(
                {"label": "back", "pin": self.settings.button.back_button_pin, "pressed": False}
            )
        return required

    def build_setup_required_pin_map(self) -> dict[str, int]:
        """Return the setup verifier pin map keyed by logical label."""
        return {
            button["label"]: int(button["pin"])
            for button in self.build_setup_gpio_requirements()
        }

    def mark_setup_complete(self, completion_timestamp: str) -> None:
        """Apply in-memory setup completion so service restart is the only remaining step."""
        self.settings.setup.completed = True
        self.settings.setup.completed_at = completion_timestamp
        self.settings.setup.version = 1
        self.settings.localization.locale = "en"

    def mark_setup_incomplete(self) -> None:
        """Apply in-memory setup reset so the next launch re-enters the wizard."""
        self.settings.setup.completed = False
        self.settings.setup.completed_at = ""
        self.settings.setup.version = 0

    def request_restart(self, exit_code: int | None = None) -> None:
        """Ask the Qt entrypoint to exit with a restart-triggering code."""
        self._requested_exit_code = self.RESTART_EXIT_CODE if exit_code is None else int(exit_code)

    @property
    def requested_exit_code(self) -> int:
        """Return the pending process exit code requested by the runtime."""
        return self._requested_exit_code

    def load_health_snapshot(self) -> dict[str, Any] | None:
        """Return the most recent health snapshot from memory or disk."""
        if self.mock_hardware:
            return {
                "overall_status": "healthy",
                "updated_at": self.timestamp(),
                "cpu": {
                    "status": "pass",
                    "temperature_c": 49.0,
                    "message": "CPU temperature is 49.0 C.",
                },
                "memory": {
                    "status": "pass",
                    "used_percent": 38.0,
                    "message": "Memory usage is 38.0%.",
                },
                "network": {
                    "status": "pass",
                    "message": "Internet connection check succeeded.",
                },
                "camera": {
                    "status": "pass",
                    "message": "Mock camera preview is active.",
                },
            }
        if self.health_monitor is not None and self.health_monitor.latest_snapshot is not None:
            return self.health_monitor.latest_snapshot
        if not self.paths.health_status_path.is_file():
            return None
        try:
            snapshot = json.loads(self.paths.health_status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return snapshot if isinstance(snapshot, dict) else None

    def ensure_health_monitor_started(self, *, is_busy: Callable[[], bool]) -> None:
        """Start the background health monitor once when setup is complete."""
        if self.mock_hardware or not self.setup_is_complete() or not self.settings.reliability.health_monitor_enabled:
            return
        if self.health_monitor is None:
            self.health_monitor = HealthMonitor(
                settings=self.settings,
                output_path=self.paths.health_status_path,
                is_busy=is_busy,
            )
        self.health_monitor.start()

    def ensure_offline_retry_started(
        self,
        *,
        analyze_func: Callable[[Any], Any],
        success_callback: Callable[[Any, Any], None],
        failure_callback: Callable[[Any, Exception, bool], None],
    ) -> None:
        """Start the shared offline retry queue once when configured."""
        queue = self.offline_retry_queue
        if queue is None or not self.setup_is_complete():
            return
        queue.start(
            analyze_func=analyze_func,
            success_callback=success_callback,
            failure_callback=failure_callback,
        )

    def quiesce_for_factory_reset(self, *, timeout_seconds: float = 5.0) -> None:
        """Stop background writers before a reset deletes their persisted state."""
        failures: list[str] = []
        if self.health_monitor is not None and not self.health_monitor.stop(timeout=timeout_seconds):
            failures.append("health monitor")
        if self.offline_retry_queue is not None and not self.offline_retry_queue.close(timeout=timeout_seconds):
            failures.append("offline retry worker")
        if failures:
            raise RuntimeError(f"Could not stop {' and '.join(failures)} before factory reset.")

    def cleanup_current_private_media(self) -> None:
        """Delete current working capture files."""
        current_path = self.paths.private_current_path
        if current_path.is_dir():
            for entry in list(current_path.iterdir()):
                if entry.is_dir():
                    safe_rmtree(entry)
                else:
                    safe_unlink(entry)
            try:
                next(current_path.iterdir())
            except StopIteration:
                safe_rmtree(current_path)
            except OSError:
                pass

    def purge_runtime_artifacts(self, *, delete_all: bool) -> None:
        """Apply shared privacy cleanup defaults for startup or full deletion."""
        self.cleanup_current_private_media()
        if self.offline_retry_queue is not None:
            if delete_all:
                self.offline_retry_queue.clear()
            else:
                self.offline_retry_queue.prune()
        if delete_all:
            safe_rmtree(self.paths.private_current_path)
            safe_rmtree(self.paths.private_retry_path)
            safe_unlink(self.paths.result_history_path)
            safe_unlink(self.paths.latest_result_path)
            safe_unlink(self.paths.setup_state_path)
            safe_rmtree(self.paths.private_quarantine_path)
            self.result_history_store.invalidate_cache()
            return
        entries = self.result_history_store.load_entries()
        if entries or self.paths.result_history_path.is_file():
            self.result_history_store.write_entries(entries)

    def delete_all_user_data(self) -> None:
        """Delete retained user data while preserving device config and secrets."""
        self.cleanup_current_private_media()
        if self.offline_retry_queue is not None:
            self.offline_retry_queue.clear()
        else:
            safe_rmtree(self.paths.private_retry_path)
            safe_unlink(self.paths.offline_retry_queue_path)
        self.result_history_store.clear()
        safe_unlink(self.paths.latest_result_path)
        safe_rmtree(self.paths.private_quarantine_path)
        self.result_history_store.invalidate_cache()
        self.paths.private_data_path.mkdir(parents=True, exist_ok=True)
        self.paths.private_quarantine_path.mkdir(parents=True, exist_ok=True)

    def shutdown(self) -> None:
        """Stop background services and release hardware resources."""
        if self.health_monitor is not None:
            self.health_monitor.stop()
        if self.offline_retry_queue is not None:
            self.offline_retry_queue.close()
        if hasattr(self.live_preview, "close"):
            self.live_preview.close()

    def _build_live_preview_service(self) -> LivePreviewService | MockLivePreviewService:
        if self.mock_hardware:
            return MockLivePreviewService(
                width=self.settings.camera.preview.resolution.width,
                height=self.settings.camera.preview.resolution.height,
            )
        return LivePreviewService(
            backend=self.settings.camera.backend,
            camera_index=self.settings.camera.index,
            width=self.settings.camera.resolution.width,
            height=self.settings.camera.resolution.height,
            preview_width=self.settings.camera.preview.resolution.width,
            preview_height=self.settings.camera.preview.resolution.height,
            autofocus_mode=self.settings.camera.autofocus_mode,
            exposure=self.settings.camera.exposure,
            brightness=self.settings.camera.brightness,
            force_mjpeg=self.settings.camera.preview.force_mjpeg,
            target_fps=self.settings.camera.preview.target_fps,
            frame_interval_seconds=self.preview_refresh_ms / 1000.0,
            prefer_snapshot_on_linux=(
                sys.platform.startswith("linux")
                and not self.settings.camera.preview.force_mjpeg
            ),
        )

    def _build_offline_retry_queue(self) -> OfflineRetryQueue | None:
        if self.mock_hardware or not self.settings.offline_retry.enabled:
            return None
        return OfflineRetryQueue(
            queue_path=self.paths.offline_retry_queue_path,
            storage_dir=self.paths.private_retry_path,
            poll_interval_seconds=self.settings.offline_retry.poll_interval_seconds,
            max_entries=self.settings.offline_retry.max_items,
            max_attempts=self.settings.offline_retry.max_attempts,
            initial_delay_seconds=self.settings.offline_retry.initial_delay_seconds,
            max_delay_seconds=self.settings.offline_retry.max_delay_seconds,
            retention_hours=self.settings.retention.retry_media_retention_hours,
            min_free_bytes=self.settings.offline_retry.min_free_mb * 1024 * 1024,
            max_storage_bytes=self.settings.offline_retry.max_storage_mb * 1024 * 1024,
            quarantine_dir=self.paths.private_quarantine_path,
        )

    def _resolve_screen_size(self) -> tuple[int, int]:
        width = max(240, min(1920, self.settings.display.size.width))
        height = max(240, min(1920, self.settings.display.size.height))
        orientation = self.settings.display.orientation
        if orientation == "landscape" and width < height:
            return height, width
        if orientation == "portrait" and width > height:
            return height, width
        return width, height
