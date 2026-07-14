"""Capture/pipeline controller running the backend workflow in a QThread."""

from __future__ import annotations

import errno
import logging
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Property, QThread, Signal, Slot

from pipeline import (
    PipelineError,
    PipelineResult,
    build_capture_session_paths,
    run_analyze,
    run_analyze_confirmed,
    run_capture,
    run_capture_analyze,
    save_latest_result,
)
from qt_app.image_provider import CachedImageStore
from qt_app.mock_backend import build_mock_pipeline_result, build_mock_preview_bytes
from qt_app.models import DictListModel
from qt_app.pipeline_review_worker import ReviewCaptureWorker
from qt_app.runtime import VisionDeskRuntime
from system.error_mapping import redact_technical_detail
from system.offline_retry import OfflineRetryQueueError, OfflineRetryQueueFullError
from system.ui_presenters import (
    build_progress_steps,
    humanize_error,
    pipeline_progress_to_step_index,
    processing_error_step,
    processing_progress_for_message,
)

LOGGER = logging.getLogger(__name__)
PREVIEW_RELEASE_TIMEOUT_SECONDS = 2.0


class _PipelineWorker(QObject):
    """Worker object moved to a dedicated `QThread` for capture/analyze jobs."""

    progress = Signal(str)
    finished = Signal(object)

    def __init__(
        self,
        runtime: VisionDeskRuntime,
        *,
        selected_mode: str,
        selected_mode_internal: str,
        confirmed_path: str | Path | None = None,
    ) -> None:
        super().__init__()
        self.runtime = runtime
        self.selected_mode = selected_mode
        self.selected_mode_internal = selected_mode_internal
        self.confirmed_path = Path(confirmed_path) if confirmed_path else None
        self._terminal_emitted = False

    @Slot()
    def run(self) -> None:
        """Execute one capture request and emit exactly one terminal payload."""
        captured_path = None
        processed_path = None
        payload: dict[str, Any] | None = None
        try:
            if self.confirmed_path is not None:
                result, preview_bytes = self._run_confirmed_submission()
            elif self.runtime.mock_hardware:
                for message in (
                    "Capturing image...",
                    "Preprocessing image...",
                    "Sending image to OpenAI Vision...",
                ):
                    self.progress.emit(message)
                    time.sleep(0.08)
                result = build_mock_pipeline_result(self.selected_mode_internal)
                preview_bytes = build_mock_preview_bytes(
                    title="Latest Preview",
                    subtitle="Mock processed result cached in memory.",
                )
            else:
                captured_path, processed_path = build_capture_session_paths(
                    self.runtime.paths.private_current_path
                )
                result = run_capture_analyze(
                    mode=self.selected_mode_internal,
                    backend=self.runtime.settings.camera.backend,
                    camera_index=self.runtime.settings.camera.index,
                    width=self.runtime.settings.camera.resolution.width,
                    height=self.runtime.settings.camera.resolution.height,
                    captured_path=str(captured_path),
                    processed_path=str(processed_path),
                    grayscale=self.runtime.settings.camera.grayscale,
                    max_dimension=self.runtime.settings.camera.max_dimension,
                    screen_optimization=self.runtime.settings.vision.screen_optimization,
                    autofocus_mode=self.runtime.settings.camera.autofocus_mode,
                    exposure=self.runtime.settings.camera.exposure,
                    brightness=self.runtime.settings.camera.brightness,
                    capture_delay_seconds=self.runtime.settings.camera.capture_delay_seconds,
                    status_callback=self.progress.emit,
                )
                preview_bytes = self._read_preview_bytes(result.processed_path or result.captured_path)
            save_latest_result(result, output_path=str(self.runtime.paths.latest_result_path))
            history_entry = self.runtime.result_history_store.append_result(
                result,
                self.selected_mode,
                self.selected_mode_internal,
            )
            payload = {
                "kind": "success",
                "terminal_state": "DONE",
                "result": result,
                "history_entry": history_entry,
                "preview_bytes": preview_bytes,
                "selected_mode": self.selected_mode,
                "selected_mode_internal": self.selected_mode_internal,
            }
        except PipelineError as exc:
            try:
                payload = self._retry_or_error_payload(exc)
            except Exception as enqueue_error:
                payload = self._retry_enqueue_failure_payload(exc, enqueue_error)
        except Exception as exc:
            LOGGER.exception("Unexpected pipeline worker failure")
            payload = self._unexpected_error_payload(exc)
        finally:
            try:
                self.runtime.cleanup_current_private_media()
            except Exception:
                LOGGER.exception("Could not clean private pipeline media after terminal outcome")
            if payload is None:
                payload = self._unexpected_error_payload(RuntimeError("Pipeline did not produce an outcome"))
            self._emit_terminal(payload)

    def _run_confirmed_submission(self) -> tuple[PipelineResult, bytes]:
        """Analyze only the image explicitly confirmed in the review screen."""
        if self.confirmed_path is None:
            raise PipelineError("No confirmed image is available.")
        if self.runtime.mock_hardware:
            self.progress.emit("Sending confirmed image to OpenAI Vision...")
            time.sleep(0.08)
            mock = build_mock_pipeline_result(self.selected_mode_internal)
            result = PipelineResult(
                captured_path=None,
                processed_path=self.confirmed_path,
                answer=mock.answer,
                mode=self.selected_mode_internal,
                camera_backend_used="mock-camera",
                camera_resolution=mock.camera_resolution,
                status="success",
                warnings=mock.warnings,
                model_used=mock.model_used,
                duration_seconds=mock.duration_seconds,
            )
        else:
            result = run_analyze_confirmed(
                self.selected_mode_internal,
                self.confirmed_path,
                status_callback=self.progress.emit,
            )
        return result, self._read_preview_bytes(self.confirmed_path)

    def _retry_or_error_payload(self, exc: PipelineError) -> dict[str, Any]:
        queue = self.runtime.offline_retry_queue
        processed_path = getattr(exc, "processed_path", None)
        retry_asset_available = isinstance(processed_path, Path) and processed_path.is_file()
        if bool(getattr(exc, "retryable", False)) and retry_asset_available and queue is None:
            return {
                "kind": "error",
                "terminal_state": "ERROR",
                "error_code": "RETRY_DISABLED",
                "friendly_error": "Offline retry is not available for this capture.",
                "technical_error": f"RETRY_DISABLED: {exc}",
                "selected_mode": self.selected_mode,
                "selected_mode_internal": self.selected_mode_internal,
            }
        if (
            queue is not None
            and bool(getattr(exc, "retryable", False))
            and retry_asset_available
        ):
            entry = queue.enqueue(
                selected_mode=self.selected_mode,
                selected_mode_internal=self.selected_mode_internal,
                processed_path=processed_path,
                camera_backend_used=getattr(exc, "camera_backend_used", None)
                or self.runtime.settings.camera.backend,
                camera_resolution=getattr(exc, "camera_resolution", None),
                error_message=str(exc),
                error_category=humanize_error(str(exc)).lower().replace(" ", "_"),
            )
            try:
                queue_position = queue.pending_count()
            except Exception:
                LOGGER.exception("Could not read offline retry queue position after enqueue")
                queue_position = 0
            friendly_error = humanize_error(str(exc))
            queued_message = (
                "Saved for automatic retry.\n"
                f"Reason: {friendly_error}.\n"
                f"Queue position: {queue_position}.\n"
                "The assistant will retry this capture again when network/OpenAI is available."
            )
            queued_result = PipelineResult(
                captured_path=None,
                processed_path=queue.resolve_processed_path(entry),
                answer=queued_message,
                mode=self.selected_mode_internal or self.runtime.default_capture_internal_mode,
                camera_backend_used=entry.camera_backend_used or self.runtime.settings.camera.backend,
                camera_resolution=entry.camera_resolution,
                status="queued",
                retry_status="queued",
                error_summary=friendly_error,
            )
            try:
                save_latest_result(queued_result, output_path=str(self.runtime.paths.latest_result_path))
            except OSError:
                LOGGER.exception("Could not save latest result for an already-queued retry")
            return {
                "kind": "queued",
                "terminal_state": "RETRY_QUEUED",
                "result": queued_result,
                "history_entry": None,
                "preview_bytes": self._read_preview_bytes(queue.resolve_processed_path(entry)),
                "friendly_error": friendly_error,
                "technical_error": str(exc),
                "selected_mode": self.selected_mode,
                "selected_mode_internal": self.selected_mode_internal,
            }
        return {
            "kind": "error",
            "terminal_state": "ERROR",
            "friendly_error": humanize_error(str(exc)),
            "technical_error": str(exc),
            "selected_mode": self.selected_mode,
            "selected_mode_internal": self.selected_mode_internal,
        }

    def _retry_enqueue_failure_payload(self, original_error: PipelineError, enqueue_error: Exception) -> dict[str, Any]:
        """Return ERROR when a retryable result cannot be durably queued."""
        error_code = self._retry_enqueue_error_code(enqueue_error)
        LOGGER.error(
            "Offline retry enqueue failed code=%s original_error=%s enqueue_error=%s",
            error_code,
            redact_technical_detail(original_error),
            redact_technical_detail(enqueue_error),
        )
        return {
            "kind": "error",
            "terminal_state": "ERROR",
            "error_code": error_code,
            "friendly_error": "VisionDesk could not save this capture for retry.",
            "technical_error": f"{error_code}: {original_error}",
            "selected_mode": self.selected_mode,
            "selected_mode_internal": self.selected_mode_internal,
        }

    @staticmethod
    def _retry_enqueue_error_code(error: Exception) -> str:
        if isinstance(error, OfflineRetryQueueFullError):
            return "RETRY_QUEUE_FULL"
        if isinstance(error, OSError) and error.errno == errno.ENOSPC:
            return "DISK_FULL"
        if isinstance(error, OfflineRetryQueueError):
            detail = str(error).lower()
            if "corrupt" in detail or "invalid" in detail:
                return "RETRY_STATE_CORRUPT"
            return "RETRY_STORAGE_ERROR"
        return "RETRY_STORAGE_ERROR"

    def _unexpected_error_payload(self, error: Exception) -> dict[str, Any]:
        return {
            "kind": "error",
            "terminal_state": "ERROR",
            "friendly_error": "VisionDesk could not complete this capture.",
            "technical_error": f"Unexpected error: {error}",
            "selected_mode": self.selected_mode,
            "selected_mode_internal": self.selected_mode_internal,
        }

    def _emit_terminal(self, payload: dict[str, Any]) -> None:
        """Prevent duplicate terminal signals if a worker is invoked unexpectedly."""
        if self._terminal_emitted:
            LOGGER.error("Pipeline worker attempted to emit a duplicate terminal payload")
            return
        self._terminal_emitted = True
        self.finished.emit(payload)

    @staticmethod
    def _read_preview_bytes(path: str | Path | None) -> bytes:
        if path is None:
            return b""
        try:
            return Path(path).read_bytes()
        except OSError:
            return b""


