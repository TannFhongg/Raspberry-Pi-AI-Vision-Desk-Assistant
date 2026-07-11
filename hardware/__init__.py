"""Hardware integration helpers with lazy exports to avoid import cycles."""

from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "DeviceState": ("hardware.status", "DeviceState"),
    "GPIOButtonError": ("hardware.button", "GPIOButtonError"),
    "GPIOButtonTrigger": ("hardware.button", "GPIOButtonTrigger"),
    "LEDIndicator": ("hardware.led", "LEDIndicator"),
    "LEDIndicatorError": ("hardware.led", "LEDIndicatorError"),
    "CameraConfigError": ("hardware.camera_config", "CameraConfigError"),
    "CameraControlRequest": ("hardware.camera_config", "CameraControlRequest"),
    "CameraControlSupport": ("hardware.camera_config", "CameraControlSupport"),
    "ResolvedCameraConfig": ("hardware.camera_config", "ResolvedCameraConfig"),
    "build_ready_state_payload": ("hardware.status", "build_ready_state_payload"),
    "build_ui_state_payload": ("hardware.status", "build_ui_state_payload"),
    "build_camera_request": ("hardware.camera_config", "build_camera_request"),
    "clear_latest_result_file": ("hardware.status", "clear_latest_result_file"),
    "coerce_device_state": ("hardware.status", "coerce_device_state"),
    "is_busy_device_state": ("hardware.status", "is_busy_device_state"),
    "read_image_resolution": ("hardware.camera_config", "read_image_resolution"),
    "resolve_opencv_config": ("hardware.camera_config", "resolve_opencv_config"),
    "screen_for_device_state": ("hardware.status", "screen_for_device_state"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    """Resolve hardware package exports lazily to avoid circular imports."""
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module 'hardware' has no attribute {name!r}") from exc

    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value
