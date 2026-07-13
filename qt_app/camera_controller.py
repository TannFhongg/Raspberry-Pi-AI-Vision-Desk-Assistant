"""Camera preview controller for the native Qt frontend."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from qt_app.image_provider import CachedImageStore
from qt_app.runtime import VisionDeskRuntime

LOGGER = logging.getLogger(__name__)


class CameraController(QObject):
    """Bridge the shared live-preview service into QML-friendly state."""

    previewRevisionChanged = Signal()
    previewAvailableChanged = Signal()
    previewErrorChanged = Signal()

    def __init__(
        self,
        runtime: VisionDeskRuntime,
        *,
        image_store: CachedImageStore,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.runtime = runtime
        self.image_store = image_store
        self._preview_available = False
        self._preview_error = ""
        self._active = False
        self._timer = QTimer(self)
        self._timer.setInterval(runtime.preview_refresh_ms)
        self._timer.timeout.connect(self._refresh_frame)

    @Property(int, notify=previewRevisionChanged)
    def previewRevision(self) -> int:
        return self.image_store.revision

    @Property(bool, notify=previewAvailableChanged)
    def previewAvailable(self) -> bool:
        return self._preview_available

    @Property(str, notify=previewErrorChanged)
    def previewError(self) -> str:
        return self._preview_error

    @Slot(bool, result=bool)
    def setActive(self, active: bool) -> bool:
        """Pause or resume live preview updates based on the current screen."""
        should_activate = bool(active)
        if should_activate == self._active:
            return True
        self._active = should_activate
        if should_activate:
            self.runtime.live_preview.resume()
            self._timer.start()
            self._refresh_frame()
            return True
        self._timer.stop()
        try:
            released = self.runtime.live_preview.pause()
            if not released:
                LOGGER.warning("Live preview did not release the camera while deactivating it")
            return released
        except Exception:
            LOGGER.exception("Failed to pause live preview")
            return False

    def runtime_status(self) -> tuple[bool, str]:
        """Return preview health information used by health presenters."""
        return self._preview_available, self._preview_error

    def close(self) -> None:
        """Stop polling and release the preview service."""
        self._timer.stop()
        try:
            self.runtime.live_preview.pause()
        except Exception:
            LOGGER.exception("Failed to pause live preview during shutdown")

    def _refresh_frame(self) -> None:
        """Read the latest in-memory preview frame and update provider state."""
        try:
            frame = self.runtime.live_preview.get_image_frame(timeout_seconds=0.05)
            if self.image_store.set_image(frame):
                self.previewRevisionChanged.emit()
        except Exception as exc:
            LOGGER.debug("Preview refresh failed: %s", exc)
        self._update_runtime_status()

    def _update_runtime_status(self) -> None:
        try:
            available = bool(self.runtime.live_preview.has_recent_frame())
        except Exception:
            available = False
        try:
            error = str(self.runtime.live_preview.latest_error_message() or "")
        except Exception:
            error = ""
        if available != self._preview_available:
            self._preview_available = available
            self.previewAvailableChanged.emit()
        if error != self._preview_error:
            self._preview_error = error
            self.previewErrorChanged.emit()