class PipelineController(QObject):
    """Run the real backend pipeline in a worker thread and expose progress."""

    busyChanged = Signal()
    progressChanged = Signal()
    payloadReady = Signal(object)
    reviewCaptureReady = Signal(object)

    def __init__(
        self,
        runtime: VisionDeskRuntime,
        *,
        result_image_store: CachedImageStore,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.runtime = runtime
        self.result_image_store = result_image_store
        self.progress_steps_model = DictListModel(["label", "state", "state_label"], self)
        self._busy = False
        self._resetting = False
        self._last_start_error = ""
        self._progress_state = "IDLE"
        self._progress_message = ""
        self._progress_tone = "active"
        self._progress_error_step = -1
        self._current_step = -1
        self._thread: QThread | None = None
        self._worker: _PipelineWorker | None = None
        self._terminal_received = False
        self._update_progress_models()

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=progressChanged)
    def progressState(self) -> str:
        return self._progress_state

    @Property(str, notify=progressChanged)
    def progressMessage(self) -> str:
        return self._progress_message

    @Property(str, notify=progressChanged)
    def progressTone(self) -> str:
        return self._progress_tone

    @Property(int, notify=progressChanged)
    def progressErrorStep(self) -> int:
        return self._progress_error_step

    @Property(int, notify=progressChanged)
    def currentStep(self) -> int:
        return self._current_step

    @Property(QObject, constant=True)
    def progressStepsModel(self) -> DictListModel:
        return self.progress_steps_model

    @Property(str, notify=progressChanged)
    def lastStartError(self) -> str:
        """Return the safe user-facing reason a capture could not begin."""
        return self._last_start_error

    def start_capture(self, *, selected_mode: str, selected_mode_internal: str) -> bool:
        """Start one capture/analyze run unless the pipeline is already busy."""
        if self._busy or self._resetting:
            return False
        if not self.runtime.live_preview.pause(timeout_seconds=PREVIEW_RELEASE_TIMEOUT_SECONDS):
            self._last_start_error = "Camera is still busy. Wait a moment and try capture again."
            LOGGER.warning("Capture cancelled because live preview did not release the camera")
            self.runtime.live_preview.resume()
            self._set_progress(
                progress_state="ERROR",
                progress_message=self._last_start_error,
                progress_error_step=0,
            )
            return False
        self._last_start_error = ""
        self._terminal_received = False
        self._set_busy(True)
        self._set_progress(
            progress_state="CAPTURING",
            progress_message="Capturing image...",
            progress_error_step=-1,
        )
        thread = QThread(self)
        worker = _PipelineWorker(
            self.runtime,
            selected_mode=selected_mode,
            selected_mode_internal=selected_mode_internal,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_worker_progress)
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_worker_refs)
        self._thread = thread
        self._worker = worker
        thread.start()
        return True

    def start_capture_for_review(self) -> bool:
        """Capture a frame for review. This path cannot call the AI service."""
        if self._busy or self._resetting:
            return False
        if not self.runtime.live_preview.pause(timeout_seconds=PREVIEW_RELEASE_TIMEOUT_SECONDS):
            self._last_start_error = "Camera is still busy. Wait a moment and try capture again."
            self.runtime.live_preview.resume()
            self._set_progress(
                progress_state="ERROR",
                progress_message=self._last_start_error,
                progress_error_step=0,
            )
            return False
        self._last_start_error = ""
        self._terminal_received = False
        self._set_busy(True)
        self._set_progress(
            progress_state="CAPTURING",
            progress_message="Capturing image...",
            progress_error_step=-1,
        )
        thread = QThread(self)
        worker = ReviewCaptureWorker(self.runtime)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_worker_progress)
        worker.finished.connect(self._on_review_capture_finished)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_worker_refs)
        self._thread = thread
        self._worker = worker
        thread.start()
        return True

    def start_submit_confirmed(self, *, selected_mode: str, selected_mode_internal: str, confirmed_path: str | Path) -> bool:
        """Submit a review-rendered image once; no capture or second preprocess occurs."""
        if self._busy or self._resetting:
            return False
        confirmed = Path(confirmed_path)
        if not confirmed.is_file():
            self._last_start_error = "The confirmed image is no longer available. Retake the image."
            return False
        self._last_start_error = ""
        self._terminal_received = False
        self._set_busy(True)
        self._set_progress(
            progress_state="ANALYZING",
            progress_message="Sending confirmed image to OpenAI Vision...",
            progress_error_step=-1,
        )
        thread = QThread(self)
        worker = _PipelineWorker(
            self.runtime,
            selected_mode=selected_mode,
            selected_mode_internal=selected_mode_internal,
            confirmed_path=confirmed,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_worker_progress)
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_worker_refs)
        self._thread = thread
        self._worker = worker
        thread.start()
        return True

    def set_resetting(self, resetting: bool) -> bool:
        """Block new capture jobs while reset work owns shared persistence."""
        if resetting and self._busy:
            return False
        self._resetting = bool(resetting)
        return True

    def close(self) -> None:
        """Stop any active worker thread."""
        thread = self._thread
        self._thread = None
        self._worker = None
        if thread is None:
            return
        try:
            if thread.isRunning():
                thread.quit()
                thread.wait(1000)
        except RuntimeError:
            # Qt already deleted the thread object after a normal worker shutdown.
            return

    def analyze_offline_retry_entry(self, entry) -> PipelineResult:
        """Re-run analysis for a deferred offline retry queue entry."""
        processed_path = self.runtime.offline_retry_queue.resolve_processed_path(entry)
        result = run_analyze(
            mode=entry.selected_mode_internal,
            captured_path=str(processed_path),
            processed_path=str(processed_path),
            grayscale=self.runtime.settings.camera.grayscale,
            max_dimension=self.runtime.settings.camera.max_dimension,
            screen_optimization=self.runtime.settings.vision.screen_optimization,
        )
        return PipelineResult(
            captured_path=None,
            processed_path=processed_path if processed_path.is_file() else result.processed_path,
            answer=result.answer,
            mode=entry.selected_mode_internal,
            camera_backend_used=entry.camera_backend_used or result.camera_backend_used,
            camera_resolution=entry.camera_resolution or result.camera_resolution,
            status="success",
            warnings=result.warnings,
            model_used=result.model_used,
            duration_seconds=result.duration_seconds,
            retry_status="retry_successful",
        )

    def record_offline_retry_success(self, entry, result: PipelineResult) -> None:
        """Persist successful offline retry output without disrupting the active Qt screen."""
        save_latest_result(result, output_path=str(self.runtime.paths.latest_result_path))
        self.runtime.result_history_store.append_result(
            result,
            entry.selected_mode,
            entry.selected_mode_internal,
        )

    def record_offline_retry_failure(self, entry, error: Exception, retryable: bool) -> None:
        """Log non-interrupting offline retry failures."""
        if retryable:
            LOGGER.warning(
                "Offline retry deferred again entry=%s ui_mode=%s internal_mode=%s error=%s",
                entry.id,
                entry.selected_mode,
                entry.selected_mode_internal,
                error,
            )
            return
        LOGGER.error(
            "Offline retry dropped entry=%s ui_mode=%s internal_mode=%s error=%s",
            entry.id,
            entry.selected_mode,
            entry.selected_mode_internal,
            error,
        )

    def _on_worker_progress(self, message: str) -> None:
        progress_state, current_step, detail = processing_progress_for_message(message)
        self._set_progress(
            progress_state=progress_state,
            progress_message=detail,
            progress_error_step=-1,
            current_step=current_step,
        )

    def _on_worker_finished(self, payload: dict[str, Any]) -> None:
        if self._terminal_received:
            LOGGER.error("Ignoring duplicate pipeline terminal payload")
            return
        self._terminal_received = True
        kind = payload.get("kind")
        if kind == "success":
            self._set_progress(
                progress_state="DONE",
                progress_message="Processing complete.",
                progress_error_step=-1,
            )
        elif kind == "queued":
            self._set_progress(
                progress_state="RETRY_QUEUED",
                progress_message="Saved for automatic retry.",
                progress_error_step=1,
                current_step=1,
            )
        else:
            self._set_progress(
                progress_state="ERROR",
                progress_message=payload.get("friendly_error", "Analysis failed"),
                progress_error_step=processing_error_step(self._progress_state, self._current_step),
            )
        if payload.get("preview_bytes"):
            if self.result_image_store.set_bytes(payload["preview_bytes"]):
                pass
        else:
            self.result_image_store.clear()
        if not self._resetting:
            self.runtime.live_preview.resume()
        self._set_busy(False)
        self.payloadReady.emit(payload)

    def _on_review_capture_finished(self, payload: dict[str, Any]) -> None:
        """Finish the pre-review phase without resuming a camera under review."""
        kind = payload.get("kind")
        if kind == "captured":
            self._set_progress(
                progress_state="DONE",
                progress_message="Image captured. Review it before analysis.",
                progress_error_step=-1,
            )
        else:
            self._set_progress(
                progress_state="ERROR",
                progress_message=payload.get("friendly_error", "Capture failed"),
                progress_error_step=0,
                current_step=0,
            )
            self.runtime.live_preview.resume()
        self._set_busy(False)
        self.reviewCaptureReady.emit(payload)

    def _set_busy(self, value: bool) -> None:
        if value != self._busy:
            self._busy = value
            self.busyChanged.emit()

    def _set_progress(
        self,
        *,
        progress_state: str,
        progress_message: str,
        progress_error_step: int,
        current_step: int | None = None,
    ) -> None:
        self._progress_state = progress_state
        self._progress_error_step = progress_error_step
        if current_step is None:
            current_step = pipeline_progress_to_step_index(
                progress_state,
                progress_error_step=progress_error_step,
            )
        self._current_step = current_step
        if progress_state == "ERROR":
            self._progress_tone = "error"
        elif progress_state == "RETRY_QUEUED":
            self._progress_tone = "queued"
        elif progress_state == "DONE":
            self._progress_tone = "done"
        else:
            self._progress_tone = "active"
        self._progress_message = progress_message
        self._update_progress_models()
        self.progressChanged.emit()

    def _update_progress_models(self) -> None:
        resolved_error_step = self._progress_error_step
        if self._progress_state == "ERROR" and resolved_error_step < 0:
            resolved_error_step = processing_error_step(self._progress_state, self._current_step)
        self.progress_steps_model.set_items(
            build_progress_steps(
                self._progress_state,
                progress_error_step=resolved_error_step,
            )
        )

    @Slot()
    def _clear_worker_refs(self) -> None:
        self._thread = None
        self._worker = None
