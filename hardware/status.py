"""Shared device-state helpers for hardware and touchscreen flows."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class DeviceState(str, Enum):
    """Lifecycle states shared by the UI, button controller, and LED."""

    READY = "READY"
    CAPTURING = "CAPTURING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    ERROR = "ERROR"


BUSY_DEVICE_STATES = frozenset({DeviceState.CAPTURING, DeviceState.PROCESSING})
DEVICE_SCREEN_MAP = {
    DeviceState.READY: "home",
    DeviceState.CAPTURING: "processing",
    DeviceState.PROCESSING: "processing",
    DeviceState.DONE: "result",
    DeviceState.ERROR: "error",
}
DEVICE_STATUS_MAP = {
    DeviceState.READY: "Ready",
    DeviceState.CAPTURING: "Capturing",
    DeviceState.PROCESSING: "Processing",
    DeviceState.DONE: "Done",
    DeviceState.ERROR: "Error",
}
DEVICE_DETAIL_MAP = {
    DeviceState.CAPTURING: "Capturing image",
    DeviceState.PROCESSING: "Processing",
    DeviceState.DONE: "Answer ready",
    DeviceState.ERROR: "Try again when ready",
}
DEVICE_STEP_MAP = {
    DeviceState.READY: -1,
    DeviceState.CAPTURING: 0,
    DeviceState.PROCESSING: 2,
    DeviceState.DONE: 4,
    DeviceState.ERROR: -1,
}


def coerce_device_state(
    value: DeviceState | str | None,
    default: DeviceState = DeviceState.READY,
) -> DeviceState:
    """Normalize text or enum values into a valid device state."""
    if isinstance(value, DeviceState):
        return value
    if isinstance(value, str):
        normalized = value.strip().upper()
        try:
            return DeviceState(normalized)
        except ValueError:
            return default
    return default


def is_busy_device_state(value: DeviceState | str | None) -> bool:
    """Return True when the device should ignore button input."""
    return coerce_device_state(value) in BUSY_DEVICE_STATES


def screen_for_device_state(value: DeviceState | str | None) -> str:
    """Return the persisted UI screen for a device lifecycle state."""
    state = coerce_device_state(value)
    return DEVICE_SCREEN_MAP[state]


def build_ui_state_payload(
    device_state: DeviceState | str,
    *,
    selected_mode: str,
    ready_detail: str,
    detail: str | None = None,
    answer: str = "",
    error: str = "",
    error_detail: str = "",
    current_step: int | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Build a normalized persisted UI payload for a given device state."""
    state = coerce_device_state(device_state)
    payload = {
        "device_state": state.value,
        "screen": screen_for_device_state(state),
        "selected_mode": selected_mode,
        "status": status or DEVICE_STATUS_MAP[state],
        "detail": detail if detail is not None else _default_detail_for_state(state, ready_detail),
        "answer": "",
        "error": "",
        "error_detail": "",
        "current_step": DEVICE_STEP_MAP[state] if current_step is None else current_step,
    }

    if state == DeviceState.DONE:
        payload["answer"] = answer
    elif state == DeviceState.ERROR:
        payload["error"] = error
        payload["error_detail"] = error_detail

    return payload


def build_ready_state_payload(
    *,
    selected_mode: str,
    ready_detail: str,
) -> dict[str, Any]:
    """Return the canonical READY payload."""
    return build_ui_state_payload(
        DeviceState.READY,
        selected_mode=selected_mode,
        ready_detail=ready_detail,
    )


def clear_latest_result_file(
    output_path: str | Path,
    mode: str | None = None,
) -> Path:
    """Overwrite the saved result file with a readable cleared placeholder."""
    result_path = Path(output_path)
    result_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"Timestamp: {timestamp}",
        f"Mode: {mode or 'n/a'}",
        "Status: cleared",
        "Message: No result available",
    ]
    result_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result_path


def _default_detail_for_state(state: DeviceState, ready_detail: str) -> str:
    """Return the default human-readable detail text for a device state."""
    if state == DeviceState.READY:
        return ready_detail
    return DEVICE_DETAIL_MAP[state]
