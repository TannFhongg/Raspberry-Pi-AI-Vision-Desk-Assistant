"""Health-summary QObject exposed to the Qt Quick header and camera screen."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Property, Signal


class HealthStateModel(QObject):
    """Singleton-style QObject for health summary metadata."""

    updatedAtChanged = Signal()
    cameraPreviewStateChanged = Signal()
    cameraPreviewTitleChanged = Signal()
    cameraPreviewMessageChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._updated_at = ""
        self._camera_preview_state = "READY"
        self._camera_preview_title = "Preview Image Here"
        self._camera_preview_message = "Select a mode to open the live preview."

    def update(self, **changes: Any) -> None:
        """Apply a partial health update and emit changed signals."""
        for key, value in changes.items():
            if key == "updated_at" and value != self._updated_at:
                self._updated_at = str(value)
                self.updatedAtChanged.emit()
            elif key == "camera_preview_state" and value != self._camera_preview_state:
                self._camera_preview_state = str(value)
                self.cameraPreviewStateChanged.emit()
            elif key == "camera_preview_title" and value != self._camera_preview_title:
                self._camera_preview_title = str(value)
                self.cameraPreviewTitleChanged.emit()
            elif key == "camera_preview_message" and value != self._camera_preview_message:
                self._camera_preview_message = str(value)
                self.cameraPreviewMessageChanged.emit()

    @Property(str, notify=updatedAtChanged)
    def updatedAt(self) -> str:
        return self._updated_at

    @Property(str, notify=cameraPreviewStateChanged)
    def cameraPreviewState(self) -> str:
        return self._camera_preview_state

    @Property(str, notify=cameraPreviewTitleChanged)
    def cameraPreviewTitle(self) -> str:
        return self._camera_preview_title

    @Property(str, notify=cameraPreviewMessageChanged)
    def cameraPreviewMessage(self) -> str:
        return self._camera_preview_message

