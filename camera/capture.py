"""USB webcam capture backend for the Raspberry Pi AI Vision Desk Assistant."""

from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
import sys

from hardware.camera_config import (
    CameraConfigError,
    build_camera_request,
    read_image_resolution,
    resolve_opencv_config,
)

VALID_BACKENDS = ("opencv",)
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
    resolution: tuple[int, int] | None = None
    warnings: tuple[str, ...] = ()


def capture_image(
    output_path: str = "data/private/current/captured.jpg",
    backend: str | None = None,
    camera_index: int | None = None,
    width: int | None = None,
    height: int | None = None,
    autofocus_mode: str | None = None,
    exposure: str | int | None = None,
    brightness: float | None = None,
    capture_delay_seconds: float | None = None,
) -> CaptureResult:
    """Capture an image using OpenCV and save it to disk."""
    try:
        request = build_camera_request(
            backend=backend,
            camera_index=camera_index,
            width=width,
            height=height,
            autofocus_mode=autofocus_mode,
            exposure=exposure,
            brightness=brightness,
            capture_delay_seconds=capture_delay_seconds,
        )
    except CameraConfigError as exc:
        raise CameraCaptureError(str(exc)) from exc

    destination = Path(output_path)
    normalized_backend = request.backend

    _prepare_output_path(destination)
    temporary_output = _build_temporary_output_path(destination)

    try:
        if normalized_backend != "opencv":
            raise CameraCaptureError(
                f"Unsupported camera backend '{normalized_backend}'. Only 'opencv' is available."
            )
        result = _capture_with_opencv(temporary_output, request)

        _validate_output_file(result.output_path)
        _finalize_output_file(result.output_path, destination)
        return _finalize_capture_result(result, destination)
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

def _capture_with_opencv(output_path: Path, request) -> CaptureResult:
    """Capture an image using OpenCV VideoCapture for USB webcams."""
    try:
        import cv2
    except ImportError as exc:
        raise CameraCaptureError(OPENCV_INSTALL_HINT) from exc

    camera = None
    last_valid_frame = None

    try:
        resolved_config = resolve_opencv_config(request)
        requested_width, requested_height = resolved_config.resolved_resolution
        camera, open_backend_label = _open_opencv_camera(
            request.camera_index,
            cv2,
            error_cls=CameraCaptureError,
        )
        _status(
            "Capturing image with OpenCV camera index "
            f"{request.camera_index} at {requested_width}x{requested_height} "
            f"using {open_backend_label}..."
        )

        warnings = list(resolved_config.warnings)
        if open_backend_label != "default":
            warnings.append(f"OpenCV camera opened through the {open_backend_label} backend.")
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, float(requested_width))
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, float(requested_height))
        warnings.extend(_apply_opencv_controls(camera, resolved_config, cv2))
        if request.capture_delay_seconds > 0:
            time.sleep(request.capture_delay_seconds)

        for _ in range(8):
            success, frame = camera.read()
            if success and frame is not None and getattr(frame, "size", 0) > 0:
                last_valid_frame = frame
            time.sleep(0.1)

        if last_valid_frame is None:
            raise CameraCaptureError(
                f"OpenCV opened camera index {request.camera_index}, but no valid frame was captured."
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
            f"OpenCV capture failed for camera index {request.camera_index}. Original error: {exc}"
        ) from exc
    finally:
        if camera is not None:
            camera.release()

    actual_resolution = read_image_resolution(output_path)
    if actual_resolution is None and last_valid_frame is not None:
        actual_resolution = (
            int(last_valid_frame.shape[1]),
            int(last_valid_frame.shape[0]),
        )

    return CaptureResult(
        output_path=output_path,
        backend_used="opencv",
        resolution=actual_resolution,
        warnings=tuple(warnings),
    )


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


def _finalize_capture_result(result: CaptureResult, destination: Path) -> CaptureResult:
    """Return the final metadata after atomic file replacement."""
    resolution = read_image_resolution(destination) or result.resolution
    return CaptureResult(
        output_path=destination,
        backend_used=result.backend_used,
        resolution=resolution,
        warnings=result.warnings,
    )


def _apply_opencv_controls(camera, resolved_config, cv2_module) -> list[str]:
    """Apply best-effort OpenCV camera controls and collect non-fatal warnings."""
    warnings: list[str] = []

    autofocus_prop = getattr(cv2_module, "CAP_PROP_AUTOFOCUS", None)
    if autofocus_prop is None:
        if resolved_config.autofocus_mode != "off":
            warnings.append("OpenCV autofocus control is unavailable in this build.")
    else:
        desired_value = 0.0 if resolved_config.autofocus_mode == "off" else 1.0
        if not camera.set(autofocus_prop, desired_value):
            warnings.append("OpenCV autofocus control was ignored by the camera driver.")

    auto_exposure_prop = getattr(cv2_module, "CAP_PROP_AUTO_EXPOSURE", None)
    exposure_prop = getattr(cv2_module, "CAP_PROP_EXPOSURE", None)
    if resolved_config.exposure == "auto":
        if auto_exposure_prop is not None and not camera.set(auto_exposure_prop, 0.75):
            warnings.append("OpenCV auto exposure control was ignored by the camera driver.")
    else:
        if auto_exposure_prop is not None:
            camera.set(auto_exposure_prop, 0.25)
        if exposure_prop is None:
            warnings.append("OpenCV manual exposure control is unavailable in this build.")
        elif not camera.set(exposure_prop, float(resolved_config.exposure)):
            warnings.append("OpenCV manual exposure control was ignored by the camera driver.")

    brightness_prop = getattr(cv2_module, "CAP_PROP_BRIGHTNESS", None)
    if brightness_prop is None:
        if resolved_config.brightness != 0.0:
            warnings.append("OpenCV brightness control is unavailable in this build.")
    elif not camera.set(brightness_prop, float(resolved_config.brightness)):
        warnings.append("OpenCV brightness control was ignored by the camera driver.")

    return warnings


def _open_opencv_camera(camera_index: int, cv2_module, *, error_cls=CameraCaptureError):
    """Open a camera with Linux-friendly backend fallback and helpful errors."""
    attempt_errors: list[str] = []

    for api_preference, label in _preferred_opencv_api_preferences(cv2_module):
        camera = None
        try:
            if api_preference is None:
                camera = cv2_module.VideoCapture(camera_index)
            else:
                camera = cv2_module.VideoCapture(camera_index, api_preference)
        except Exception as exc:
            attempt_errors.append(f"{label}: {exc}")
            continue

        if camera is not None and camera.isOpened():
            return camera, label

        attempt_errors.append(f"{label}: could not open camera index {camera_index}")
        if camera is not None:
            try:
                camera.release()
            except Exception:
                pass

    attempt_summary = "; ".join(attempt_errors) if attempt_errors else "no backend attempts were available"
    raise error_cls(
        f"OpenCV could not open camera index {camera_index}. "
        "Make sure a USB webcam is connected and not being used by another app. "
        f"Tried backends: {attempt_summary}."
    )


def _preferred_opencv_api_preferences(cv2_module) -> list[tuple[int | None, str]]:
    """Return the ordered OpenCV API preferences for camera access on this platform."""
    candidates: list[tuple[int | None, str]] = []
    if sys.platform.startswith("linux"):
        v4l2_api = getattr(cv2_module, "CAP_V4L2", None)
        if v4l2_api is not None:
            candidates.append((v4l2_api, "V4L2"))
    candidates.append((None, "default"))
    return candidates
