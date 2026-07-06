"""Camera capture backends for Raspberry Pi CSI cameras and USB webcams."""

from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

VALID_BACKENDS = ("auto", "picamera2", "opencv")
PICAMERA2_INSTALL_HINT = (
    "Picamera2 is not available. On Raspberry Pi OS, install it with: "
    "sudo apt install -y python3-picamera2 and create the virtual environment with: "
    "python3 -m venv --system-site-packages .venv"
)
OPENCV_INSTALL_HINT = (
    "OpenCV is not available. On Raspberry Pi OS, install it with: "
    "sudo apt install -y python3-opencv and create the virtual environment with: "
    "python3 -m venv --system-site-packages .venv"
)


class CameraCaptureError(Exception):
    """Friendly error raised when camera capture fails."""


@dataclass(slots=True)
class CaptureResult:
    """Capture metadata returned after a successful image save."""

    output_path: Path
    backend_used: str


def capture_image(
    output_path: str = "static/captured.jpg",
    backend: str = "auto",
    camera_index: int = 0,
    width: int = 1280,
    height: int = 720,
) -> CaptureResult:
    """Capture an image using Picamera2 or OpenCV and save it to disk."""
    normalized_backend = backend.lower().strip()
    if normalized_backend not in VALID_BACKENDS:
        valid_values = ", ".join(VALID_BACKENDS)
        raise CameraCaptureError(
            f"Unsupported backend '{backend}'. Choose one of: {valid_values}"
        )

    destination = Path(output_path)

    if normalized_backend == "auto":
        picamera_error_message = ""
        _prepare_output_path(destination)
        try:
            _status("Trying Picamera2 backend first...")
            temporary_output = _build_temporary_output_path(destination)
            result = _capture_with_picamera2(temporary_output, width, height)
            _validate_output_file(result.output_path)
            _finalize_output_file(result.output_path, destination)
            return CaptureResult(output_path=destination, backend_used=result.backend_used)
        except CameraCaptureError as picamera_error:
            picamera_error_message = str(picamera_error)
            _status(f"Picamera2 failed: {picamera_error}")
            _status("Falling back to OpenCV backend...")
            _cleanup_temporary_file(locals().get("temporary_output"))

        _prepare_output_path(destination)
        try:
            temporary_output = _build_temporary_output_path(destination)
            result = _capture_with_opencv(temporary_output, camera_index, width, height)
            _validate_output_file(result.output_path)
            _finalize_output_file(result.output_path, destination)
            return CaptureResult(output_path=destination, backend_used=result.backend_used)
        except CameraCaptureError as opencv_error:
            _cleanup_temporary_file(locals().get("temporary_output"))
            raise CameraCaptureError(
                "Automatic camera capture failed. "
                f"Picamera2 error: {picamera_error_message} "
                f"OpenCV error: {opencv_error}"
            ) from opencv_error

    _prepare_output_path(destination)
    temporary_output = _build_temporary_output_path(destination)

    try:
        if normalized_backend == "picamera2":
            result = _capture_with_picamera2(temporary_output, width, height)
        else:
            result = _capture_with_opencv(temporary_output, camera_index, width, height)

        _validate_output_file(result.output_path)
        _finalize_output_file(result.output_path, destination)
        return CaptureResult(output_path=destination, backend_used=result.backend_used)
    except CameraCaptureError:
        _cleanup_temporary_file(temporary_output)
        raise


