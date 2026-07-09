"""Hardware-aware camera configuration helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from PIL import Image

from config import load_device_settings

VALID_AUTOFOCUS_MODES = ("continuous", "auto", "off")
VALID_CAMERA_BACKENDS = ("auto", "picamera2", "opencv")


class CameraConfigError(Exception):
    """Raised when camera control settings are invalid."""


@dataclass(slots=True)
class CameraControlRequest:
    """Requested camera controls before backend resolution."""

    backend: str
    camera_index: int
    width: int
    height: int
    autofocus_mode: str
    exposure: str | int
    brightness: float
    capture_delay_seconds: float


@dataclass(slots=True)
class CameraControlSupport:
    """Control capability flags for a resolved backend."""

    autofocus: bool
    exposure: bool
    brightness: bool


@dataclass(slots=True)
class ResolvedCameraConfig:
    """Backend-aware capture settings after capability resolution."""

    requested_backend: str
    backend: str
    camera_index: int
    requested_resolution: tuple[int, int]
    resolved_resolution: tuple[int, int]
    autofocus_mode: str
    exposure: str | int
    brightness: float
    capture_delay_seconds: float
    control_support: CameraControlSupport
    warnings: list[str] = field(default_factory=list)


def build_camera_request(
    backend: str | None = None,
    camera_index: int | None = None,
    width: int | None = None,
    height: int | None = None,
    autofocus_mode: str | None = None,
    exposure: str | int | None = None,
    brightness: float | None = None,
    capture_delay_seconds: float | None = None,
) -> CameraControlRequest:
    """Merge explicit values with device defaults."""
    settings = load_device_settings()
    camera = settings.camera
    requested_backend = (backend or camera.backend).strip().lower()
    if requested_backend not in VALID_CAMERA_BACKENDS:
        expected = ", ".join(VALID_CAMERA_BACKENDS)
        raise CameraConfigError(
            f"Unsupported backend '{backend}'. Choose one of: {expected}."
        )

    requested_autofocus = (autofocus_mode or camera.autofocus_mode).strip().lower()
    if requested_autofocus not in VALID_AUTOFOCUS_MODES:
        expected = ", ".join(VALID_AUTOFOCUS_MODES)
        raise CameraConfigError(
            f"Unsupported autofocus mode '{autofocus_mode}'. Choose one of: {expected}."
        )

    resolved_exposure = camera.exposure if exposure is None else exposure
    if isinstance(resolved_exposure, str):
        normalized_exposure = resolved_exposure.strip().lower()
        if normalized_exposure != "auto":
            try:
                resolved_exposure = int(normalized_exposure)
            except ValueError as exc:
                raise CameraConfigError(
                    "Exposure must be 'auto' or a positive integer microsecond value."
                ) from exc
        else:
            resolved_exposure = "auto"

    try:
        resolved_camera_index = camera.index if camera_index is None else int(camera_index)
        resolved_width = camera.resolution.width if width is None else int(width)
        resolved_height = camera.resolution.height if height is None else int(height)
        resolved_brightness = camera.brightness if brightness is None else float(brightness)
        resolved_delay = (
            camera.capture_delay_seconds
            if capture_delay_seconds is None
            else float(capture_delay_seconds)
        )
    except (TypeError, ValueError) as exc:
        raise CameraConfigError("Invalid numeric camera control value.") from exc

    if resolved_camera_index < 0:
        raise CameraConfigError("Camera index must be 0 or greater.")
    if resolved_width <= 0 or resolved_height <= 0:
        raise CameraConfigError("Capture width and height must both be greater than 0.")
    if resolved_delay < 0:
        raise CameraConfigError("Capture delay must be 0 or greater.")

    if resolved_exposure != "auto":
        try:
            resolved_exposure = int(resolved_exposure)
        except (TypeError, ValueError) as exc:
            raise CameraConfigError(
                "Exposure must be 'auto' or a positive integer microsecond value."
            ) from exc
        if resolved_exposure <= 0:
            raise CameraConfigError(
                "Exposure must be 'auto' or a positive integer microsecond value."
            )

    return CameraControlRequest(
        backend=requested_backend,
        camera_index=resolved_camera_index,
        width=resolved_width,
        height=resolved_height,
        autofocus_mode=requested_autofocus,
        exposure=resolved_exposure,
        brightness=resolved_brightness,
        capture_delay_seconds=resolved_delay,
    )


def resolve_picamera2_config(
    request: CameraControlRequest,
    sensor_modes: Sequence[dict[str, Any]] | None = None,
    controls: Iterable[str] | None = None,
) -> ResolvedCameraConfig:
    """Resolve Picamera2 settings against advertised modes and controls."""
    resolved_resolution = select_best_resolution(
        sensor_modes=sensor_modes,
        requested_width=request.width,
        requested_height=request.height,
    )
    available_controls = {str(name) for name in (controls or [])}

    return ResolvedCameraConfig(
        requested_backend=request.backend,
        backend="picamera2",
        camera_index=request.camera_index,
        requested_resolution=(request.width, request.height),
        resolved_resolution=resolved_resolution,
        autofocus_mode=request.autofocus_mode,
        exposure=request.exposure,
        brightness=request.brightness,
        capture_delay_seconds=request.capture_delay_seconds,
        control_support=CameraControlSupport(
            autofocus=_supports_any_control(
                available_controls,
                {"AfMode", "LensPosition"},
                default_if_unknown=True,
            ),
            exposure=_supports_any_control(
                available_controls,
                {"AeEnable", "ExposureTime"},
                default_if_unknown=True,
            ),
            brightness=_supports_any_control(
                available_controls,
                {"Brightness"},
                default_if_unknown=True,
            ),
        ),
    )


def resolve_opencv_config(request: CameraControlRequest) -> ResolvedCameraConfig:
    """Resolve OpenCV settings and document best-effort control support."""
    warnings: list[str] = []
    if request.autofocus_mode != "off":
        warnings.append(
            "OpenCV autofocus support depends on the connected camera driver and may be ignored."
        )
    if request.exposure != "auto":
        warnings.append(
            "OpenCV manual exposure support depends on the connected camera driver and may be ignored."
        )
    if request.brightness != 0.0:
        warnings.append(
            "OpenCV brightness control depends on the connected camera driver and may be ignored."
        )

    return ResolvedCameraConfig(
        requested_backend=request.backend,
        backend="opencv",
        camera_index=request.camera_index,
        requested_resolution=(request.width, request.height),
        resolved_resolution=(request.width, request.height),
        autofocus_mode=request.autofocus_mode,
        exposure=request.exposure,
        brightness=request.brightness,
        capture_delay_seconds=request.capture_delay_seconds,
        control_support=CameraControlSupport(
            autofocus=True,
            exposure=True,
            brightness=True,
        ),
        warnings=warnings,
    )


def select_best_resolution(
    sensor_modes: Sequence[dict[str, Any]] | None,
    requested_width: int,
    requested_height: int,
) -> tuple[int, int]:
    """Choose the closest supported still resolution for a Picamera2 camera."""
    candidates = _extract_mode_sizes(sensor_modes)
    if not candidates:
        return (requested_width, requested_height)

    target_pixels = requested_width * requested_height

    def sort_key(size: tuple[int, int]) -> tuple[int, int, int]:
        width, height = size
        pixels = width * height
        return (
            abs(pixels - target_pixels),
            abs(width - requested_width) + abs(height - requested_height),
            -pixels,
        )

    return sorted(candidates, key=sort_key)[0]


def read_image_resolution(image_path: str | Path) -> tuple[int, int] | None:
    """Read the saved image resolution from disk."""
    path = Path(image_path)
    if not path.is_file():
        return None

    try:
        with Image.open(path) as image:
            return image.size
    except OSError:
        return None


def _extract_mode_sizes(
    sensor_modes: Sequence[dict[str, Any]] | None,
) -> list[tuple[int, int]]:
    """Pull unique WxH sensor mode sizes from Picamera2 metadata."""
    if not sensor_modes:
        return []

    sizes: list[tuple[int, int]] = []
    for mode in sensor_modes:
        if not isinstance(mode, dict):
            continue
        size = mode.get("size")
        if _is_valid_size(size):
            normalized = (int(size[0]), int(size[1]))
            if normalized not in sizes:
                sizes.append(normalized)
            continue

        format_value = mode.get("format")
        if isinstance(format_value, dict):
            maybe_size = format_value.get("size")
            if _is_valid_size(maybe_size):
                normalized = (int(maybe_size[0]), int(maybe_size[1]))
                if normalized not in sizes:
                    sizes.append(normalized)
    return sizes


def _is_valid_size(value: Any) -> bool:
    """Return True when a value looks like a width/height pair."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return False
    try:
        width = int(value[0])
        height = int(value[1])
    except (TypeError, ValueError):
        return False
    return width > 0 and height > 0


def _supports_any_control(
    available_controls: set[str],
    wanted_controls: set[str],
    default_if_unknown: bool,
) -> bool:
    """Return True when controls are available or unknown."""
    if not available_controls:
        return default_if_unknown
    return any(control in available_controls for control in wanted_controls)

