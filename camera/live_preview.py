"""Background live-preview service for the touchscreen Flask UI."""

from __future__ import annotations

from dataclasses import replace
import io
import logging
import sys
import threading
import time
from typing import Any, Iterator

from PIL import Image, ImageDraw

from camera.capture import (
    OPENCV_INSTALL_HINT,
    camera_access,
    _describe_opencv_stream,
    _apply_opencv_controls,
    _configure_opencv_camera,
    _read_latest_valid_frame,
    _open_opencv_camera,
)
from hardware.camera_config import (
    build_camera_request,
    resolve_opencv_config,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_PLACEHOLDER_SIZE = (960, 540)
DEFAULT_PREVIEW_STREAM_RESOLUTION = (640, 360)
DEFAULT_RECENT_PREVIEW_FRAME_WINDOW_SECONDS = 10.0
PERSISTENT_PREVIEW_READ_ATTEMPTS = 1
SNAPSHOT_PREVIEW_MIN_FRAME_INTERVAL_SECONDS = 0.25


class LivePreviewError(Exception):
    """Friendly error raised when live camera preview cannot start."""


class LivePreviewService:
    """Maintain a background live-preview frame for the touchscreen UI."""

    def __init__(
        self,
        *,
        backend: str | None = None,
        camera_index: int | None = None,
        width: int | None = None,
        height: int | None = None,
        preview_width: int | None = None,
        preview_height: int | None = None,
        autofocus_mode: str | None = None,
        exposure: str | int | None = None,
        brightness: float | None = None,
        force_mjpeg: bool = True,
        target_fps: float = 0.0,
        frame_interval_seconds: float = 0.15,
        prefer_snapshot_on_linux: bool = False,
    ) -> None:
        request = build_camera_request(
            backend=backend,
            camera_index=camera_index,
            width=width,
            height=height,
            autofocus_mode=autofocus_mode,
            exposure=exposure,
            brightness=brightness,
            capture_delay_seconds=0.0,
            force_mjpeg=force_mjpeg,
            target_fps=target_fps,
        )
        preview_max_width = (
            DEFAULT_PREVIEW_STREAM_RESOLUTION[0]
            if preview_width is None
            else max(1, int(preview_width))
        )
        preview_max_height = (
            DEFAULT_PREVIEW_STREAM_RESOLUTION[1]
            if preview_height is None
            else max(1, int(preview_height))
        )
        preview_width, preview_height = _build_preview_resolution(
            request.width,
            request.height,
            max_width=preview_max_width,
            max_height=preview_max_height,
        )

        self._request = replace(
            request,
            width=preview_width,
            height=preview_height,
            capture_delay_seconds=0.0,
            autofocus_mode="continuous" if request.autofocus_mode == "auto" else request.autofocus_mode,
        )
        self._frame_interval_seconds = max(0.02, frame_interval_seconds)
        self._preview_size = (preview_width, preview_height)
        self._linux_mode = sys.platform.startswith("linux")
        self._linux_snapshot_fallback = bool(prefer_snapshot_on_linux and self._linux_mode)
        self._condition = threading.Condition()
        self._latest_frame = _build_placeholder_frame(
            "Starting live camera feed...",
            size=self._preview_size,
        )
        self._frame_version = 0
        self._paused = False
        self._source_active = False
        self._stop_requested = False
        self._last_success_monotonic: float | None = None
        self._last_error_message: str | None = None
        self._worker: threading.Thread | None = None

    def get_jpeg_frame(self, timeout_seconds: float = 1.0) -> bytes:
        """Return the latest JPEG frame, waiting for the worker when needed."""
        frame_bytes, _ = self._wait_for_frame(after_version=None, timeout_seconds=timeout_seconds)
        return frame_bytes

    def iter_mjpeg_stream(
        self,
        *,
        boundary: str = "frame",
        timeout_seconds: float = 1.0,
    ) -> Iterator[bytes]:
        """Yield a multipart MJPEG stream for browsers and kiosk displays."""
        last_version: int | None = None
        separator = boundary.encode("ascii")

        try:
            while True:
                frame_bytes, frame_version = self._wait_for_frame(
                    after_version=last_version,
                    timeout_seconds=timeout_seconds,
                )
                last_version = frame_version
                yield (
                    b"--" + separator + b"\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(frame_bytes)).encode("ascii") + b"\r\n"
                    b"Cache-Control: no-store, no-cache, must-revalidate, max-age=0\r\n"
                    b"Pragma: no-cache\r\n\r\n"
                    + frame_bytes
                    + b"\r\n"
                )
        except GeneratorExit:
            return

    def _wait_for_frame(
        self,
        *,
        after_version: int | None,
        timeout_seconds: float,
    ) -> tuple[bytes, int]:
        """Return the latest frame, optionally waiting for a newer version."""
        with self._condition:
            paused = self._paused

        if not paused:
            self._ensure_worker_started()
        deadline = time.monotonic() + max(0.0, timeout_seconds)

        with self._condition:
            while not self._stop_requested:
                has_frame = self._latest_frame is not None
                version_ready = after_version is None or self._frame_version > after_version
                if has_frame and version_ready:
                    return self._latest_frame, self._frame_version
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(timeout=remaining)

            fallback_frame = self._latest_frame
            fallback_version = self._frame_version

        if fallback_frame is not None:
            return fallback_frame, fallback_version
        return (
            _build_placeholder_frame(
                "Live camera feed unavailable.",
                size=self._preview_size,
            ),
            fallback_version,
        )

    def pause(self, timeout_seconds: float = 2.0) -> bool:
        """Stop the preview and wait for the current camera handle to be released."""
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        with self._condition:
            self._paused = True
            self._condition.notify_all()
            while self._source_active and not self._stop_requested:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    LOGGER.warning("Timed out waiting for live preview to release the camera")
                    return False
                self._condition.wait(timeout=remaining)
            return not self._source_active

    def resume(self) -> None:
        """Allow the worker to reopen the camera and continue preview updates."""
        with self._condition:
            self._paused = False
            self._condition.notify_all()

    def is_camera_active(self) -> bool:
        """Return True when the preview worker currently owns the camera."""
        with self._condition:
            return self._source_active and not self._paused

    def has_recent_frame(
        self,
        *,
        max_age_seconds: float = DEFAULT_RECENT_PREVIEW_FRAME_WINDOW_SECONDS,
    ) -> bool:
        """Return True when the preview has produced a frame recently."""
        with self._condition:
            last_success = self._last_success_monotonic
            paused = self._paused

        if paused or last_success is None:
            return False
        return (time.monotonic() - last_success) <= max(0.0, max_age_seconds)

    def latest_error_message(self) -> str | None:
        """Return the most recent preview error when available."""
        with self._condition:
            return self._last_error_message

    def close(self) -> None:
        """Stop the background preview thread."""
        with self._condition:
            self._stop_requested = True
            self._condition.notify_all()

        worker = self._worker
        if worker is not None:
            worker.join(timeout=1.0)

    def _ensure_worker_started(self) -> None:
        """Create the preview worker only once."""
        with self._condition:
            if self._worker is not None and self._worker.is_alive():
                return
            if self._stop_requested:
                self._stop_requested = False

            self._worker = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name="live-preview-worker",
            )
            self._worker.start()

    def _worker_loop(self) -> None:
        """Continuously refresh the in-memory preview frame."""
        source = None

        try:
            while True:
                with self._condition:
                    if self._stop_requested:
                        break
                    paused = self._paused

                if paused:
                    if source is not None:
                        source = self._close_source(source)
                    with self._condition:
                        if self._stop_requested:
                            break
                        self._condition.wait(timeout=0.1)
                    continue

                if source is None:
                    self._mark_source_active(True)
                    try:
                        source = _open_frame_source(
                            self._request,
                            prefer_snapshot_on_linux=self._linux_snapshot_fallback,
                        )
                        if (
                            self._linux_mode
                            and not self._linux_snapshot_fallback
                            and isinstance(source, _OpenCVSnapshotFrameSource)
                        ):
                            self._linux_snapshot_fallback = True
                        if not source.holds_camera_between_reads():
                            self._mark_source_active(False)
                        LOGGER.info(
                            "Live preview source opened mode=%s resolution=%sx%s force_mjpeg=%s target_fps=%.1f stream=%s",
                            source.describe_mode(),
                            self._request.width,
                            self._request.height,
                            self._request.force_mjpeg,
                            self._request.target_fps,
                            source.describe_stream() or "unknown",
                        )
                    except LivePreviewError as exc:
                        self._mark_source_active(False)
                        LOGGER.warning("Live preview unavailable: %s", exc)
                        self._record_frame_failure(str(exc))
                        self._update_frame(
                            _build_placeholder_frame(
                                "Live camera feed unavailable.",
                                subtitle=str(exc),
                                size=self._preview_size,
                            )
                        )
                        time.sleep(1.0)
                        continue

                    with self._condition:
                        if self._paused or self._stop_requested:
                            source = self._close_source(source)
                            continue

                try:
                    if not source.holds_camera_between_reads():
                        self._mark_source_active(True)
                    try:
                        frame = source.read_frame()
                    finally:
                        if not source.holds_camera_between_reads():
                            self._mark_source_active(False)
                    jpeg_bytes = _encode_preview_frame(frame)
                    self._record_frame_success()
                    self._update_frame(jpeg_bytes)
                except Exception as exc:
                    if self._linux_mode and isinstance(source, _OpenCVFrameSource):
                        self._linux_snapshot_fallback = True
                        LOGGER.warning(
                            "Persistent Linux preview failed; switching to snapshot fallback: %s",
                            exc,
                        )
                    LOGGER.warning("Live preview frame failed: %s", exc)
                    self._record_frame_failure(str(exc))
                    self._update_frame(
                        _build_placeholder_frame(
                            "Reconnecting live camera feed...",
                            size=self._preview_size,
                        )
                    )
                    source = self._close_source(source)
                    time.sleep(0.5)
                    continue

                with self._condition:
                    if self._stop_requested:
                        break
                    if self._paused:
                        continue
                    wait_interval_seconds = self._frame_interval_seconds
                    if source is not None and not source.holds_camera_between_reads():
                        wait_interval_seconds = max(
                            wait_interval_seconds,
                            SNAPSHOT_PREVIEW_MIN_FRAME_INTERVAL_SECONDS,
                        )
                    self._condition.wait(timeout=wait_interval_seconds)
        finally:
            if source is not None:
                self._close_source(source)
            else:
                self._mark_source_active(False)

    def _update_frame(self, frame_bytes: bytes) -> None:
        """Persist the newest preview frame and wake any waiting readers."""
        with self._condition:
            self._latest_frame = frame_bytes
            self._frame_version += 1
            self._condition.notify_all()

    def _mark_source_active(self, active: bool) -> None:
        """Track whether the preview worker currently owns the camera."""
        with self._condition:
            self._source_active = active
            self._condition.notify_all()

    def _record_frame_success(self) -> None:
        """Remember that preview delivered a usable camera frame."""
        with self._condition:
            self._last_success_monotonic = time.monotonic()
            self._last_error_message = None

    def _record_frame_failure(self, message: str) -> None:
        """Remember the latest preview error for UI health hints."""
        with self._condition:
            self._last_error_message = message

    def _close_source(self, source: "_BaseFrameSource | None") -> "_BaseFrameSource | None":
        """Close the active preview source and publish that the camera is free."""
        if source is None:
            self._mark_source_active(False)
            return None

        try:
            source.close()
        finally:
            self._mark_source_active(False)
        return None


