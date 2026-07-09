"""Hardware integration helpers."""

from hardware.button import GPIOButtonError, GPIOButtonTrigger
from hardware.camera_config import (
    CameraConfigError,
    CameraControlRequest,
    CameraControlSupport,
    ResolvedCameraConfig,
    build_camera_request,
    read_image_resolution,
    resolve_opencv_config,
    resolve_picamera2_config,
    select_best_resolution,
)
from hardware.led import LEDIndicator, LEDIndicatorError
from hardware.status import (
    DeviceState,
    build_ready_state_payload,
    build_ui_state_payload,
    clear_latest_result_file,
    coerce_device_state,
    is_busy_device_state,
    screen_for_device_state,
)

__all__ = [
    "DeviceState",
    "GPIOButtonError",
    "GPIOButtonTrigger",
    "LEDIndicator",
    "LEDIndicatorError",
    "CameraConfigError",
    "CameraControlRequest",
    "CameraControlSupport",
    "ResolvedCameraConfig",
    "build_ready_state_payload",
    "build_ui_state_payload",
    "build_camera_request",
    "clear_latest_result_file",
    "coerce_device_state",
    "is_busy_device_state",
    "read_image_resolution",
    "resolve_opencv_config",
    "resolve_picamera2_config",
    "screen_for_device_state",
    "select_best_resolution",
]
