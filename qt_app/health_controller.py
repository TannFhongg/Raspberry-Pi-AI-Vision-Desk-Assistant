"""Health-summary controller for the native Qt frontend."""

from __future__ import annotations

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
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.runtime = runtime
        self.camera_controller = camera_controller
        self.ui_state_provider = ui_state_provider
        self.busy_provider = busy_provider
        self.state_model = HealthStateModel(self)
        self.metrics_model = DictListModel(
            ["key", "label", "value", "state", "message", "title", "value_size", "aria_label"],
            self,
        )
        self.camera_analysis_model = DictListModel(
            ["key", "label", "status", "message"],
            self,
        )
        self._summary: dict[str, Any] = {}
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
        self.summaryChanged.emit()

    def summary(self) -> dict[str, Any]:
        """Return the last computed summary payload."""
        return dict(self._summary)

