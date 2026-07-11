"""Hardware diagnostics for the Raspberry Pi AI Vision Desk Assistant."""

from __future__ import annotations

import os
import socket
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from camera import CameraCaptureError, capture_image
from config import DeviceSettings, load_device_settings

DEFAULT_SOCKET_TIMEOUT_SECONDS = 5.0
DEFAULT_INTERNET_HOST = ("1.1.1.1", 53)
DEFAULT_CAMERA_PROBE_MAX_WIDTH = 1280
DEFAULT_CAMERA_PROBE_MAX_HEIGHT = 720


@dataclass(slots=True)
class HardwareCheckResult:
    """Result for a single hardware or connectivity check."""

    name: str
    status: str
    message: str
    required: bool = True

    @property
    def passed(self) -> bool:
        """Return True when the check passed."""
        return self.status == "pass"

    @property
    def failed(self) -> bool:
        """Return True when a required check failed."""
        return self.status == "fail" and self.required


@dataclass(slots=True)
class HardwareCheckReport:
    """Full diagnostic report for the standalone device."""

    results: list[HardwareCheckResult]

    @property
    def all_required_passed(self) -> bool:
        """Return True when every required check passed."""
        return all(not result.failed for result in self.results)


def run_device_checks(
    settings: DeviceSettings | None = None,
    status_callback: Callable[[HardwareCheckResult], None] | None = None,
) -> HardwareCheckReport:
    """Run all required device checks and return a full report."""
    resolved_settings = settings or load_device_settings()
    results = [
        check_camera(resolved_settings),
        check_display(resolved_settings),
        check_internet_connection(),
        check_openai_reachable(),
        check_gpio_available(),
    ]

    if status_callback is not None:
        for result in results:
            status_callback(result)

    return HardwareCheckReport(results=results)


def check_camera(settings: DeviceSettings) -> HardwareCheckResult:
    """Verify that the configured camera backend can capture a still image."""
    probe_width, probe_height = _build_camera_probe_resolution(settings)
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".jpg",
            prefix="vision-device-check-",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)

        result = capture_image(
            output_path=str(temp_path),
            backend=settings.camera.backend,
            camera_index=settings.camera.index,
            width=probe_width,
            height=probe_height,
            autofocus_mode=settings.camera.autofocus_mode,
            exposure=settings.camera.exposure,
            brightness=settings.camera.brightness,
            capture_delay_seconds=0.0,
        )
    except CameraCaptureError as exc:
        return HardwareCheckResult(
            name="camera",
            status="fail",
            message=str(exc),
        )
    finally:
        if "temp_path" in locals():
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

    resolution_text = "unknown"
    if result.resolution is not None:
        resolution_text = f"{result.resolution[0]}x{result.resolution[1]}"

    message = f"Camera capture succeeded via {result.backend_used} at {resolution_text}."
    if result.warnings:
        message = f"{message} Warnings: {'; '.join(result.warnings)}"

    return HardwareCheckResult(
        name="camera",
        status="pass",
        message=message,
    )


def _build_camera_probe_resolution(settings: DeviceSettings) -> tuple[int, int]:
    """Use a lightweight probe resolution so health checks do not stress the camera path."""
    width = max(1, int(settings.camera.resolution.width))
    height = max(1, int(settings.camera.resolution.height))
    scale = min(
        1.0,
        DEFAULT_CAMERA_PROBE_MAX_WIDTH / float(width),
        DEFAULT_CAMERA_PROBE_MAX_HEIGHT / float(height),
    )
    probe_width = max(1, int(round(width * scale)))
    probe_height = max(1, int(round(height * scale)))
    return (probe_width, probe_height)


def check_display(settings: DeviceSettings) -> HardwareCheckResult:
    """Verify that a connected display is available when kiosk mode is required."""
    status_files = sorted(Path("/sys/class/drm").glob("card*-*/status"))
    connected = []
    disconnected = []
    for status_file in status_files:
        try:
            state = status_file.read_text(encoding="utf-8").strip().lower()
        except OSError:
            continue
        connector_name = status_file.parent.name
        if state == "connected":
            connected.append(connector_name)
        else:
            disconnected.append(connector_name)

    if connected:
        return HardwareCheckResult(
            name="display",
            status="pass",
            message=f"Connected display(s): {', '.join(connected)}.",
        )

    if settings.startup.behavior == "kiosk":
        if not status_files:
            return HardwareCheckResult(
                name="display",
                status="fail",
                message="No DRM display status files were found for kiosk mode.",
            )
        known_connectors = ", ".join(disconnected) or "none"
        return HardwareCheckResult(
            name="display",
            status="fail",
            message=f"No connected display detected for kiosk mode. Checked: {known_connectors}.",
        )

    return HardwareCheckResult(
        name="display",
        status="skip",
        message="Display check skipped because startup behavior is not kiosk.",
        required=False,
    )


