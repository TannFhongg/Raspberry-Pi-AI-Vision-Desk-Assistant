"""Background live-preview service for the touchscreen Flask UI."""

from __future__ import annotations

from dataclasses import replace
import io
import logging
import threading
import time
from typing import Any

from PIL import Image, ImageDraw

from camera.capture import (
    PICAMERA2_INSTALL_HINT,
    OPENCV_INSTALL_HINT,
    _apply_opencv_controls,
    _apply_picamera2_controls,
)
from hardware.camera_config import (
    build_camera_request,
    resolve_opencv_config,
    resolve_picamera2_config,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_PLACEHOLDER_SIZE = (960, 540)


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
        autofocus_mode: str | None = None,
        exposure: str | int | None = None,
        brightness: float | None = None,
        frame_interval_seconds: float = 0.15,
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
        )
        preview_width, preview_height = _build_preview_resolution(
            request.width,
            request.height,
        )

        self._request = replace(
            request,
            width=preview_width,
            height=preview_height,
            capture_delay_seconds=0.0,
            autofocus_mode="continuous" if request.autofocus_mode == "auto" else request.autofocus_mode,
        )
        self._frame_interval_seconds = max(0.05, frame_interval_seconds)
        self._preview_size = (preview_width, preview_height)
        self._condition = threading.Condition()
        self._latest_frame = _build_placeholder_frame(
            "Starting live camera feed...",
            size=self._preview_size,
        )
        self._paused = False
        self._stop_requested = False
        self._worker: threading.Thread | None = None

    def get_jpeg_frame(self, timeout_seconds: float = 1.0) -> bytes:
        """Return the latest JPEG frame, starting the worker on demand."""
        with self._condition:
            paused = self._paused

        if not paused:
            self._ensure_worker_started()
        deadline = time.monotonic() + max(0.0, timeout_seconds)

        with self._condition:
            while self._latest_frame is None and not self._stop_requested:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(timeout=remaining)

            if self._latest_frame is not None:
                return self._latest_frame

        return _build_placeholder_frame(
            "Live camera feed unavailable.",
            size=self._preview_size,
        )

    def pause(self) -> None:
        """Temporarily stop reading the camera so still capture can take over."""
        with self._condition:
            self._paused = True
            self._condition.notify_all()

    def resume(self) -> None:
        """Allow the worker to reopen the camera and continue preview updates."""
        with self._condition:
            self._paused = False
            self._condition.notify_all()

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
                        source.close()
                        source = None
                    time.sleep(0.1)
                    continue

                if source is None:
                    try:
                        source = _open_frame_source(self._request)
                        LOGGER.info("Live preview source opened")
                    except LivePreviewError as exc:
                        LOGGER.warning("Live preview unavailable: %s", exc)
                        self._update_frame(
                            _build_placeholder_frame(
                                "Live camera feed unavailable.",
                                subtitle=str(exc),
                                size=self._preview_size,
                            )
                        )
                        time.sleep(1.0)
                        continue

                try:
                    frame = source.read_frame()
                    jpeg_bytes = _encode_preview_frame(frame)
                    self._update_frame(jpeg_bytes)
                except Exception as exc:
                    LOGGER.warning("Live preview frame failed: %s", exc)
                    self._update_frame(
                        _build_placeholder_frame(
                            "Reconnecting live camera feed...",
                            size=self._preview_size,
                        )
                    )
                    source.close()
                    source = None
                    time.sleep(0.5)
                    continue

                time.sleep(self._frame_interval_seconds)
        finally:
            if source is not None:
                source.close()

    def _update_frame(self, frame_bytes: bytes) -> None:
        """Persist the newest preview frame and wake any waiting readers."""
        with self._condition:
            self._latest_frame = frame_bytes
            self._condition.notify_all()


def _build_preview_resolution(width: int, height: int) -> tuple[int, int]:
    """Scale the configured capture size down to a lightweight preview size."""
    longest_side = max(width, height)
    if longest_side <= DEFAULT_PLACEHOLDER_SIZE[0]:
        return (width, height)

    scale = DEFAULT_PLACEHOLDER_SIZE[0] / float(longest_side)
    preview_width = max(1, int(round(width * scale)))
    preview_height = max(1, int(round(height * scale)))
    return (preview_width, preview_height)