def _build_preview_resolution(
    width: int,
    height: int,
    *,
    max_width: int = DEFAULT_PREVIEW_STREAM_RESOLUTION[0],
    max_height: int = DEFAULT_PREVIEW_STREAM_RESOLUTION[1],
) -> tuple[int, int]:
    """Scale preview frames down to a lighter resolution while preserving aspect ratio."""
    safe_width = max(1, int(width))
    safe_height = max(1, int(height))
    bounded_max_width = max(1, int(max_width))
    bounded_max_height = max(1, int(max_height))
    scale = min(
        1.0,
        bounded_max_width / float(safe_width),
        bounded_max_height / float(safe_height),
    )
    preview_width = _normalize_even_dimension(int(round(safe_width * scale)))
    preview_height = _normalize_even_dimension(int(round(safe_height * scale)))
    return (preview_width, preview_height)


def _normalize_even_dimension(value: int) -> int:
    """Prefer even preview dimensions so common webcam formats stay happy."""
    normalized = max(1, int(value))
    if normalized <= 2:
        return normalized
    if normalized % 2 == 0:
        return normalized
    return normalized - 1


def _open_frame_source(
    request,
    *,
    prefer_snapshot_on_linux: bool = False,
) -> "_BaseFrameSource":
    """Open the OpenCV live-preview source for the configured USB webcam."""
    if sys.platform.startswith("linux"):
        if prefer_snapshot_on_linux:
            return _OpenCVSnapshotFrameSource(request)
        try:
            return _OpenCVFrameSource(request)
        except LivePreviewError as exc:
            LOGGER.warning(
                "Persistent Linux preview could not start; falling back to snapshot mode: %s",
                exc,
            )
            return _OpenCVSnapshotFrameSource(request)
    return _OpenCVFrameSource(request)


