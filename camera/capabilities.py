"""Camera capability detection without assuming OpenCV controls are supported."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
import subprocess
from typing import Any


@dataclass(frozen=True, slots=True)
class CameraCapabilities:
    """Normalized, verified controls available to the active camera backend."""

    available: bool
    autofocus: bool = False
    autofocus_lock: bool = False
    manual_focus: bool = False
    auto_exposure: bool = False
    exposure_compensation: bool = False
    manual_exposure: bool = False
    source: str = "unavailable"
    message: str = "Camera capability detection has not completed."

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_camera_capabilities(settings, *, mock_hardware: bool = False) -> CameraCapabilities:
    """Probe V4L2 controls read-only; unknown controls remain disabled.

    `v4l2-ctl --list-ctrls-menus` describes capabilities without changing focus
    or exposure.  If it is unavailable, controls are deliberately disabled
    rather than guessed from the camera configuration.
    """
    if mock_hardware:
        return CameraCapabilities(
            available=True,
            autofocus=True,
            autofocus_lock=False,
            manual_focus=False,
            auto_exposure=True,
            exposure_compensation=False,
            manual_exposure=False,
            source="mock",
            message="Mock camera capabilities are simulated for UI testing.",
        )
    if str(getattr(settings.camera, "backend", "")).lower() != "opencv":
        return CameraCapabilities(available=False, message="This camera backend does not expose capability details.")
    device_path = f"/dev/video{int(getattr(settings.camera, 'index', 0))}"
    try:
        result = subprocess.run(
            ["v4l2-ctl", "--device", device_path, "--list-ctrls-menus"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return CameraCapabilities(available=False, message="Camera controls could not be verified on this device.")
    if result.returncode != 0:
        return CameraCapabilities(available=False, message="Camera controls could not be verified on this device.")
    controls = result.stdout.lower()
    if not controls.strip():
        return CameraCapabilities(available=True, source="v4l2", message="The camera is available; adjustable controls were not reported.")
    has = lambda *names: any(re.search(rf"\b{re.escape(name)}\b", controls) for name in names)
    autofocus = has("focus_auto", "auto_focus_start", "focus_automatic_continuous")
    manual_focus = has("focus_absolute")
    auto_exposure = has("exposure_auto")
    manual_exposure = has("exposure_absolute")
    return CameraCapabilities(
        available=True,
        autofocus=autofocus,
        autofocus_lock=autofocus and has("focus_auto", "focus_automatic_continuous"),
        manual_focus=manual_focus,
        auto_exposure=auto_exposure,
        exposure_compensation=has("exposure_bias", "auto_exposure_bias"),
        manual_exposure=manual_exposure,
        source="v4l2",
        message="Camera controls were read from the active V4L2 device.",
    )
