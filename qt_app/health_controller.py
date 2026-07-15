"""Health-summary controller for the native Qt frontend."""

from __future__ import annotations

import os
import shutil
from typing import Any, Callable

from PySide6.QtCore import QObject, Property, QTimer, Signal

from qt_app.camera_controller import CameraController
from qt_app.models import DictListModel, HealthStateModel
from qt_app.navigation_controller import NavigationController
from qt_app.runtime import VisionDeskRuntime
from system.ui_presenters import HealthSummaryBuilder


class HealthController(QObject):
    """Own header health pills and camera-analysis summary models."""

    summaryChanged = Signal()

    def __init__(
        self,
        runtime: VisionDeskRuntime,
        *,
        camera_controller: CameraController,
        ui_state_provider: Callable[[], dict[str, Any]],
        busy_provider: Callable[[], bool],
        camera_capabilities_provider: Callable[[], list[dict[str, Any]]] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.runtime = runtime
        self.camera_controller = camera_controller
        self.ui_state_provider = ui_state_provider
        self.busy_provider = busy_provider
        self.camera_capabilities_provider = camera_capabilities_provider or (lambda: [])
        self.state_model = HealthStateModel(self)
        self.metrics_model = DictListModel(
            ["key", "label", "value", "state", "message", "title", "value_size", "aria_label"],
            self,
        )
        self.camera_analysis_model = DictListModel(
            ["key", "label", "status", "message"],
            self,
        )
        self.device_health_model = DictListModel(
            ["key", "section", "title", "value", "message", "tone"],
            self,
        )
        self._summary: dict[str, Any] = {}
        self._display_diagnostics: dict[str, str] = {}
        self._builder = HealthSummaryBuilder(
            load_ui_state=self.ui_state_provider,
            resolve_mode_pair=runtime.resolve_mode_pair,
            resolve_render_screen=NavigationController.resolve_render_screen,
            load_health_snapshot=runtime.load_health_snapshot,
            load_setup_state=runtime.setup_state_store.load_state,
            setup_is_complete=runtime.setup_is_complete,
            live_preview_runtime_status=self.camera_controller.runtime_status,
            is_live_preview_screen=lambda screen: str(screen or "").strip().lower() in {"setup", "camera"},
            camera_autofocus_mode=runtime.settings.camera.autofocus_mode,
            cpu_warning_threshold=runtime.cpu_warning_threshold,
            cpu_error_threshold=runtime.cpu_error_threshold,
            memory_warning_threshold=runtime.memory_warning_threshold,
            memory_error_threshold=runtime.memory_error_threshold,
            offline_retry_enabled=runtime.offline_retry_enabled,
        )
        self._timer = QTimer(self)
        self._timer.setInterval(runtime.health_refresh_ms)
        self._timer.timeout.connect(self.refresh)

    @Property(QObject, constant=True)
    def metricsModel(self) -> DictListModel:
        return self.metrics_model

    @Property(QObject, constant=True)
    def cameraAnalysisModel(self) -> DictListModel:
        return self.camera_analysis_model

    @Property(QObject, constant=True)
    def stateModel(self) -> HealthStateModel:
        return self.state_model

    @Property(QObject, constant=True)
    def deviceHealthModel(self) -> DictListModel:
        return self.device_health_model

    def start(self) -> None:
        """Start periodic health refresh plus the shared monitor when configured."""
        self.runtime.ensure_health_monitor_started(is_busy=self.busy_provider)
        self.refresh()
        self._timer.start()

    def stop(self) -> None:
        """Stop periodic health refresh."""
        self._timer.stop()

    def refresh(self) -> None:
        """Refresh the live health summary from shared backend signals."""
        summary = self._builder.build_summary()
        self._summary = summary
        self.metrics_model.set_items(list(summary.get("metrics", [])))
        camera_preview = summary.get("camera_preview", {})
        self.state_model.update(
            updated_at=summary.get("updated_at", ""),
            camera_preview_state=camera_preview.get("screen_state", "READY"),
            camera_preview_title=camera_preview.get("title", ""),
            camera_preview_message=camera_preview.get("message", ""),
        )
        analysis_summary = summary.get("camera_analysis", {})
        self.camera_analysis_model.set_items(
            [
                {
                    "key": key,
                    "label": str(value.get("label", "")).upper(),
                    "status": value.get("status", "unknown"),
                    "message": value.get("message", ""),
                }
                for key, value in analysis_summary.items()
            ]
        )
        self.device_health_model.set_items(self._build_device_health_cards(summary))
        self.summaryChanged.emit()

    def summary(self) -> dict[str, Any]:
        """Return the last computed summary payload."""
        return dict(self._summary)

    def set_display_diagnostics(self, values: dict[str, Any]) -> None:
        """Publish non-sensitive Qt display details in Device Health."""
        self._display_diagnostics = {str(key): str(value) for key, value in values.items()}
        self.device_health_model.set_items(self._build_device_health_cards(self._summary))
        self.summaryChanged.emit()

    def _build_device_health_cards(self, summary: dict[str, Any]) -> list[dict[str, str]]:
        """Build Device Health from existing snapshots without new polling work."""
        snapshot = self.runtime.load_health_snapshot() or {}
        global_status = summary.get("global_status", {})
        cpu = snapshot.get("cpu", {}) if isinstance(snapshot.get("cpu"), dict) else {}
        memory = snapshot.get("memory", {}) if isinstance(snapshot.get("memory"), dict) else {}
        network = snapshot.get("network", {}) if isinstance(snapshot.get("network"), dict) else {}
        camera = snapshot.get("camera", {}) if isinstance(snapshot.get("camera"), dict) else {}
        cards: list[dict[str, str]] = [
            self._card(
                "overall",
                "Overview",
                "Overall device status",
                str(global_status.get("text", "Starting")),
                "Use Refresh to read the latest shared health checks.",
                str(global_status.get("tone", "info")),
            ),
            self._card(
                "cpu_temperature",
                "Performance",
                "CPU temperature",
                self._temperature_label(cpu.get("temperature_c")),
                self._safe_message(cpu.get("message"), "CPU temperature is unavailable."),
                self._tone(cpu.get("status")),
            ),
            self._card(
                "memory",
                "Performance",
                "Memory usage",
                self._percent_label(memory.get("used_percent")),
                self._safe_message(memory.get("message"), "Memory usage is unavailable."),
                self._tone(memory.get("status")),
            ),
            self._storage_card(),
            self._card(
                "wifi",
                "Connection",
                "Wi-Fi connection",
                self._connection_label(network.get("status")),
                self._safe_message(network.get("message"), "Wi-Fi status is unavailable."),
                self._tone(network.get("status")),
            ),
            self._card(
                "network_name",
                "Connection",
                "Configured network",
                self.runtime.settings.network.wifi.ssid or "Not configured",
                "Network passwords are never shown.",
                "success" if self.runtime.settings.network.wifi.ssid else "warning",
            ),
            self._card(
                "camera",
                "Camera",
                "Camera availability",
                self._connection_label(camera.get("status")),
                self._safe_message(camera.get("message"), "Camera status is unavailable."),
                self._tone(camera.get("status")),
            ),
            self._card(
                "camera_resolution",
                "Camera",
                "Capture resolution",
                f"{self.runtime.settings.camera.resolution.width} × {self.runtime.settings.camera.resolution.height}",
                "Configured still-capture resolution.",
                "info",
            ),
            self._card(
                "ai",
                "Service",
                "AI service",
                "Configured" if bool(os.getenv("OPENAI_API_KEY", "").strip()) else "Setup required",
                "Reachability is checked when an image is confirmed for analysis.",
                "success" if bool(os.getenv("OPENAI_API_KEY", "").strip()) else "warning",
            ),
            self._card(
                "app_version",
                "Service",
                "Application version",
                self.runtime.app_version,
                "The native VisionDesk service is running.",
                "success",
            ),
            self._card(
                "last_check",
                "Service",
                "Last successful health check",
                str(summary.get("updated_at") or "Not available"),
                "Checks use the configured monitor interval; refresh does not force an expensive camera probe.",
                "info" if summary.get("updated_at") else "warning",
            ),
            self._card(
                "updates",
                "Service",
                "Update status",
                "No update status available",
                "Updates are checked through the managed release workflow.",
                "info",
            ),
        ]
        for capability in self.camera_capabilities_provider():
            key = str(capability.get("key", "camera_control"))
            supported = bool(capability.get("supported", False))
            cards.append(
                self._card(
                    f"camera_{key}",
                    "Camera controls",
                    str(capability.get("label", "Camera control")),
                    "Available" if supported else "Not supported",
                    str(capability.get("message", "Not supported by this camera")),
                    "success" if supported else "info",
                )
            )
        technical_labels = (
            ("screen_name", "Screen name"),
            ("geometry", "Screen geometry"),
            ("available_geometry", "Available geometry"),
            ("fullscreen_geometry", "Fullscreen geometry"),
            ("device_pixel_ratio", "Device pixel ratio"),
            ("logical_dpi", "Logical DPI"),
            ("physical_dpi", "Physical DPI"),
            ("selected_font_family", "Selected body font"),
            ("font_fallback", "Font fallback order"),
            ("qt_platform", "Qt platform"),
        )
        for key, title in technical_labels:
            if key not in self._display_diagnostics:
                continue
            cards.append(
                self._card(
                    f"display_{key}",
                    "Technical Details",
                    title,
                    self._display_diagnostics[key],
                    "Display diagnostics contain no credentials or captured content.",
                    "info",
                )
            )
        cards.append(
            self._card(
                "display_text_rendering",
                "Technical Details",
                "Text rendering policy",
                "NativeRendering" if self.runtime.settings.display.text_rendering == "native" else "QtRendering",
                "Use UI_TEXT_RENDERING=native only for a real-panel comparison.",
                "info",
            )
        )
        return cards

    def _storage_card(self) -> dict[str, str]:
        try:
            usage = shutil.disk_usage(self.runtime.paths.private_data_path)
            used_percent = 100.0 * (usage.used / max(1, usage.total))
            value = f"{used_percent:.0f}% used"
            message = f"{usage.free // (1024 * 1024)} MB free for VisionDesk data."
            tone = "warning" if used_percent >= 85.0 else "success"
        except OSError:
            value, message, tone = "Unavailable", "Storage usage is unavailable.", "warning"
        return self._card("storage", "Performance", "Storage usage", value, message, tone)

    @staticmethod
    def _card(key: str, section: str, title: str, value: str, message: str, tone: str) -> dict[str, str]:
        return {"key": key, "section": section, "title": title, "value": value, "message": message, "tone": tone}

    @staticmethod
    def _safe_message(value: Any, fallback: str) -> str:
        return str(value or fallback).replace("\n", " ")[:180]

    @staticmethod
    def _temperature_label(value: Any) -> str:
        return f"{float(value):.1f} °C" if isinstance(value, (int, float)) else "Unavailable"

    @staticmethod
    def _percent_label(value: Any) -> str:
        return f"{float(value):.0f}% used" if isinstance(value, (int, float)) else "Unavailable"

    @staticmethod
    def _connection_label(value: Any) -> str:
        return "Connected" if str(value).lower() in {"pass", "healthy"} else "Unavailable" if str(value).lower() in {"unknown", ""} else "Needs attention"

    @staticmethod
    def _tone(value: Any) -> str:
        return "success" if str(value).lower() in {"pass", "healthy"} else "warning" if str(value).lower() in {"warning", "unknown", ""} else "error"