def _encode_preview_frame(frame: Any) -> bytes:
    """Convert an RGB image array into a JPEG byte string."""
    image = Image.fromarray(frame)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=82)
    return buffer.getvalue()


def _build_placeholder_frame(
    message: str,
    *,
    subtitle: str = "",
    size: tuple[int, int],
) -> bytes:
    """Render a simple preview placeholder JPEG when no live frame is ready yet."""
    width, height = size
    image = Image.new("RGB", size, color=(9, 12, 18))
    draw = ImageDraw.Draw(image)
    accent_height = max(8, height // 18)
    draw.rectangle((0, 0, width, accent_height), fill=(40, 173, 96))

    title_y = max(24, height // 3)
    subtitle_y = min(height - 32, title_y + 34)
    draw.text((24, title_y), message, fill=(255, 255, 255))
    if subtitle:
        draw.text((24, subtitle_y), subtitle, fill=(192, 201, 214))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=82)
    return buffer.getvalue()


class _BaseFrameSource:
    """Small interface wrapper shared by each preview backend."""

    def read_frame(self) -> Any:
        raise NotImplementedError

    def holds_camera_between_reads(self) -> bool:
        """Return True when the source keeps the camera open continuously."""
        return False

    def describe_mode(self) -> str:
        """Return a short mode label for logs."""
        return "unknown"

    def describe_stream(self) -> str:
        """Return a compact stream summary for logs when available."""
        return ""

    def close(self) -> None:
        raise NotImplementedError


class _OpenCVFrameSource(_BaseFrameSource):
    """Use OpenCV VideoCapture for continuous preview frames."""

    def __init__(self, request) -> None:
        try:
            import cv2
        except ImportError as exc:
            raise LivePreviewError(OPENCV_INSTALL_HINT) from exc

        self._cv2 = cv2
        self._camera, self._backend_label = _open_opencv_camera(
            request.camera_index,
            cv2,
            error_cls=LivePreviewError,
        )

        resolved_config = resolve_opencv_config(request)
        _configure_opencv_camera(self._camera, request, resolved_config, cv2)
        self._stream_summary = _describe_opencv_stream(self._camera, cv2)

    def read_frame(self) -> Any:
        """Read the newest frame and convert it from BGR into RGB."""
        if self._camera is None:
            raise LivePreviewError("OpenCV preview is not running.")

        frame = _read_persistent_preview_frame(self._camera)
        if frame is None or getattr(frame, "size", 0) <= 0:
            raise LivePreviewError("OpenCV preview could not read a frame.")

        if len(frame.shape) == 2:
            return frame
        if frame.shape[2] == 4:
            return frame[:, :, [2, 1, 0, 3]].copy()
        return frame[:, :, ::-1].copy()

    def holds_camera_between_reads(self) -> bool:
        """Persistent preview keeps a camera handle open between frames."""
        return True

    def describe_mode(self) -> str:
        """Return a human-readable label for preview logs."""
        return "persistent"

    def describe_stream(self) -> str:
        """Return the actual persistent stream properties when known."""
        return self._stream_summary

    def close(self) -> None:
        """Release the OpenCV camera handle."""
        if self._camera is None:
            return
        try:
            self._camera.release()
        except Exception:
            pass
        self._camera = None


class _OpenCVSnapshotFrameSource(_BaseFrameSource):
    """Open the camera per frame on Linux for more reliable USB webcam previews."""

    def __init__(self, request) -> None:
        try:
            import cv2
        except ImportError as exc:
            raise LivePreviewError(OPENCV_INSTALL_HINT) from exc

        self._cv2 = cv2
        self._request = request
        self._resolved_config = resolve_opencv_config(request)

    def read_frame(self) -> Any:
        """Capture a fresh preview frame without holding the camera between reads."""
        camera = None
        try:
            with camera_access():
                camera, _backend_label = _open_opencv_camera(
                    self._request.camera_index,
                    self._cv2,
                    error_cls=LivePreviewError,
                )
                _configure_opencv_camera(camera, self._request, self._resolved_config, self._cv2)
                time.sleep(0.05)
                frame = _read_latest_valid_frame(
                    camera,
                    attempts=6,
                    inter_read_delay_seconds=0.03,
                )
                if frame is None or getattr(frame, "size", 0) <= 0:
                    raise LivePreviewError("OpenCV preview could not read a frame.")

                if len(frame.shape) == 2:
                    return frame
                if frame.shape[2] == 4:
                    return frame[:, :, [2, 1, 0, 3]].copy()
                return frame[:, :, ::-1].copy()
        finally:
            if camera is not None:
                try:
                    camera.release()
                except Exception:
                    pass

    def close(self) -> None:
        """Snapshot preview does not keep a persistent camera handle."""
        return None

    def describe_mode(self) -> str:
        """Return a human-readable label for preview logs."""
        return "snapshot"

    def describe_stream(self) -> str:
        """Snapshot mode reopens the camera for each frame."""
        return "open-per-frame"


def _read_persistent_preview_frame(camera):
    """Read a preview frame with minimal latency from a persistent camera handle."""
    return _read_latest_valid_frame(
        camera,
        attempts=PERSISTENT_PREVIEW_READ_ATTEMPTS,
        inter_read_delay_seconds=0.0,
    )