def _prepare_output_path(output_path: Path) -> None:
    """Create the output directory and confirm the destination is a file path."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            if output_path.is_dir():
                raise CameraCaptureError(
                    f"Output path '{output_path}' is a directory. Please provide a file path."
                )
    except CameraCaptureError:
        raise
    except OSError as exc:
        raise CameraCaptureError(
            f"Could not prepare output path '{output_path}'. {exc}"
        ) from exc


def _capture_with_picamera2(output_path: Path, width: int, height: int) -> CaptureResult:
    """Capture a still image using the Raspberry Pi Picamera2 stack."""
    try:
        from picamera2 import Picamera2
    except ImportError as exc:
        raise CameraCaptureError(PICAMERA2_INSTALL_HINT) from exc

    picam2 = None
    try:
        _status(f"Capturing image with Picamera2 at {width}x{height}...")
        picam2 = Picamera2()
        configuration = picam2.create_still_configuration(main={"size": (width, height)})
        picam2.configure(configuration)
        picam2.start()
        time.sleep(1.0)
        picam2.capture_file(str(output_path))
    except Exception as exc:
        raise CameraCaptureError(
            "Picamera2 could not capture an image. Make sure the CSI camera is connected correctly. "
            f"Original error: {exc}"
        ) from exc
    finally:
        if picam2 is not None:
            try:
                picam2.stop()
            except Exception:
                pass
            try:
                picam2.close()
            except Exception:
                pass

    return CaptureResult(output_path=output_path, backend_used="picamera2")


def _capture_with_opencv(
    output_path: Path, camera_index: int, width: int, height: int
) -> CaptureResult:
    """Capture an image using OpenCV VideoCapture for USB webcams."""
    try:
        import cv2
    except ImportError as exc:
        raise CameraCaptureError(OPENCV_INSTALL_HINT) from exc

    camera = None
    last_valid_frame = None

    try:
        _status(
            f"Capturing image with OpenCV camera index {camera_index} at {width}x{height}..."
        )
        camera = cv2.VideoCapture(camera_index)
        if not camera.isOpened():
            raise CameraCaptureError(
                f"OpenCV could not open camera index {camera_index}. "
                "Make sure a USB webcam is connected and not being used by another app."
            )

        camera.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))

        for _ in range(5):
            success, frame = camera.read()
            if success and frame is not None and getattr(frame, "size", 0) > 0:
                last_valid_frame = frame
            time.sleep(0.1)

        if last_valid_frame is None:
            raise CameraCaptureError(
                f"OpenCV opened camera index {camera_index}, but no valid frame was captured."
            )

        saved = cv2.imwrite(str(output_path), last_valid_frame)
        if not saved:
            raise CameraCaptureError(
                f"OpenCV captured a frame but could not save it to '{output_path}'."
            )
    except CameraCaptureError:
        raise
    except Exception as exc:
        raise CameraCaptureError(
            f"OpenCV capture failed for camera index {camera_index}. Original error: {exc}"
        ) from exc
    finally:
        if camera is not None:
            camera.release()

    return CaptureResult(output_path=output_path, backend_used="opencv")


def _validate_output_file(output_path: Path) -> None:
    """Confirm that the captured file exists and is not empty."""
    if not output_path.exists():
        raise CameraCaptureError(
            f"Capture finished but '{output_path}' was not created."
        )
    if output_path.stat().st_size <= 0:
        raise CameraCaptureError(
            f"Capture finished but '{output_path}' is empty."
        )


def _status(message: str) -> None:
    """Print a short status message for terminal-based testing."""
    print(message)


def _build_temporary_output_path(output_path: Path) -> Path:
    """Create a temporary file path in the target directory for atomic replacement."""
    try:
        temporary_file = tempfile.NamedTemporaryFile(
            delete=False,
            dir=output_path.parent,
            prefix=f".{output_path.stem}-",
            suffix=output_path.suffix,
        )
        temporary_file.close()
    except OSError as exc:
        raise CameraCaptureError(
            f"Could not create a temporary file for '{output_path}'. {exc}"
        ) from exc

    return Path(temporary_file.name)


def _finalize_output_file(source_path: Path, destination_path: Path) -> None:
    """Replace the destination only after a new capture has been saved successfully."""
    try:
        source_path.replace(destination_path)
    except OSError as exc:
        _cleanup_temporary_file(source_path)
        raise CameraCaptureError(
            f"Capture succeeded but could not move the image to '{destination_path}'. {exc}"
        ) from exc


def _cleanup_temporary_file(path: Path | None) -> None:
    """Remove any temporary capture file left behind after a failed attempt."""
    if path is None:
        return

    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