def _open_frame_source(request) -> "_BaseFrameSource":
    """Open the preferred live-preview backend with auto fallback support."""
    if request.backend == "auto":
        try:
            return _Picamera2FrameSource(request)
        except LivePreviewError as picamera_error:
            LOGGER.info("Picamera2 preview unavailable, falling back to OpenCV: %s", picamera_error)
            return _OpenCVFrameSource(request)

    if request.backend == "picamera2":
        return _Picamera2FrameSource(request)
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

    def close(self) -> None:
        raise NotImplementedError


class _Picamera2FrameSource(_BaseFrameSource):
    """Use the Raspberry Pi Picamera2 stack for continuous preview."""

    def __init__(self, request) -> None:
        try:
            from picamera2 import Picamera2
        except ImportError as exc:
            raise LivePreviewError(PICAMERA2_INSTALL_HINT) from exc

        self._picam2 = None
        try:
            picam2 = Picamera2(camera_num=request.camera_index)
            sensor_modes = getattr(picam2, "sensor_modes", None)
            camera_controls = getattr(picam2, "camera_controls", {})
            control_names = camera_controls.keys() if isinstance(camera_controls, dict) else ()
            resolved_config = resolve_picamera2_config(
                request=request,
                sensor_modes=sensor_modes,
                controls=control_names,
            )
            configuration = picam2.create_preview_configuration(
                main={
                    "size": (request.width, request.height),
                    "format": "RGB888",
                },
                buffer_count=4,
            )
            picam2.configure(configuration)
            picam2.start()
            _apply_picamera2_controls(picam2, resolved_config)
            self._picam2 = picam2
        except LivePreviewError:
            raise
        except Exception as exc:
            if self._picam2 is not None:
                self.close()
            raise LivePreviewError(f"Picamera2 preview could not start. {exc}") from exc

    def read_frame(self) -> Any:
        """Read the newest RGB frame from Picamera2."""
        if self._picam2 is None:
            raise LivePreviewError("Picamera2 preview is not running.")
        return self._picam2.capture_array("main")

    def close(self) -> None:
        """Stop and close the Picamera2 instance safely."""
        if self._picam2 is None:
            return
        try:
            self._picam2.stop()
        except Exception:
            pass
        try:
            self._picam2.close()
        except Exception:
            pass
        self._picam2 = None


class _OpenCVFrameSource(_BaseFrameSource):
    """Use OpenCV VideoCapture for continuous preview frames."""

    def __init__(self, request) -> None:
        try:
            import cv2
        except ImportError as exc:
            raise LivePreviewError(OPENCV_INSTALL_HINT) from exc

        self._cv2 = cv2
        self._camera = cv2.VideoCapture(request.camera_index)
        if not self._camera.isOpened():
            self.close()
            raise LivePreviewError(
                f"OpenCV could not open camera index {request.camera_index}."
            )

        resolved_config = resolve_opencv_config(request)
        self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, float(request.width))
        self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, float(request.height))
        _apply_opencv_controls(self._camera, resolved_config, cv2)

        for _ in range(3):
            self._camera.read()
            time.sleep(0.05)

    def read_frame(self) -> Any:
        """Read the newest frame and convert it from BGR into RGB."""
        if self._camera is None:
            raise LivePreviewError("OpenCV preview is not running.")

        success, frame = self._camera.read()
        if not success or frame is None or getattr(frame, "size", 0) <= 0:
            raise LivePreviewError("OpenCV preview could not read a frame.")

        if len(frame.shape) == 2:
            return frame
        if frame.shape[2] == 4:
            return frame[:, :, [2, 1, 0, 3]].copy()
        return frame[:, :, ::-1].copy()

    def close(self) -> None:
        """Release the OpenCV camera handle."""
        if self._camera is None:
            return
        try:
            self._camera.release()
        except Exception:
            pass
        self._camera = None
