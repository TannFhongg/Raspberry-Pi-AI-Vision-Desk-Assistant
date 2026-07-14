"""Capture-only worker used before the user has confirmed an image."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from pipeline import PipelineError, build_capture_session_paths, run_capture
from qt_app.mock_backend import build_mock_preview_bytes


class ReviewCaptureWorker(QObject):
    """Capture a private frame and never contact the AI service."""

    progress = Signal(str)
    finished = Signal(object)

    def __init__(self, runtime) -> None:
        super().__init__()
        self.runtime = runtime

    @Slot()
    def run(self) -> None:
        captured_path: Path | None = None
        try:
            captured_path, _unused = build_capture_session_paths(self.runtime.paths.private_current_path)
            if self.runtime.mock_hardware:
                self.progress.emit("Capturing image...")
                captured_path.parent.mkdir(parents=True, exist_ok=True)
                captured_path.write_bytes(
                    build_mock_preview_bytes(
                        title="Captured image",
                        subtitle="Review and adjust before analysis.",
                        size=(1920, 1080),
                    )
                )
                payload = {
                    "kind": "captured",
                    "captured_path": captured_path,
                    "camera_backend_used": "mock-camera",
                    "camera_resolution": (1920, 1080),
                }
            else:
                result = run_capture(
                    output_path=str(captured_path),
                    backend=self.runtime.settings.camera.backend,
                    camera_index=self.runtime.settings.camera.index,
                    width=self.runtime.settings.camera.resolution.width,
                    height=self.runtime.settings.camera.resolution.height,
                    autofocus_mode=self.runtime.settings.camera.autofocus_mode,
                    exposure=self.runtime.settings.camera.exposure,
                    brightness=self.runtime.settings.camera.brightness,
                    capture_delay_seconds=self.runtime.settings.camera.capture_delay_seconds,
                    status_callback=self.progress.emit,
                )
                payload = {
                    "kind": "captured",
                    "captured_path": result.captured_path,
                    "camera_backend_used": result.camera_backend_used,
                    "camera_resolution": result.camera_resolution,
                }
        except PipelineError as exc:
            if captured_path is not None:
                captured_path.unlink(missing_ok=True)
            payload = {"kind": "error", "friendly_error": str(exc), "technical_error": str(exc), "retryable": True}
        except Exception as exc:
            if captured_path is not None:
                captured_path.unlink(missing_ok=True)
            payload = {"kind": "error", "friendly_error": "VisionDesk could not capture an image.", "technical_error": str(exc), "retryable": True}
        self.finished.emit(payload)
