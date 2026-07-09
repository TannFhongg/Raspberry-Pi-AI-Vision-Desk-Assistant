"""Camera capture backends for Raspberry Pi CSI cameras and USB webcams."""

from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from hardware.camera_config import (
    CameraConfigError,
    build_camera_request,
    read_image_resolution,
    resolve_opencv_config,
    resolve_picamera2_config,
)

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
    resolution: tuple[int, int] | None = None
    warnings: tuple[str, ...] = ()


def capture_image(
    output_path: str = "static/captured.jpg",
    backend: str | None = None,
    camera_index: int | None = None,
    width: int | None = None,
    height: int | None = None,
    autofocus_mode: str | None = None,
    exposure: str | int | None = None,
    brightness: float | None = None,
    capture_delay_seconds: float | None = None,
) -> CaptureResult:
    """Capture an image using Picamera2 or OpenCV and save it to disk."""
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

    if normalized_backend == "auto":
        picamera_error_message = ""
        _prepare_output_path(destination)
        try:
            _status("Trying Picamera2 backend first...")
            temporary_output = _build_temporary_output_path(destination)
            result = _capture_with_picamera2(temporary_output, request)
            _validate_output_file(result.output_path)
            _finalize_output_file(result.output_path, destination)
            return _finalize_capture_result(result, destination)
        except CameraCaptureError as picamera_error:
            picamera_error_message = str(picamera_error)
            _status(f"Picamera2 failed: {picamera_error}")
            _status("Falling back to OpenCV backend...")
            _cleanup_temporary_file(locals().get("temporary_output"))

        _prepare_output_path(destination)
        try:
            temporary_output = _build_temporary_output_path(destination)
            result = _capture_with_opencv(temporary_output, request)
            _validate_output_file(result.output_path)
            _finalize_output_file(result.output_path, destination)
            return _finalize_capture_result(result, destination)
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
            result = _capture_with_picamera2(temporary_output, request)
        else:
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


def _capture_with_picamera2(output_path: Path, request) -> CaptureResult:
    """Capture a still image using the Raspberry Pi Picamera2 stack."""
    try:
        from picamera2 import Picamera2
    except ImportError as exc:
        raise CameraCaptureError(PICAMERA2_INSTALL_HINT) from exc

    picam2 = None
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
        resolved_width, resolved_height = resolved_config.resolved_resolution
        _status(
            f"Capturing image with Picamera2 at {resolved_width}x{resolved_height}..."
        )
        configuration = picam2.create_still_configuration(
            main={"size": (resolved_width, resolved_height)},
            buffer_count=2,
        )
        picam2.configure(configuration)
        picam2.start()
        warnings = list(resolved_config.warnings)
        warnings.extend(_apply_picamera2_controls(picam2, resolved_config))
        if request.capture_delay_seconds > 0:
            time.sleep(request.capture_delay_seconds)
        if resolved_config.autofocus_mode == "auto":
            warnings.extend(_run_picamera2_autofocus_cycle(picam2))
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

    return CaptureResult(
        output_path=output_path,
        backend_used="picamera2",
        resolution=read_image_resolution(output_path) or resolved_config.resolved_resolution,
        warnings=tuple(warnings),
    )


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
        _status(
            f"Capturing image with OpenCV camera index {request.camera_index} at {requested_width}x{requested_height}..."
        )
        camera = cv2.VideoCapture(request.camera_index)
        if not camera.isOpened():
            raise CameraCaptureError(
                f"OpenCV could not open camera index {request.camera_index}. "
                "Make sure a USB webcam is connected and not being used by another app."
            )

        warnings = list(resolved_config.warnings)
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


def _apply_picamera2_controls(picam2, resolved_config) -> list[str]:
    """Apply supported Picamera2 controls without failing capture on partial support."""
    warnings: list[str] = []
    try:
        from libcamera import controls
    except ImportError:
        controls = None

    autofocus_controls = {
        "continuous": getattr(getattr(controls, "AfModeEnum", None), "Continuous", None),
        "auto": getattr(getattr(controls, "AfModeEnum", None), "Auto", None),
        "off": getattr(getattr(controls, "AfModeEnum", None), "Manual", None),
    }

    control_payload: dict[str, object] = {}
    if resolved_config.control_support.autofocus and controls is not None:
        autofocus_value = autofocus_controls.get(resolved_config.autofocus_mode)
        if autofocus_value is not None:
            control_payload["AfMode"] = autofocus_value
    elif resolved_config.autofocus_mode != "off":
        warnings.append("Autofocus controls are not available for this Picamera2 camera.")

    if resolved_config.control_support.exposure:
        if resolved_config.exposure == "auto":
            control_payload["AeEnable"] = True
        else:
            control_payload["AeEnable"] = False
            control_payload["ExposureTime"] = int(resolved_config.exposure)
    elif resolved_config.exposure != "auto":
        warnings.append("Manual exposure is not available for this Picamera2 camera.")

    if resolved_config.control_support.brightness:
        control_payload["Brightness"] = float(resolved_config.brightness)
    elif resolved_config.brightness != 0.0:
        warnings.append("Brightness control is not available for this Picamera2 camera.")

    if control_payload:
        try:
            picam2.set_controls(control_payload)
        except Exception as exc:
            warnings.append(f"Some camera controls could not be applied: {exc}")
    return warnings


def _run_picamera2_autofocus_cycle(picam2) -> list[str]:
    """Run a one-shot autofocus cycle when supported."""
    if not hasattr(picam2, "autofocus_cycle"):
        return ["Picamera2 autofocus cycle is not available in this environment."]

    try:
        picam2.autofocus_cycle(wait=True)
    except TypeError:
        try:
            picam2.autofocus_cycle()
        except Exception as exc:
            return [f"Picamera2 autofocus cycle failed: {exc}"]
        time.sleep(0.5)
    except Exception as exc:
        return [f"Picamera2 autofocus cycle failed: {exc}"]
    return []


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