def check_internet_connection(
    host: tuple[str, int] = DEFAULT_INTERNET_HOST,
    timeout_seconds: float = DEFAULT_SOCKET_TIMEOUT_SECONDS,
) -> HardwareCheckResult:
    """Verify general internet connectivity with a short TCP probe."""
    try:
        with socket.create_connection(host, timeout=timeout_seconds):
            pass
    except OSError as exc:
        return HardwareCheckResult(
            name="internet",
            status="fail",
            message=f"Internet connection check failed: {exc}",
        )

    return HardwareCheckResult(
        name="internet",
        status="pass",
        message=f"Internet connection check succeeded via {host[0]}:{host[1]}.",
    )


def check_openai_reachable() -> HardwareCheckResult:
    """Verify API key presence and that the OpenAI API can be reached."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return HardwareCheckResult(
            name="openai",
            status="fail",
            message="Missing OPENAI_API_KEY.",
        )

    model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini").strip() or "gpt-5.4-mini"

    try:
        import openai
        from openai import OpenAI
    except ImportError as exc:
        return HardwareCheckResult(
            name="openai",
            status="fail",
            message=f"OpenAI SDK is not installed. {exc}",
        )

    try:
        client = OpenAI(api_key=api_key)
        try:
            client.responses.create(
                model=model,
                input="Reply with OK.",
                max_output_tokens=8,
                text={"verbosity": "low"},
            )
        except TypeError:
            client.responses.create(
                model=model,
                input="Reply with OK.",
                text={"verbosity": "low"},
            )
    except openai.AuthenticationError:
        return HardwareCheckResult(
            name="openai",
            status="fail",
            message="OpenAI authentication failed. Check OPENAI_API_KEY.",
        )
    except openai.PermissionDeniedError:
        return HardwareCheckResult(
            name="openai",
            status="fail",
            message=f"OpenAI access denied for model '{model}'.",
        )
    except openai.NotFoundError:
        return HardwareCheckResult(
            name="openai",
            status="fail",
            message=f"OpenAI model '{model}' was not found.",
        )
    except openai.RateLimitError:
        return HardwareCheckResult(
            name="openai",
            status="fail",
            message="OpenAI rate limit or quota reached.",
        )
    except openai.APIConnectionError as exc:
        return HardwareCheckResult(
            name="openai",
            status="fail",
            message=f"Could not connect to OpenAI. {exc}",
        )
    except openai.APITimeoutError:
        return HardwareCheckResult(
            name="openai",
            status="fail",
            message="OpenAI request timed out.",
        )
    except openai.APIStatusError as exc:
        return HardwareCheckResult(
            name="openai",
            status="fail",
            message=f"OpenAI API error with status {exc.status_code}.",
        )
    except openai.OpenAIError as exc:
        return HardwareCheckResult(
            name="openai",
            status="fail",
            message=f"OpenAI SDK error: {exc}",
        )

    return HardwareCheckResult(
        name="openai",
        status="pass",
        message=f"OpenAI API reachable with model '{model}'.",
    )


def check_gpio_available() -> HardwareCheckResult:
    """Verify that gpiozero has access to a real pin factory."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from gpiozero import Device
    except ImportError as exc:
        return HardwareCheckResult(
            name="gpio",
            status="fail",
            message=f"gpiozero is not installed. {exc}",
        )
    except Exception as exc:
        return HardwareCheckResult(
            name="gpio",
            status="fail",
            message=f"GPIO import failed. {exc}",
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            Device.ensure_pin_factory()
            pin_factory = Device.pin_factory
    except Exception as exc:
        return HardwareCheckResult(
            name="gpio",
            status="fail",
            message=f"GPIO is not available on this system. {exc}",
        )

    factory_name = pin_factory.__class__.__name__
    factory_module = pin_factory.__class__.__module__.lower()
    if "mock" in factory_module or "mock" in factory_name.lower():
        return HardwareCheckResult(
            name="gpio",
            status="fail",
            message=f"GPIO is using a mock pin factory ({factory_name}).",
        )

    return HardwareCheckResult(
        name="gpio",
        status="pass",
        message=f"GPIO pin factory available: {factory_name}.",
    )
