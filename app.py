"""Touchscreen-first Flask UI for the Raspberry Pi AI Vision Desk Assistant."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, render_template, request, url_for
from markupsafe import Markup, escape

from ai.modes import get_mode, normalize_mode
from camera import CameraCaptureError
from camera.live_preview import LivePreviewService
from config import SettingsError, load_device_settings, update_device_config
from hardware import (
    DeviceState,
    GPIOButtonError,
    GPIOButtonTrigger,
    LEDIndicator,
    build_ui_state_payload,
    clear_latest_result_file,
    coerce_device_state,
    is_busy_device_state,
    screen_for_device_state,
)
from hardware.device_check import HardwareCheckResult, check_camera, check_openai_reachable
from hardware.setup_gpio import GPIOSetupVerifier, GPIOSetupVerifierError
from pipeline import (
    PipelineError,
    PipelineResult,
    build_capture_session_paths,
    run_analyze,
    run_capture_analyze,
    save_latest_result,
)
from system import (
    HealthMonitor,
    OfflineRetryEntry,
    OfflineRetryQueue,
    OfflineRetryQueueError,
    OfflineRetryQueueFullError,
    atomic_write_json,
    configure_logging,
    quarantine_file,
    safe_rmtree,
    safe_unlink,
)
from system.device_setup import (
    DeviceSetupError,
    connect_wifi_network,
    has_configured_openai_key,
    scan_wifi_networks,
    upsert_env_value,
)

load_dotenv()

try:
    SETTINGS = load_device_settings()
except SettingsError as exc:
    raise RuntimeError(f"Invalid device settings: {exc}") from exc

configure_logging(settings=SETTINGS)
LOGGER = logging.getLogger(__name__)
LOGGER.info("Flask app startup begin")

app = Flask(__name__)
app.logger.handlers.clear()
app.logger.propagate = True
app.logger.setLevel(logging.getLogger().level)

UI_STATE_PATH = Path("data/ui_state.json")
SETUP_STATE_PATH = Path("data/setup_state.json")
HEALTH_STATUS_PATH = Path("data/health_status.json")
LATEST_RESULT_PATH = Path("data/latest_result.txt")
RESULT_HISTORY_PATH = Path("data/result_history.json")
RESULT_HISTORY_ASSET_DIR = Path("data/result_history_assets")
PRIVATE_DATA_PATH = Path("data/private")
PRIVATE_CURRENT_PATH = PRIVATE_DATA_PATH / "current"
PRIVATE_RETRY_PATH = PRIVATE_DATA_PATH / "retry"
PRIVATE_QUARANTINE_PATH = PRIVATE_DATA_PATH / "quarantine"
ENV_FILE_PATH = Path(".env")
CAPTURED_IMAGE_PATH = PRIVATE_CURRENT_PATH / "captured.jpg"
PROCESSED_IMAGE_PATH = PRIVATE_CURRENT_PATH / "processed.jpg"
OFFLINE_RETRY_QUEUE_PATH = PRIVATE_DATA_PATH / "retry_queue.json"
OFFLINE_RETRY_STORAGE_PATH = PRIVATE_RETRY_PATH
VALID_SCREENS = {"home", "processing", "result", "error", "history", "history_detail", "setup"}
MJPEG_BOUNDARY = "frame"
SETUP_STEPS = ("wifi", "openai", "camera", "gpio", "finish")
SETUP_GPIO_LABELS = {
    "capture": "Capture Button",
    "mode_read_text": "Read Text Button",
    "mode_summarize_document": "Summarize Document Button",
    "mode_analyze_image": "Analyze Image Button",
    "mode_professional_assistant": "Professional Assistant Button",
    "mode_solve_problem": "Solve Problem Button",
    "back": "Back Button",
}
SETUP_RESTART_DELAY_SECONDS = 0.75
UI_MODE_OPTIONS = (
    {
        "id": "read_text",
        "name": "Read Text",
        "description": "Read the visible text clearly and quickly.",
        "internal_mode": "document_reader",
    },
    {
        "id": "summarize_document",
        "name": "Summarize Document",
        "description": "Summarize documents, notes, and text-heavy pages.",
        "internal_mode": "document_reader",
    },
    {
        "id": "analyze_image",
        "name": "Analyze Image",
        "description": "Describe what the camera sees and explain the important parts.",
        "internal_mode": "general_vision",
    },
    {
        "id": "professional_assistant",
        "name": "Professional Assistant",
        "description": "Give quick professional help for work, meetings, and presentations.",
        "internal_mode": "general_vision",
    },
    {
        "id": "solve_problem",
        "name": "Solve Problem",
        "description": "Solve visible questions, tasks, calculations, and problems.",
        "internal_mode": "math_solver",
    },
)
UI_MODE_BY_ID = {mode["id"]: mode for mode in UI_MODE_OPTIONS}
MODE_LABELS = {mode["id"]: mode["name"] for mode in UI_MODE_OPTIONS}
UI_MODE_TO_INTERNAL_MODE = {
    mode["id"]: mode["internal_mode"] for mode in UI_MODE_OPTIONS
}
INTERNAL_TO_UI_MODE = {
    "document_reader": "read_text",
    "math_solver": "solve_problem",
    "engineering_mode": "analyze_image",
    "general_vision": "analyze_image",
}
PROGRESS_STEPS = [
    "Capturing...",
    "Processing...",
    "Thinking...",
]

STATE_LOCK = threading.Lock()
SETUP_STATE_LOCK = threading.Lock()
RESULT_HISTORY_LOCK = threading.Lock()
RESULT_HISTORY_THUMBNAIL_LOCK = threading.Lock()
RUN_LOCK = threading.Lock()
GPIO_START_LOCK = threading.Lock()
SETUP_GPIO_LOCK = threading.Lock()
RUNNING = False
GPIO_START_ATTEMPTED = False
GPIO_TRIGGER: GPIOButtonTrigger | None = None
SETUP_GPIO_VERIFIER: GPIOSetupVerifier | None = None
HEALTH_MONITOR: HealthMonitor | None = None
RESULT_HISTORY_CACHE: list[dict[str, Any]] | None = None
RESULT_HISTORY_THUMBNAIL_CACHE: dict[str, str] = {}
OFFLINE_RETRY_QUEUE: OfflineRetryQueue | None = None


def _current_config_path() -> Path:
    """Return the active device config path."""
    return SETTINGS.config_path


def _setup_is_complete() -> bool:
    """Return True when the first-boot flow has been completed."""
    return bool(getattr(SETTINGS.setup, "completed", False))


def _coerce_setup_step(value: Any) -> str:
    """Normalize a persisted wizard step value."""
    normalized = str(value or "").strip().lower()
    if normalized in SETUP_STEPS:
        return normalized
    return SETUP_STEPS[0]


def _default_setup_state() -> dict[str, Any]:
    """Return the default persisted setup-wizard state."""
    required_buttons = _build_setup_gpio_requirements()
    return {
        "current_step": SETUP_STEPS[0],
        "warnings_acknowledged": False,
        "finish_message": "",
        "updated_at": _timestamp(),
        "wifi": {
            "scan_status": "idle",
            "connect_status": "idle",
            "available_networks": [],
            "ssid": SETTINGS.network.wifi.ssid,
            "connection_name": SETTINGS.network.wifi.connection_name,
            "message": "",
            "auto_connect": SETTINGS.network.wifi.auto_connect,
            "managed_by": SETTINGS.network.wifi.managed_by,
        },
        "openai": {
            "status": "idle",
            "key_present": has_configured_openai_key(os.getenv("OPENAI_API_KEY")),
            "message": "",
        },
        "camera": {
            "status": "idle",
            "message": "",
        },
        "gpio": {
            "status": "idle",
            "message": "",
            "active": False,
            "required": required_buttons,
            "pressed_labels": [],
            "all_pressed": False,
        },
    }


def _coerce_setup_state(raw_state: Any) -> dict[str, Any]:
    """Normalize any persisted setup state into the supported schema."""
    default_state = _default_setup_state()
    if not isinstance(raw_state, dict):
        return default_state

    wifi = raw_state.get("wifi", {})
    gpio = raw_state.get("gpio", {})
    normalized_state = {
        "current_step": _coerce_setup_step(raw_state.get("current_step")),
        "warnings_acknowledged": bool(raw_state.get("warnings_acknowledged", False)),
        "finish_message": str(raw_state.get("finish_message", "")),
        "updated_at": str(raw_state.get("updated_at", default_state["updated_at"])),
        "wifi": {
            "scan_status": str(wifi.get("scan_status", default_state["wifi"]["scan_status"])),
            "connect_status": str(wifi.get("connect_status", default_state["wifi"]["connect_status"])),
            "available_networks": _coerce_setup_networks(wifi.get("available_networks", [])),
            "ssid": str(wifi.get("ssid", default_state["wifi"]["ssid"])).strip(),
            "connection_name": str(
                wifi.get("connection_name", default_state["wifi"]["connection_name"])
            ).strip(),
            "message": str(wifi.get("message", "")),
            "auto_connect": bool(wifi.get("auto_connect", default_state["wifi"]["auto_connect"])),
            "managed_by": str(wifi.get("managed_by", default_state["wifi"]["managed_by"])) or "nmcli",
        },
        "openai": {
            "status": str(raw_state.get("openai", {}).get("status", default_state["openai"]["status"])),
            "key_present": bool(raw_state.get("openai", {}).get("key_present", default_state["openai"]["key_present"])),
            "message": str(raw_state.get("openai", {}).get("message", "")),
        },
        "camera": {
            "status": str(raw_state.get("camera", {}).get("status", default_state["camera"]["status"])),
            "message": str(raw_state.get("camera", {}).get("message", "")),
        },
        "gpio": {
            "status": str(gpio.get("status", default_state["gpio"]["status"])),
            "message": str(gpio.get("message", "")),
            "active": bool(gpio.get("active", False)),
            "required": _coerce_setup_required_buttons(gpio.get("required", default_state["gpio"]["required"])),
            "pressed_labels": sorted({
                str(label).strip()
                for label in gpio.get("pressed_labels", [])
                if str(label).strip()
            }),
            "all_pressed": bool(gpio.get("all_pressed", False)),
        },
    }
    normalized_state["gpio"]["all_pressed"] = _setup_gpio_complete(normalized_state)
    return normalized_state


def _coerce_setup_networks(value: Any) -> list[dict[str, Any]]:
    """Return a normalized Wi-Fi scan result list."""
    if not isinstance(value, list):
        return []
    networks: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        ssid = str(item.get("ssid", "")).strip()
        if not ssid:
            continue
        try:
            signal = int(item.get("signal", 0))
        except (TypeError, ValueError):
            signal = 0
        security = str(item.get("security", "open")).strip() or "open"
        networks.append({"ssid": ssid, "signal": signal, "security": security})
    return networks


def _coerce_setup_required_buttons(value: Any) -> list[dict[str, Any]]:
    """Return a normalized GPIO setup requirements list."""
    if not isinstance(value, list):
        return _build_setup_gpio_requirements()
    required: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        if not label:
            continue
        try:
            pin = int(item.get("pin"))
        except (TypeError, ValueError):
            continue
        required.append(
            {
                "label": label,
                "pin": pin,
                "pressed": bool(item.get("pressed", False)),
            }
        )
    return required or _build_setup_gpio_requirements()


def _load_setup_state() -> dict[str, Any]:
    """Read the persisted setup-wizard state file."""
    default_state = _default_setup_state()
    with SETUP_STATE_LOCK:
        if not SETUP_STATE_PATH.is_file():
            return default_state
        try:
            raw_state = json.loads(SETUP_STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            quarantine_file(
                SETUP_STATE_PATH,
                quarantine_dir=PRIVATE_QUARANTINE_PATH,
                reason="invalid-setup-state",
            )
            return default_state
    return _coerce_setup_state(raw_state)


def _write_setup_state(updates: dict[str, Any] | None = None) -> dict[str, Any]:
    """Persist merged setup-wizard state to disk."""
    next_state = _load_setup_state()
    if updates:
        _merge_nested_state(next_state, updates)
    next_state["current_step"] = _coerce_setup_step(next_state.get("current_step"))
    next_state["updated_at"] = _timestamp()
    next_state = _coerce_setup_state(next_state)
    SETUP_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SETUP_STATE_LOCK:
        atomic_write_json(
            SETUP_STATE_PATH,
            next_state,
            ensure_ascii=False,
            indent=2,
        )
    return next_state


def _clear_setup_state() -> None:
    """Delete the persisted setup state and stop any temporary GPIO verifier."""
    _stop_setup_gpio_verifier(restart_main_listener=False)
    safe_unlink(SETUP_STATE_PATH)


def _merge_nested_state(target: dict[str, Any], updates: dict[str, Any]) -> None:
    """Recursively merge nested state dictionaries in-place."""
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_nested_state(target[key], value)
        else:
            target[key] = value


def _build_setup_gpio_requirements() -> list[dict[str, Any]]:
    """Return the button labels and pins that the setup GPIO verifier must track."""
    required: list[dict[str, Any]] = [
        {"label": "capture", "pin": CAPTURE_BUTTON_PIN, "pressed": False},
    ]
    mode_button_pairs = [
        ("mode_read_text", MODE_BUTTON_1_PIN),
        ("mode_summarize_document", MODE_BUTTON_2_PIN),
        ("mode_analyze_image", MODE_BUTTON_3_PIN),
        ("mode_professional_assistant", MODE_BUTTON_4_PIN),
        ("mode_solve_problem", MODE_BUTTON_5_PIN),
    ]
    for label, pin in mode_button_pairs:
        if pin is None:
            continue
        required.append({"label": label, "pin": pin, "pressed": False})
    if BACK_BUTTON_PIN is not None:
        required.append({"label": "back", "pin": BACK_BUTTON_PIN, "pressed": False})
    return required


def _build_setup_required_pin_map() -> dict[str, int]:
    """Return the setup verifier pin map keyed by logical button labels."""
    return {
        button["label"]: int(button["pin"])
        for button in _build_setup_gpio_requirements()
    }


def _setup_gpio_complete(state: dict[str, Any]) -> bool:
    """Return True when every required GPIO setup button has been pressed once."""
    gpio = state.get("gpio", {})
    required = gpio.get("required", [])
    pressed_labels = {
        str(label).strip()
        for label in gpio.get("pressed_labels", [])
        if str(label).strip()
    }
    required_labels = {
        str(item.get("label", "")).strip()
        for item in required
        if isinstance(item, dict) and str(item.get("label", "")).strip()
    }
    return bool(required_labels) and required_labels.issubset(pressed_labels)


def _build_setup_warnings(state: dict[str, Any] | None = None) -> list[str]:
    """Return the unresolved warnings shown on the finish step."""
    current_state = _load_setup_state() if state is None else state
    warnings: list[str] = []
    wifi = current_state["wifi"]
    openai = current_state["openai"]
    camera = current_state["camera"]
    gpio = current_state["gpio"]

    if wifi.get("connect_status") != "pass":
        warnings.append("Wi-Fi setup has not completed successfully.")
    if openai.get("status") != "pass":
        warnings.append("OpenAI API key has not been verified successfully.")
    if camera.get("status") != "pass":
        warnings.append("Camera test has not completed successfully.")
    if not _setup_gpio_complete(current_state):
        warnings.append("GPIO button test has not completed successfully.")
    return warnings


def _stop_setup_gpio_verifier(*, restart_main_listener: bool) -> None:
    """Stop the temporary setup GPIO verifier and optionally restore the main listener."""
    global SETUP_GPIO_VERIFIER

    with SETUP_GPIO_LOCK:
        verifier = SETUP_GPIO_VERIFIER
        SETUP_GPIO_VERIFIER = None
    if verifier is not None:
        verifier.close()
    if restart_main_listener and _setup_is_complete():
        _ensure_gpio_button_listener_started()


def _snapshot_setup_gpio_progress() -> dict[str, Any]:
    """Return the latest GPIO verifier snapshot, or a default requirement set."""
    with SETUP_GPIO_LOCK:
        verifier = SETUP_GPIO_VERIFIER
    if verifier is None:
        base_required = _build_setup_gpio_requirements()
        return {
            "required": base_required,
            "pressed_labels": [],
            "all_pressed": False,
            "active": False,
            "message": "GPIO setup test is not running.",
        }
    snapshot = verifier.snapshot()
    snapshot["active"] = True
    snapshot["message"] = (
        "All configured GPIO setup buttons were pressed successfully."
        if snapshot["all_pressed"]
        else "Press each configured GPIO button once to verify it."
    )
    return snapshot


def _read_int_env(
    name: str,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Return a bounded integer environment variable value."""
    raw_value = os.getenv(name)
    try:
        value = int(raw_value) if raw_value is not None else default
    except (TypeError, ValueError):
        value = default

    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _read_bool_env(name: str, default: bool) -> bool:
    """Return a truthy/falsey environment variable as a boolean."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _read_orientation_env(name: str, default: str) -> str:
    """Return a supported display orientation value."""
    value = os.getenv(name, default).strip().lower()
    if value not in {"portrait", "landscape", "auto"}:
        return default
    return value

CAMERA_BACKEND = SETTINGS.camera.backend
CAMERA_INDEX = SETTINGS.camera.index
CAPTURE_WIDTH = SETTINGS.camera.resolution.width
CAPTURE_HEIGHT = SETTINGS.camera.resolution.height
CAMERA_AUTOFOCUS_MODE = SETTINGS.camera.autofocus_mode
CAMERA_EXPOSURE = SETTINGS.camera.exposure
CAMERA_BRIGHTNESS = SETTINGS.camera.brightness
CAPTURE_DELAY_SECONDS = SETTINGS.camera.capture_delay_seconds
PREVIEW_WIDTH = SETTINGS.camera.preview.resolution.width
PREVIEW_HEIGHT = SETTINGS.camera.preview.resolution.height
PREVIEW_TARGET_FPS = SETTINGS.camera.preview.target_fps
PREVIEW_FORCE_MJPEG = SETTINGS.camera.preview.force_mjpeg
GRAYSCALE = SETTINGS.camera.grayscale
MAX_DIMENSION = SETTINGS.camera.max_dimension
ENABLE_GPIO_BUTTON = SETTINGS.button.enabled
CAPTURE_BUTTON_PIN = SETTINGS.button.pin
GPIO_BUTTON_DEBOUNCE_SECONDS = SETTINGS.button.debounce_seconds
GPIO_BUTTON_HOLD_SECONDS = SETTINGS.button.hold_seconds
MODE_BUTTON_1_PIN = SETTINGS.button.mode_button_1_pin
MODE_BUTTON_2_PIN = SETTINGS.button.mode_button_2_pin
MODE_BUTTON_3_PIN = SETTINGS.button.mode_button_3_pin
MODE_BUTTON_4_PIN = SETTINGS.button.mode_button_4_pin
MODE_BUTTON_5_PIN = SETTINGS.button.mode_button_5_pin
BACK_BUTTON_PIN = SETTINGS.button.back_button_pin
ENABLE_GPIO_LED = SETTINGS.led.enabled
GPIO_LED_PIN = SETTINGS.led.pin
GPIO_LED_ACTIVE_HIGH = SETTINGS.led.active_high
APP_HOST = SETTINGS.app.host
APP_PORT = SETTINGS.app.port
FLASK_DEBUG = SETTINGS.app.debug
STORE_IMAGES = SETTINGS.retention.store_images
TEXT_HISTORY_RETENTION_DAYS = SETTINGS.retention.text_history_retention_days
RETRY_MEDIA_RETENTION_HOURS = SETTINGS.retention.retry_media_retention_hours
PURGE_ON_STARTUP = SETTINGS.retention.purge_on_startup
OFFLINE_RETRY_ENABLED = SETTINGS.offline_retry.enabled
UI_DEBUG = _read_bool_env("UI_DEBUG", False)
LIVE_PREVIEW_FORCE_POLLING = _read_bool_env("LIVE_PREVIEW_FORCE_POLLING", False)

UI_BASE_FONT_SIZE = _read_int_env("UI_BASE_FONT_SIZE", 20, minimum=16, maximum=42)
UI_TITLE_FONT_SIZE = _read_int_env("UI_TITLE_FONT_SIZE", 34, minimum=24, maximum=72)
UI_STATUS_FONT_SIZE = _read_int_env("UI_STATUS_FONT_SIZE", 28, minimum=20, maximum=64)
UI_BUTTON_FONT_SIZE = _read_int_env("UI_BUTTON_FONT_SIZE", 24, minimum=18, maximum=42)
UI_TOUCH_TARGET = _read_int_env("UI_TOUCH_TARGET", 68, minimum=52, maximum=96)
UI_DISPLAY_ORIENTATION = _read_orientation_env(
    "UI_DISPLAY_ORIENTATION",
    "landscape",
)
LIVE_PREVIEW_FRAME_INTERVAL_MS = _read_int_env(
    "LIVE_PREVIEW_FRAME_INTERVAL_MS",
    max(20, int(round(1000.0 / max(1.0, PREVIEW_TARGET_FPS)))),
    minimum=20,
    maximum=500,
)
UI_HEALTH_REFRESH_MS = _read_int_env("UI_HEALTH_REFRESH_MS", 5000, minimum=2000, maximum=60000)
RESULT_HISTORY_LIMIT = SETTINGS.retention.text_history_max_items
RAW_SCREEN_WIDTH = max(240, min(1920, SETTINGS.display.size.width))
RAW_SCREEN_HEIGHT = max(240, min(1920, SETTINGS.display.size.height))
if UI_DISPLAY_ORIENTATION == "landscape" and RAW_SCREEN_WIDTH < RAW_SCREEN_HEIGHT:
    UI_SCREEN_WIDTH, UI_SCREEN_HEIGHT = RAW_SCREEN_HEIGHT, RAW_SCREEN_WIDTH
elif UI_DISPLAY_ORIENTATION == "portrait" and RAW_SCREEN_WIDTH > RAW_SCREEN_HEIGHT:
    UI_SCREEN_WIDTH, UI_SCREEN_HEIGHT = RAW_SCREEN_HEIGHT, RAW_SCREEN_WIDTH
else:
    UI_SCREEN_WIDTH, UI_SCREEN_HEIGHT = RAW_SCREEN_WIDTH, RAW_SCREEN_HEIGHT
UI_PROCESSING_REFRESH_MS = _read_int_env("UI_PROCESSING_REFRESH_MS", 800, minimum=400, maximum=5000)
UI_IDLE_REFRESH_MS = _read_int_env("UI_IDLE_REFRESH_MS", 2500, minimum=1000, maximum=10000)
DEFAULT_CAPTURE_INTERNAL_MODE = SETTINGS.ai.default_mode
DEFAULT_CAPTURE_MODE = INTERNAL_TO_UI_MODE.get(DEFAULT_CAPTURE_INTERNAL_MODE, "read_text")
READY_DETAIL = "Press button to select the mode."
MODE_SELECTED_DETAIL = "Selected mode ready. Press Button Main to capture."
HARDWARE_IDLE_SCREENS = {"home", "result", "error"}
MODE_BUTTON_PINS = {
    "read_text": MODE_BUTTON_1_PIN,
    "summarize_document": MODE_BUTTON_2_PIN,
    "analyze_image": MODE_BUTTON_3_PIN,
    "professional_assistant": MODE_BUTTON_4_PIN,
    "solve_problem": MODE_BUTTON_5_PIN,
}
if OFFLINE_RETRY_ENABLED:
    OFFLINE_RETRY_QUEUE = OfflineRetryQueue(
        queue_path=OFFLINE_RETRY_QUEUE_PATH,
        storage_dir=OFFLINE_RETRY_STORAGE_PATH,
        poll_interval_seconds=SETTINGS.offline_retry.poll_interval_seconds,
        max_entries=SETTINGS.offline_retry.max_items,
        max_attempts=SETTINGS.offline_retry.max_attempts,
        initial_delay_seconds=SETTINGS.offline_retry.initial_delay_seconds,
        max_delay_seconds=SETTINGS.offline_retry.max_delay_seconds,
        retention_hours=RETRY_MEDIA_RETENTION_HOURS,
        min_free_bytes=SETTINGS.offline_retry.min_free_mb * 1024 * 1024,
        max_storage_bytes=SETTINGS.offline_retry.max_storage_mb * 1024 * 1024,
        quarantine_dir=PRIVATE_QUARANTINE_PATH,
    )

if APP_HOST == "0.0.0.0":
    LOGGER.warning(
        "Security warning: APP_HOST is set to 0.0.0.0. This pilot release is intended for local-only kiosk access."
    )

LED_INDICATOR = LEDIndicator.create(
    pin=GPIO_LED_PIN,
    enabled=ENABLE_GPIO_LED,
    active_high=GPIO_LED_ACTIVE_HIGH,
)
LIVE_PREVIEW = LivePreviewService(
    backend=CAMERA_BACKEND,
    camera_index=CAMERA_INDEX,
    width=CAPTURE_WIDTH,
    height=CAPTURE_HEIGHT,
    preview_width=PREVIEW_WIDTH,
    preview_height=PREVIEW_HEIGHT,
    autofocus_mode=CAMERA_AUTOFOCUS_MODE,
    exposure=CAMERA_EXPOSURE,
    brightness=CAMERA_BRIGHTNESS,
    force_mjpeg=PREVIEW_FORCE_MJPEG,
    target_fps=PREVIEW_TARGET_FPS,
    frame_interval_seconds=LIVE_PREVIEW_FRAME_INTERVAL_MS / 1000.0,
)


@app.before_request
def first_boot_setup_gate():
    """Redirect normal routes into the mandatory setup wizard until setup completes."""
    endpoint = request.endpoint or ""
    setup_endpoints = {
        "setup",
        "admin_setup",
        "setup_state_api",
        "setup_wifi_scan",
        "setup_wifi_connect",
        "setup_openai_key",
        "setup_camera_test",
        "setup_gpio_test_start",
        "setup_gpio_test_stop",
        "setup_finish",
        "live_preview_frame",
        "live_preview_stream",
        "static",
    }
    if _setup_is_complete():
        if endpoint not in setup_endpoints and SETUP_GPIO_VERIFIER is not None:
            _stop_setup_gpio_test()
        return None

    if endpoint in setup_endpoints | {"index"}:
        if endpoint == "index":
            return redirect(url_for("setup"))
        return None
    return redirect(url_for("setup"))


@app.get("/")
def index():
    """Render the current device screen."""
    return render_template("index.html", **_build_template_context())


@app.get("/setup")
def setup():
    """Render the first-boot setup wizard."""
    return render_template("index.html", **_build_template_context(screen_override="setup"))


@app.get("/admin/setup")
def admin_setup():
    """Reopen the device setup wizard after first boot."""
    return redirect(url_for("setup"))


@app.get("/api/setup-state")
def setup_state_api():
    """Return the persisted setup wizard progress as JSON."""
    setup_state = _sync_setup_gpio_state()
    return jsonify(
        {
            **setup_state,
            "warnings": _build_setup_warnings(setup_state),
        }
    )


@app.get("/camera/live-frame.jpg")
def live_preview_frame():
    """Return a single live preview frame for diagnostics and compatibility."""
    try:
        frame_bytes = LIVE_PREVIEW.get_jpeg_frame()
    except CameraCaptureError as exc:
        LOGGER.warning("Live preview frame capture failed: %s", exc)
        frame_bytes = LIVE_PREVIEW.get_jpeg_frame(timeout_seconds=0.1)
    return Response(
        frame_bytes,
        mimetype="image/jpeg",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/camera/live-stream.mjpg")
def live_preview_stream():
    """Return the live preview as a browser-friendly MJPEG stream."""
    return Response(
        LIVE_PREVIEW.iter_mjpeg_stream(boundary=MJPEG_BOUNDARY),
        mimetype=f"multipart/x-mixed-replace; boundary={MJPEG_BOUNDARY}",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
        direct_passthrough=True,
    )


@app.get("/api/ui-state")
def ui_state_api():
    """Return the current UI state for smooth in-browser synchronization."""
    return jsonify(_build_ui_state_api_payload())


@app.get("/api/health")
def health_status_api():
    """Return a compact device-health snapshot for the touchscreen status bar."""
    return jsonify(_build_health_summary())


@app.get("/mode")
def mode_select():
    """Keep the legacy mode route working by returning to the home screen."""
    return redirect(url_for("index"))


@app.post("/mode/select")
def select_mode():
    """Persist a touch-friendly mode selection and return home."""
    if _is_running():
        return redirect(url_for("index"))

    requested_mode = request.form.get("mode", "")
    _set_selected_mode(requested_mode)
    return redirect(url_for("index"))


@app.post("/capture")
@app.post("/capture-analyze")
@app.post("/analyze")
def capture():
    """Start a background capture + analyze run and return immediately."""
    _start_capture_job()
    return redirect(url_for("index"))


@app.post("/retry")
def retry():
    """Retry the full capture workflow after an error."""
    _start_capture_job()
    return redirect(url_for("index"))


@app.post("/reanalyze")
def reanalyze():
    """Keep the legacy reanalyze route but fail gracefully in text-only mode."""
    entry_id = request.form.get("entry_id", "")
    requested_mode = request.form.get("mode", "")
    _start_reanalyze_job(entry_id, requested_mode)
    return redirect(url_for("index"))


@app.post("/back")
def back():
    """Return to the startup ready screen."""
    _return_to_mode_selection()
    return redirect(url_for("index"))


@app.post("/clear")
def clear():
    """Clear the saved result/error and return to the ready screen."""
    _clear_and_reset_ui_state(clear_selected_mode=True)
    return redirect(url_for("index"))


@app.post("/data/delete-all")
def delete_all_data():
    """Delete retained local user data after an explicit confirmation."""
    if request.form.get("confirm", "").strip().lower() != "delete-all":
        LOGGER.warning("Delete-all request ignored because confirmation token was missing")
        return redirect(url_for("index"))
    if request.form.get("confirm_stage", "").strip().lower() != "final":
        LOGGER.warning("Delete-all request ignored because second confirmation was missing")
        return redirect(url_for("index"))

    _delete_all_user_data()
    LOGGER.info("All retained local user data was deleted from the device")
    return redirect(url_for("index"))


@app.get("/history")
def history():
    """Render the recent-results screen."""
    return render_template("index.html", **_build_template_context(screen_override="history"))


@app.get("/history/<entry_id>")
def history_detail(entry_id: str):
    """Render a saved history entry without disturbing the active device state."""
    entry = _get_result_history_entry(entry_id)
    if entry is None:
        return redirect(url_for("history"))
    return render_template(
        "index.html",
        **_build_template_context(screen_override="history_detail", history_entry=entry),
    )


@app.post("/setup/wifi/scan")
def setup_wifi_scan():
    """Scan for nearby Wi-Fi networks via nmcli and persist the result."""
    _run_setup_wifi_scan()
    return redirect(url_for("setup"))


@app.post("/setup/wifi/connect")
def setup_wifi_connect():
    """Connect to a Wi-Fi network via nmcli and persist non-secret metadata."""
    _run_setup_wifi_connect(
        selected_ssid=request.form.get("ssid", ""),
        manual_ssid=request.form.get("manual_ssid", ""),
        password=request.form.get("password", ""),
        connection_name=request.form.get("connection_name", ""),
    )
    return redirect(url_for("setup"))


@app.post("/setup/openai-key")
def setup_openai_key():
    """Save and verify the OpenAI API key."""
    _run_setup_openai_key(request.form.get("openai_api_key", ""))
    return redirect(url_for("setup"))


@app.post("/setup/camera/test")
def setup_camera_test():
    """Run a one-shot camera diagnostic for the setup wizard."""
    _run_setup_camera_test()
    return redirect(url_for("setup"))


@app.post("/setup/gpio/test/start")
def setup_gpio_test_start():
    """Start the temporary GPIO verifier used by the setup wizard."""
    _start_setup_gpio_test()
    return redirect(url_for("setup"))


@app.post("/setup/gpio/test/stop")
def setup_gpio_test_stop():
    """Stop the temporary GPIO verifier and persist the final progress snapshot."""
    _stop_setup_gpio_test()
    return redirect(url_for("setup"))


@app.post("/setup/finish")
def setup_finish():
    """Finalize the setup wizard, mark the device configured, and restart the app."""
    _finish_setup(
        warnings_acknowledged=request.form.get("warnings_acknowledged", "").strip().lower()
        in {"1", "true", "yes", "on"},
    )
    return redirect(url_for("index" if _setup_is_complete() else "setup"))


def _sync_setup_gpio_state() -> dict[str, Any]:
    """Persist live GPIO setup progress while the temporary verifier is active."""
    snapshot = _snapshot_setup_gpio_progress()
    state = _load_setup_state()
    if not snapshot.get("active"):
        return state
    if (
        state["gpio"].get("active")
        and state["gpio"].get("pressed_labels", []) == snapshot["pressed_labels"]
        and bool(state["gpio"].get("all_pressed")) == bool(snapshot["all_pressed"])
    ):
        return state
    required = [
        {
            "label": item["label"],
            "pin": item["pin"],
            "pressed": item["label"] in set(snapshot["pressed_labels"]),
        }
        for item in snapshot["required"]
    ]
    return _write_setup_state(
        {
            "gpio": {
                "status": "pass" if snapshot["all_pressed"] else "running",
                "message": snapshot["message"],
                "active": True,
                "required": required,
                "pressed_labels": snapshot["pressed_labels"],
                "all_pressed": snapshot["all_pressed"],
            }
        }
    )


def _run_setup_wifi_scan() -> None:
    """Scan nearby Wi-Fi networks and save the result into setup state."""
    try:
        networks = scan_wifi_networks()
        message = (
            f"Found {len(networks)} Wi-Fi network{'s' if len(networks) != 1 else ''}."
            if networks
            else "No nearby Wi-Fi networks were found."
        )
        _write_setup_state(
            {
                "current_step": "wifi",
                "finish_message": "",
                "wifi": {
                    "scan_status": "pass",
                    "available_networks": networks,
                    "message": message,
                },
            }
        )
    except DeviceSetupError as exc:
        LOGGER.warning("Wi-Fi scan failed: %s", exc)
        _write_setup_state(
            {
                "current_step": "wifi",
                "finish_message": "",
                "wifi": {
                    "scan_status": "fail",
                    "message": str(exc),
                },
            }
        )


def _run_setup_wifi_connect(
    *,
    selected_ssid: str,
    manual_ssid: str,
    password: str,
    connection_name: str,
) -> None:
    """Connect to Wi-Fi, persist YAML metadata, and update setup state."""
    state = _load_setup_state()
    requested_ssid = manual_ssid.strip() or selected_ssid.strip()
    hidden = bool(manual_ssid.strip()) and requested_ssid not in {
        str(item.get("ssid", "")).strip()
        for item in state["wifi"].get("available_networks", [])
        if isinstance(item, dict)
    }
    try:
        wifi_details = connect_wifi_network(
            ssid=requested_ssid,
            password=password,
            connection_name=connection_name.strip() or requested_ssid,
            hidden=hidden,
            auto_connect=True,
        )
        update_device_config(
            {
                "network": {
                    "wifi": {
                        "ssid": wifi_details["ssid"],
                        "connection_name": wifi_details["connection_name"],
                        "auto_connect": True,
                        "managed_by": "nmcli",
                    }
                }
            },
            config_path=_current_config_path(),
        )
        _write_setup_state(
            {
                "current_step": "openai",
                "finish_message": "",
                "wifi": {
                    "connect_status": "pass",
                    "ssid": wifi_details["ssid"],
                    "connection_name": wifi_details["connection_name"],
                    "message": wifi_details["message"],
                    "auto_connect": True,
                    "managed_by": "nmcli",
                },
            }
        )
    except (DeviceSetupError, SettingsError) as exc:
        LOGGER.warning("Wi-Fi connect failed: %s", exc)
        _write_setup_state(
            {
                "current_step": "wifi",
                "finish_message": "",
                "wifi": {
                    "connect_status": "fail",
                    "ssid": requested_ssid,
                    "connection_name": connection_name.strip() or requested_ssid,
                    "message": str(exc),
                },
            }
        )


def _run_setup_openai_key(api_key: str) -> None:
    """Persist and verify the OpenAI API key for the device."""
    normalized_key = api_key.strip()
    if not has_configured_openai_key(normalized_key):
        _write_setup_state(
            {
                "current_step": "openai",
                "finish_message": "",
                "openai": {
                    "status": "fail",
                    "key_present": False,
                    "message": "Enter a real OPENAI_API_KEY before continuing.",
                },
            }
        )
        return

    upsert_env_value(ENV_FILE_PATH, "OPENAI_API_KEY", normalized_key)
    os.environ["OPENAI_API_KEY"] = normalized_key
    result = check_openai_reachable()
    next_step = "camera" if result.passed else "openai"
    _write_setup_state(
        {
            "current_step": next_step,
            "finish_message": "",
            "openai": {
                "status": "pass" if result.passed else "fail",
                "key_present": True,
                "message": result.message,
            },
        }
    )


def _run_setup_camera_test() -> None:
    """Run the configured one-shot camera diagnostic."""
    result = check_camera(SETTINGS)
    next_step = "gpio" if result.passed else "camera"
    _write_setup_state(
        {
            "current_step": next_step,
            "finish_message": "",
            "camera": {
                "status": "pass" if result.passed else "fail",
                "message": result.message,
            },
        }
    )


def _stop_gpio_button_listener() -> None:
    """Stop the main GPIO button listener so setup can temporarily reuse the pins."""
    global GPIO_START_ATTEMPTED, GPIO_TRIGGER

    trigger = GPIO_TRIGGER
    GPIO_TRIGGER = None
    GPIO_START_ATTEMPTED = False
    if trigger is not None:
        trigger.close()


def _start_setup_gpio_test() -> None:
    """Start the temporary GPIO setup verifier."""
    global SETUP_GPIO_VERIFIER

    try:
        _stop_setup_gpio_verifier(restart_main_listener=False)
        _stop_gpio_button_listener()
        verifier = GPIOSetupVerifier(
            _build_setup_required_pin_map(),
            debounce_seconds=GPIO_BUTTON_DEBOUNCE_SECONDS,
        )
        verifier.start()
        with SETUP_GPIO_LOCK:
            SETUP_GPIO_VERIFIER = verifier
        snapshot = _snapshot_setup_gpio_progress()
        required = [
            {
                "label": item["label"],
                "pin": item["pin"],
                "pressed": False,
            }
            for item in snapshot["required"]
        ]
        _write_setup_state(
            {
                "current_step": "gpio",
                "finish_message": "",
                "gpio": {
                    "status": "running",
                    "message": "Press each configured GPIO button once to verify it.",
                    "active": True,
                    "required": required,
                    "pressed_labels": [],
                    "all_pressed": False,
                },
            }
        )
    except GPIOSetupVerifierError as exc:
        LOGGER.warning("GPIO setup verifier could not start: %s", exc)
        _write_setup_state(
            {
                "current_step": "gpio",
                "finish_message": "",
                "gpio": {
                    "status": "fail",
                    "message": str(exc),
                    "active": False,
                    "required": _build_setup_gpio_requirements(),
                    "pressed_labels": [],
                    "all_pressed": False,
                },
            }
        )
        if _setup_is_complete():
            _ensure_gpio_button_listener_started()


def _stop_setup_gpio_test() -> None:
    """Stop the temporary GPIO setup verifier and save the final progress snapshot."""
    state = _sync_setup_gpio_state()
    snapshot = state["gpio"]
    _stop_setup_gpio_verifier(restart_main_listener=True)
    _write_setup_state(
        {
            "current_step": "finish" if snapshot.get("all_pressed") else "gpio",
            "finish_message": "",
            "gpio": {
                "status": "pass" if snapshot.get("all_pressed") else "fail",
                "message": snapshot.get(
                    "message",
                    "All configured GPIO setup buttons were pressed successfully."
                    if snapshot.get("all_pressed")
                    else "GPIO button verification is incomplete.",
                ),
                "active": False,
                "required": snapshot.get("required", _build_setup_gpio_requirements()),
                "pressed_labels": snapshot.get("pressed_labels", []),
                "all_pressed": bool(snapshot.get("all_pressed", False)),
            },
        }
    )


def _finish_setup(*, warnings_acknowledged: bool) -> None:
    """Persist setup completion and restart the app when the wizard finishes."""
    state = _sync_setup_gpio_state()
    warnings = _build_setup_warnings(state)
    if warnings and not warnings_acknowledged:
        _write_setup_state(
            {
                "current_step": "finish",
                "warnings_acknowledged": False,
                "finish_message": "Acknowledge the setup warnings before finishing.",
            }
        )
        return

    completion_timestamp = datetime.now().isoformat(timespec="seconds")
    update_device_config(
        {
            "setup": {
                "completed": True,
                "completed_at": completion_timestamp,
                "version": 1,
            },
            "localization": {
                "locale": "en",
            },
        },
        config_path=_current_config_path(),
    )
    SETTINGS.setup.completed = True
    SETTINGS.setup.completed_at = completion_timestamp
    SETTINGS.setup.version = 1
    SETTINGS.localization.locale = "en"
    _clear_setup_state()
    _schedule_process_restart()


def _schedule_process_restart(delay_seconds: float = SETUP_RESTART_DELAY_SECONDS) -> None:
    """Restart the current Flask process after a short delay."""
    def _restart_worker() -> None:
        time.sleep(max(0.1, delay_seconds))
        os.execv(sys.executable, [sys.executable, *sys.argv])

    worker = threading.Thread(
        target=_restart_worker,
        daemon=True,
        name="setup-restart-worker",
    )
    worker.start()


def _normalize_internal_mode(mode: Any) -> str:
    """Resolve a UI mode id or legacy mode into a supported internal pipeline mode."""
    if not isinstance(mode, str):
        return ""

    normalized_mode = mode.strip().lower()
    if not normalized_mode:
        return ""
    if normalized_mode in UI_MODE_TO_INTERNAL_MODE:
        return UI_MODE_TO_INTERNAL_MODE[normalized_mode]

    try:
        return normalize_mode(normalized_mode)
    except ValueError:
        return ""


def _normalize_ui_mode(mode: Any) -> str:
    """Resolve saved mode values into one of the current five Raspberry Pi UI modes."""
    if not isinstance(mode, str):
        return ""

    normalized_mode = mode.strip().lower()
    if not normalized_mode:
        return ""
    if normalized_mode in UI_MODE_BY_ID:
        return normalized_mode

    internal_mode = _normalize_internal_mode(normalized_mode)
    if not internal_mode:
        return ""
    return INTERNAL_TO_UI_MODE.get(internal_mode, "")


def _resolve_mode_pair(
    selected_mode: Any,
    selected_mode_internal: Any = None,
    *,
    fallback_to_default: bool = False,
) -> tuple[str, str]:
    """Return the UI mode id and canonical internal mode for the current state."""
    ui_mode = _normalize_ui_mode(selected_mode)
    internal_mode = _normalize_internal_mode(selected_mode_internal)

    if ui_mode and not internal_mode:
        internal_mode = UI_MODE_TO_INTERNAL_MODE[ui_mode]
    if internal_mode and not ui_mode:
        ui_mode = INTERNAL_TO_UI_MODE.get(internal_mode, "")

    if fallback_to_default and not internal_mode:
        return DEFAULT_CAPTURE_MODE, DEFAULT_CAPTURE_INTERNAL_MODE
    return ui_mode, internal_mode


def _build_idle_state_payload(
    selected_mode: Any,
    selected_mode_internal: Any = None,
) -> dict[str, Any]:
    """Build the persisted home-screen payload for READY or MODE_SELECTED."""
    ui_mode, internal_mode = _resolve_mode_pair(selected_mode, selected_mode_internal)
    device_state = DeviceState.MODE_SELECTED if ui_mode else DeviceState.READY
    detail = MODE_SELECTED_DETAIL if ui_mode else READY_DETAIL
    payload = build_ui_state_payload(
        device_state,
        selected_mode=ui_mode,
        ready_detail=READY_DETAIL,
        detail=detail,
    )
    payload["selected_mode_internal"] = internal_mode
    payload["history_entry_id"] = ""
    return payload


def _build_live_preview_url() -> str:
    """Return the cache-busted live preview endpoint for the UI."""
    route_name = "live_preview_frame" if _use_snapshot_preview_route() else "live_preview_stream"
    return f"{url_for(route_name)}?t={int(datetime.now().timestamp() * 1000)}"


def _build_live_preview_base_url() -> str:
    """Return the non-cache-busted preview URL used by the browser refresh loop."""
    route_name = "live_preview_frame" if _use_snapshot_preview_route() else "live_preview_stream"
    return url_for(route_name)


def _use_snapshot_preview_route() -> bool:
    """Allow a polling fallback when MJPEG streaming needs to be disabled manually."""
    return LIVE_PREVIEW_FORCE_POLLING


def _build_live_preview_refresh_ms() -> int:
    """Return a conservative preview refresh rate for the current platform."""
    if not _use_snapshot_preview_route():
        return 0
    return max(400, int(max(CAPTURE_DELAY_SECONDS, 0.0) * 1000) + 200)


def _build_ui_state_api_payload() -> dict[str, Any]:
    """Return a public JSON-safe view of the current UI state."""
    state = _load_ui_state()
    screen = state["screen"] if state["screen"] in VALID_SCREENS else "home"
    selected_mode, selected_mode_internal = _resolve_mode_pair(
        state.get("selected_mode"),
        state.get("selected_mode_internal"),
    )
    display_status = state["status"]
    if screen == "processing":
        display_status = state["detail"] or "Processing..."
    elif screen == "result":
        display_status = state["status"] or "Answer Ready"

    selected_mode_definition = UI_MODE_BY_ID.get(selected_mode)
    selected_mode_label = (
        selected_mode_definition["name"] if selected_mode_definition else "No mode selected"
    )

    return {
        "screen": screen,
        "device_state": state["device_state"],
        "selected_mode": selected_mode,
        "selected_mode_internal": selected_mode_internal,
        "selected_mode_label": selected_mode_label,
        "status": state["status"],
        "display_status": display_status,
        "detail": state["detail"],
        "error": state["error"],
        "error_detail": state["error_detail"],
        "current_step": state["current_step"],
        "history_entry_id": state["history_entry_id"],
        "updated_at": state["updated_at"],
        "progress_steps": _build_progress_steps(state["current_step"]),
        "has_mode_selected": bool(selected_mode),
    }


def _build_health_summary() -> dict[str, Any]:
    """Return compact health labels for the small-screen device UI."""
    snapshot = _load_health_snapshot()
    cpu_chip = _build_cpu_health_chip(snapshot)
    memory_chip = _build_memory_health_chip(snapshot)
    network_chip = _build_component_health_chip(snapshot, "network", prefix="NET")
    camera_chip = _build_camera_health_chip(snapshot)
    overall_status = _resolve_ui_health_overall_status(
        cpu_chip,
        memory_chip,
        network_chip,
        camera_chip,
    )

    return {
        "updated_at": str(snapshot.get("updated_at", "")) if snapshot else "",
        "overall": _build_overall_health_chip(overall_status, snapshot),
        "cpu": cpu_chip,
        "memory": memory_chip,
        "network": network_chip,
        "camera": camera_chip,
    }


def _load_health_snapshot() -> dict[str, Any] | None:
    """Return the newest in-memory or on-disk health snapshot when available."""
    if HEALTH_MONITOR is not None and HEALTH_MONITOR.latest_snapshot is not None:
        return HEALTH_MONITOR.latest_snapshot

    if not HEALTH_STATUS_PATH.is_file():
        return None

    try:
        snapshot = json.loads(HEALTH_STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if isinstance(snapshot, dict):
        return snapshot
    return None


def _build_overall_health_chip(
    overall_status: str,
    snapshot: dict[str, Any] | None,
) -> dict[str, str]:
    """Return the overall device-health chip."""
    label_lookup = {
        "pass": "System OK",
        "fail": "Check Device",
        "unknown": "Health Pending",
    }
    message_lookup = {
        "pass": "All monitored device checks are passing.",
        "fail": "One or more monitored device checks need attention.",
        "unknown": "Waiting for a complete health snapshot.",
    }
    updated_at = str(snapshot.get("updated_at", "")) if snapshot else ""
    message = message_lookup[overall_status]
    if updated_at:
        message = f"{message} Last update: {updated_at}."
    return {
        "status": overall_status,
        "label": label_lookup[overall_status],
        "message": message,
    }


def _build_cpu_health_chip(snapshot: dict[str, Any] | None) -> dict[str, str]:
    """Return the CPU temperature chip."""
    if not snapshot or not isinstance(snapshot.get("cpu"), dict):
        return {
            "status": "unknown",
            "label": "CPU --",
            "message": "CPU temperature is unavailable.",
        }

    cpu = snapshot["cpu"]
    status = _normalize_component_health_status(cpu.get("status"))
    temperature_c = cpu.get("temperature_c")
    label = "CPU --"
    if isinstance(temperature_c, (int, float)):
        label = f"CPU {float(temperature_c):.1f}C"
    return {
        "status": status,
        "label": label,
        "message": str(cpu.get("message", "CPU temperature is unavailable.")),
    }


def _build_memory_health_chip(snapshot: dict[str, Any] | None) -> dict[str, str]:
    """Return the memory usage chip."""
    if not snapshot or not isinstance(snapshot.get("memory"), dict):
        return {
            "status": "unknown",
            "label": "RAM --",
            "message": "Memory usage is unavailable.",
        }

    memory = snapshot["memory"]
    status = _normalize_component_health_status(memory.get("status"))
    used_percent = memory.get("used_percent")
    label = "RAM --"
    if isinstance(used_percent, (int, float)):
        label = f"RAM {float(used_percent):.1f}%"
    return {
        "status": status,
        "label": label,
        "message": str(memory.get("message", "Memory usage is unavailable.")),
    }


def _build_component_health_chip(
    snapshot: dict[str, Any] | None,
    key: str,
    *,
    prefix: str,
) -> dict[str, str]:
    """Return a compact pass/fail/unknown label for network and camera health."""
    if not snapshot or not isinstance(snapshot.get(key), dict):
        return {
            "status": "unknown",
            "label": f"{prefix} --",
            "message": f"{prefix} status is unavailable.",
        }

    component = snapshot[key]
    status = _normalize_component_health_status(component.get("status"))
    suffix_lookup = {
        "pass": "OK",
        "fail": "FAIL",
        "unknown": "WAIT",
    }
    return {
        "status": status,
        "label": f"{prefix} {suffix_lookup[status]}",
        "message": str(component.get("message", f"{prefix} status is unavailable.")),
    }


def _build_camera_health_chip(snapshot: dict[str, Any] | None) -> dict[str, str]:
    """Return camera health with live-preview-aware status overrides."""
    preview_service = LIVE_PREVIEW
    has_recent_frame = False
    latest_error = ""

    if hasattr(preview_service, "has_recent_frame"):
        try:
            has_recent_frame = bool(preview_service.has_recent_frame())
        except Exception:
            has_recent_frame = False

    if hasattr(preview_service, "latest_error_message"):
        try:
            latest_error = str(preview_service.latest_error_message() or "")
        except Exception:
            latest_error = ""

    if has_recent_frame:
        return {
            "status": "pass",
            "label": "CAM OK",
            "message": "Live preview is receiving camera frames normally.",
        }

    component = _build_component_health_chip(snapshot, "camera", prefix="CAM")
    if component["status"] != "unknown":
        return component

    if _is_live_preview_screen():
        return {
            "status": "unknown",
            "label": "CAM LIVE",
            "message": latest_error or "Live preview is warming up the camera feed.",
        }

    if latest_error:
        return {
            "status": "fail",
            "label": "CAM FAIL",
            "message": latest_error,
        }

    return component


def _resolve_ui_health_overall_status(*chips: dict[str, str]) -> str:
    """Collapse UI chip statuses into the overall health pill state."""
    statuses = [str(chip.get("status", "unknown")).lower() for chip in chips]
    if any(status == "fail" for status in statuses):
        return "fail"
    if statuses and all(status == "pass" for status in statuses):
        return "pass"
    return "unknown"


def _normalize_component_health_status(value: Any) -> str:
    """Normalize component health statuses into pass/fail/unknown."""
    normalized = str(value or "").strip().lower()
    if normalized == "pass":
        return "pass"
    if normalized == "fail":
        return "fail"
    return "unknown"


def _normalize_overall_health_status(value: Any) -> str:
    """Normalize aggregate health statuses into pass/fail/unknown."""
    normalized = str(value or "").strip().lower()
    if normalized == "healthy":
        return "pass"
    if normalized == "degraded":
        return "fail"
    return "unknown"


def _load_result_history() -> list[dict[str, Any]]:
    """Return the recent result history from memory or disk."""
    global RESULT_HISTORY_CACHE

    with RESULT_HISTORY_LOCK:
        if RESULT_HISTORY_CACHE is not None:
            return [entry.copy() for entry in RESULT_HISTORY_CACHE]

        if not RESULT_HISTORY_PATH.is_file():
            RESULT_HISTORY_CACHE = []
            return []

        try:
            raw_entries = json.loads(RESULT_HISTORY_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            quarantine_file(
                RESULT_HISTORY_PATH,
                quarantine_dir=PRIVATE_QUARANTINE_PATH,
                reason="invalid-history-json",
            )
            RESULT_HISTORY_CACHE = []
            return []

        parsed_entries: list[dict[str, Any]] = []
        if not isinstance(raw_entries, list):
            quarantine_file(
                RESULT_HISTORY_PATH,
                quarantine_dir=PRIVATE_QUARANTINE_PATH,
                reason="invalid-history-shape",
            )
            RESULT_HISTORY_CACHE = []
            return []

        for raw_entry in raw_entries:
            entry = _coerce_result_history_entry(raw_entry)
            if entry is not None:
                parsed_entries.append(entry)

        RESULT_HISTORY_CACHE = _apply_history_retention(parsed_entries)
        return [entry.copy() for entry in RESULT_HISTORY_CACHE]


def _write_result_history(entries: list[dict[str, Any]]) -> None:
    """Persist recent result history and refresh the in-memory cache."""
    global RESULT_HISTORY_CACHE

    normalized_entries = _apply_history_retention([
        entry.copy() for entry in entries[:RESULT_HISTORY_LIMIT]
        if _coerce_result_history_entry(entry) is not None
    ])
    RESULT_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    with RESULT_HISTORY_LOCK:
        RESULT_HISTORY_CACHE = normalized_entries
        atomic_write_json(
            RESULT_HISTORY_PATH,
            normalized_entries,
            ensure_ascii=False,
            indent=2,
        )


def _append_result_history(
    result: PipelineResult,
    selected_mode: str,
    selected_mode_internal: str,
) -> dict[str, Any] | None:
    """Save a successful assistant response into recent-results history."""
    answer = (result.answer or "").strip()
    if not answer:
        return None

    ui_mode, internal_mode = _resolve_mode_pair(selected_mode, selected_mode_internal)
    history_entries = _load_result_history()
    created_at = _timestamp()
    entry_id = str(int(datetime.now().timestamp() * 1000))
    history_entry = {
        "id": entry_id,
        "created_at": created_at,
        "selected_mode": ui_mode,
        "selected_mode_internal": internal_mode,
        "mode_label": _history_mode_label(ui_mode, internal_mode),
        "status": result.status,
        "answer": answer,
        "summary": _history_summary(answer),
        "camera_backend_used": result.camera_backend_used or "",
        "camera_resolution": list(result.camera_resolution) if result.camera_resolution else [],
        "model_used": result.model_used or "",
        "duration_seconds": result.duration_seconds,
        "retry_status": result.retry_status or "",
        "error_summary": result.error_summary or "",
    }
    history_entries.insert(0, history_entry)
    _write_result_history(history_entries)
    return history_entry


def _get_result_history_entry(entry_id: str) -> dict[str, Any] | None:
    """Return a single saved result history entry by identifier."""
    for entry in _load_result_history():
        if entry.get("id") == entry_id:
            return entry
    return None


def _coerce_result_history_entry(raw_entry: Any) -> dict[str, Any] | None:
    """Validate the stored history payload shape."""
    if not isinstance(raw_entry, dict):
        return None

    entry_id = str(raw_entry.get("id", "")).strip()
    answer = str(raw_entry.get("answer", "")).strip()
    if not entry_id or not answer:
        return None

    selected_mode, selected_mode_internal = _resolve_mode_pair(
        raw_entry.get("selected_mode", ""),
        raw_entry.get("selected_mode_internal", ""),
    )
    mode_label = str(raw_entry.get("mode_label", "")).strip() or _history_mode_label(
        selected_mode,
        selected_mode_internal,
    )
    summary = str(raw_entry.get("summary", "")).strip() or _history_summary(answer)

    raw_resolution = raw_entry.get("camera_resolution", [])
    camera_resolution: list[int] = []
    if (
        isinstance(raw_resolution, (list, tuple))
        and len(raw_resolution) == 2
        and all(isinstance(value, (int, float)) for value in raw_resolution)
    ):
        camera_resolution = [int(raw_resolution[0]), int(raw_resolution[1])]

    return {
        "id": entry_id,
        "created_at": str(raw_entry.get("created_at", "")),
        "selected_mode": selected_mode,
        "selected_mode_internal": selected_mode_internal,
        "mode_label": mode_label,
        "status": str(raw_entry.get("status", "success")).strip() or "success",
        "answer": answer,
        "summary": summary,
        "camera_backend_used": str(raw_entry.get("camera_backend_used", "")),
        "camera_resolution": camera_resolution,
        "model_used": str(raw_entry.get("model_used", "")).strip(),
        "duration_seconds": _coerce_optional_float(raw_entry.get("duration_seconds")),
        "retry_status": str(raw_entry.get("retry_status", "")).strip(),
        "error_summary": str(raw_entry.get("error_summary", "")).strip(),
    }


def _history_mode_label(selected_mode: str, selected_mode_internal: str) -> str:
    """Return the best user-facing label for a stored history entry."""
    if selected_mode in MODE_LABELS:
        return MODE_LABELS[selected_mode]
    if selected_mode_internal:
        return get_mode(selected_mode_internal).name
    return "Saved Result"


def _history_summary(answer: str, max_chars: int = 160) -> str:
    """Return a compact one-line summary for the recent-results list."""
    cleaned = " ".join(answer.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _history_entry_camera_resolution(entry: dict[str, Any]) -> tuple[int, int] | None:
    """Return the saved capture resolution for a history entry when available."""
    raw_resolution = entry.get("camera_resolution", [])
    if (
        isinstance(raw_resolution, (list, tuple))
        and len(raw_resolution) == 2
        and all(isinstance(value, (int, float)) for value in raw_resolution)
    ):
            return (int(raw_resolution[0]), int(raw_resolution[1]))
    return None


def _result_history_entry_has_reanalyze_assets(entry: dict[str, Any]) -> bool:
    """Return False while privacy-first text retention is enabled."""
    return False


def _decorate_result_history_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Add non-persisted fields used by the touchscreen templates."""
    decorated_entry = entry.copy()
    decorated_entry["has_thumbnail"] = False
    decorated_entry["has_reanalyze_assets"] = False
    decorated_entry["thumbnail_data_url"] = ""
    return decorated_entry


def _decorate_result_history_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Decorate a full list of persisted history entries for template rendering."""
    return [_decorate_result_history_entry(entry) for entry in entries]


def _build_reanalyze_mode_options(current_mode: str) -> list[dict[str, str]]:
    """Return alternate UI modes that can reuse the same already-captured image."""
    return []


def _coerce_optional_float(value: Any) -> float | None:
    """Return a float value when the history payload contains one."""
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _apply_history_retention(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Trim history entries by age and configured item count."""
    retained: list[dict[str, Any]] = []
    cutoff = datetime.now() - timedelta(days=TEXT_HISTORY_RETENTION_DAYS)
    for entry in entries:
        created_at = _parse_timestamp(str(entry.get("created_at", "")))
        if created_at is not None and created_at < cutoff:
            continue
        retained.append(entry)
        if len(retained) >= RESULT_HISTORY_LIMIT:
            break
    return retained


def _parse_timestamp(value: str) -> datetime | None:
    """Parse an ISO timestamp from persisted UI/history payloads."""
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _resolve_active_reanalyze_entry(state: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Return the current result/history entry whose saved image can be re-analyzed."""
    return None


def _build_template_context(
    screen_override: str | None = None,
    *,
    history_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the render context for the current screen."""
    state = _load_ui_state()
    screen = screen_override or state["screen"]
    if screen not in VALID_SCREENS:
        screen = "home"

    selected_mode, selected_mode_internal = _resolve_mode_pair(
        state.get("selected_mode"),
        state.get("selected_mode_internal"),
    )
    selected_mode_definition = UI_MODE_BY_ID.get(selected_mode)
    selected_mode_label = (
        selected_mode_definition["name"] if selected_mode_definition else "No mode selected"
    )
    selected_mode_description = (
        selected_mode_definition["description"]
        if selected_mode_definition
        else "Press one of the mode buttons to choose what the assistant should do."
    )
    setup_state = _sync_setup_gpio_state() if screen == "setup" else None
    setup_warnings = _build_setup_warnings(setup_state) if setup_state is not None else []
    history_entries = _load_result_history()
    recent_results = _decorate_result_history_entries(history_entries)
    effective_history_entry = _decorate_result_history_entry(history_entry) if history_entry is not None else None
    current_result_history_entry: dict[str, Any] | None = None
    answer_text = state["answer"]
    display_status = state["status"]
    if screen == "processing":
        display_status = state["detail"] or "Processing..."
    elif screen == "result":
        display_status = state["status"] or "Answer Ready"
        current_result_history_entry = _resolve_active_reanalyze_entry(state)
        if current_result_history_entry is not None:
            current_result_history_entry = _decorate_result_history_entry(current_result_history_entry)
    elif screen == "history":
        display_status = f"{len(recent_results)} saved result{'s' if len(recent_results) != 1 else ''}"
    elif screen == "history_detail":
        if effective_history_entry is None:
            if recent_results:
                effective_history_entry = recent_results[0]
            else:
                screen = "history"
                display_status = "No saved results"
        if effective_history_entry is not None:
            answer_text = effective_history_entry["answer"]
            selected_mode = str(effective_history_entry.get("selected_mode", ""))
            selected_mode_internal = str(effective_history_entry.get("selected_mode_internal", ""))
            selected_mode_label = str(
                effective_history_entry.get("mode_label", selected_mode_label or "Saved Result")
            )
            selected_mode_description = "Recent text-only result stored on device for quick review."
            display_status = "Saved Result"

    reanalyze_entry = None
    reanalyze_mode_options: list[dict[str, str]] = []

    active_mode_definition = None
    if selected_mode_internal:
        active_mode_definition = get_mode(selected_mode_internal)

    ui_state_api_url = url_for("ui_state_api")
    ui_state_updated_at = state["updated_at"]
    auto_refresh_ms = _get_auto_refresh_ms(screen)
    if screen == "setup" and setup_state is not None:
        ui_state_api_url = url_for("setup_state_api")
        ui_state_updated_at = setup_state["updated_at"]
        auto_refresh_ms = 1500 if setup_state["gpio"].get("active") else None

    return {
        "screen": screen,
        "status": state["status"],
        "display_status": display_status,
        "detail": state["detail"],
        "error": state["error"],
        "error_detail": state["error_detail"],
        "answer_html": _format_answer_html(answer_text),
        "selected_mode": selected_mode,
        "selected_mode_internal": selected_mode_internal,
        "selected_mode_label": selected_mode_label,
        "selected_mode_description": selected_mode_description,
        "active_mode_name": active_mode_definition.name if active_mode_definition else "",
        "has_mode_selected": bool(selected_mode),
        "recent_results": recent_results,
        "has_recent_results": bool(recent_results),
        "history_entry": effective_history_entry,
        "current_result_history_entry": current_result_history_entry,
        "reanalyze_entry": reanalyze_entry,
        "reanalyze_mode_options": reanalyze_mode_options,
        "mode_options": UI_MODE_OPTIONS,
        "progress_steps": _build_progress_steps(state["current_step"]),
        "live_preview_url": _build_live_preview_url(),
        "live_preview_base_url": _build_live_preview_base_url(),
        "live_preview_refresh_ms": _build_live_preview_refresh_ms(),
        "default_capture_mode_label": MODE_LABELS[DEFAULT_CAPTURE_MODE],
        "auto_refresh_ms": auto_refresh_ms,
        "ui_state_api_url": ui_state_api_url,
        "ui_state_updated_at": ui_state_updated_at,
        "health_api_url": url_for("health_status_api"),
        "health_refresh_ms": UI_HEALTH_REFRESH_MS,
        "health_summary": _build_health_summary(),
        "setup_state": setup_state,
        "setup_warnings": setup_warnings,
        "setup_has_warnings": bool(setup_warnings),
        "setup_finish_message": setup_state.get("finish_message", "") if setup_state else "",
        "setup_gpio_running": bool(setup_state and setup_state["gpio"].get("active")),
        "setup_can_exit": _setup_is_complete(),
        "show_debug": UI_DEBUG,
        "ui_config": {
            "screen_width": UI_SCREEN_WIDTH,
            "screen_height": UI_SCREEN_HEIGHT,
            "base_font_size": UI_BASE_FONT_SIZE,
            "title_font_size": UI_TITLE_FONT_SIZE,
            "status_font_size": UI_STATUS_FONT_SIZE,
            "button_font_size": UI_BUTTON_FONT_SIZE,
            "touch_target": UI_TOUCH_TARGET,
            "orientation": _resolve_orientation(),
            "locale": SETTINGS.localization.locale,
        },
    }
 

def _start_capture_job() -> bool:
    """Start the shared capture workflow unless one is already running."""
    global RUNNING

    with RUN_LOCK:
        if RUNNING:
            LOGGER.info("Capture request ignored because a job is already running")
            return False
        RUNNING = True

    state = _load_ui_state()
    selected_mode, selected_mode_internal = _resolve_mode_pair(
        state.get("selected_mode"),
        state.get("selected_mode_internal"),
        fallback_to_default=True,
    )
    LOGGER.info(
        "Background capture job starting ui_mode=%s internal_mode=%s",
        selected_mode,
        selected_mode_internal,
    )
    preview_released = LIVE_PREVIEW.pause()
    if preview_released is False:
        LOGGER.warning("Live preview did not release the camera before capture started")
    _write_device_state(
        DeviceState.CAPTURING,
        selected_mode=selected_mode,
        selected_mode_internal=selected_mode_internal,
        detail=PROGRESS_STEPS[0],
        current_step=0,
    )

    worker = threading.Thread(
        target=_run_capture_job,
        args=(selected_mode, selected_mode_internal),
        daemon=True,
        name="touch-capture-worker",
    )
    worker.start()
    return True


def _start_reanalyze_job(entry_id: str, requested_mode: str) -> bool:
    """Reject same-image re-analysis while text-only retention is active."""
    LOGGER.info(
        "Re-analyze request ignored because text-only retention is enabled entry_id=%s requested_mode=%s",
        entry_id,
        requested_mode,
    )
    _record_error_state(
        _load_ui_state().get("selected_mode", ""),
        _load_ui_state().get("selected_mode_internal", ""),
        "Saved image re-analysis is unavailable while text-only retention is enabled.",
    )
    return False


def _run_capture_job(selected_mode: str, selected_mode_internal: str) -> None:
    """Run the capture pipeline in the background and persist screen state."""
    global RUNNING

    try:
        captured_path, processed_path = build_capture_session_paths(PRIVATE_CURRENT_PATH)
        LOGGER.info(
            "Capture job using working files captured=%s processed=%s",
            captured_path,
            processed_path,
        )
        result = run_capture_analyze(
            mode=selected_mode_internal,
            backend=CAMERA_BACKEND,
            camera_index=CAMERA_INDEX,
            width=CAPTURE_WIDTH,
            height=CAPTURE_HEIGHT,
            captured_path=str(captured_path),
            processed_path=str(processed_path),
            grayscale=GRAYSCALE,
            max_dimension=MAX_DIMENSION,
            autofocus_mode=CAMERA_AUTOFOCUS_MODE,
            exposure=CAMERA_EXPOSURE,
            brightness=CAMERA_BRIGHTNESS,
            capture_delay_seconds=CAPTURE_DELAY_SECONDS,
            status_callback=lambda message: _update_processing_state(
                selected_mode,
                selected_mode_internal,
                message,
            ),
        )
        save_latest_result(result, output_path=str(LATEST_RESULT_PATH))
        history_entry = _append_result_history(result, selected_mode, selected_mode_internal)
        _write_device_state(
            DeviceState.DONE,
            selected_mode=selected_mode,
            selected_mode_internal=selected_mode_internal,
            history_entry_id=history_entry["id"] if history_entry is not None else "",
            detail="Done",
            answer=result.answer or "",
            current_step=len(PROGRESS_STEPS),
            status="Answer Ready",
        )
        LOGGER.info(
            "Background capture job completed ui_mode=%s internal_mode=%s",
            selected_mode,
            selected_mode_internal,
        )
    except (PipelineError, ValueError) as exc:
        LOGGER.exception(
            "Background capture job failed ui_mode=%s internal_mode=%s",
            selected_mode,
            selected_mode_internal,
        )
        if not _queue_retryable_pipeline_error(selected_mode, selected_mode_internal, exc):
            _record_error_state(selected_mode, selected_mode_internal, str(exc))
    except Exception as exc:
        LOGGER.exception(
            "Background capture job crashed ui_mode=%s internal_mode=%s",
            selected_mode,
            selected_mode_internal,
        )
        _record_error_state(
            selected_mode,
            selected_mode_internal,
            f"Unexpected error: {exc}",
        )
    finally:
        _cleanup_current_private_media()
        LIVE_PREVIEW.resume()
        with RUN_LOCK:
            RUNNING = False


def _run_reanalyze_job(source_entry_id: str, selected_mode: str, selected_mode_internal: str) -> None:
    """Keep the legacy worker path aligned with the text-only retention policy."""
    _record_error_state(
        selected_mode,
        selected_mode_internal,
        "Saved image re-analysis is unavailable while text-only retention is enabled.",
    )


def _update_processing_state(
    selected_mode: str,
    selected_mode_internal: str,
    pipeline_message: str,
) -> None:
    """Translate shared pipeline updates into small-screen UI text."""
    step_index = _step_index_for_message(pipeline_message)
    detail = PROGRESS_STEPS[step_index]
    _write_device_state(
        DeviceState.CAPTURING if step_index == 0 else DeviceState.PROCESSING,
        selected_mode=selected_mode,
        selected_mode_internal=selected_mode_internal,
        detail=detail,
        current_step=step_index,
    )


def _record_error_state(
    selected_mode: str,
    selected_mode_internal: str,
    error_message: str,
) -> None:
    """Persist a short, readable error state for the touchscreen."""
    friendly_error = _humanize_error(error_message)
    LOGGER.error(
        "Persisting device error state ui_mode=%s internal_mode=%s friendly_error=%s error=%s",
        selected_mode,
        selected_mode_internal,
        friendly_error,
        error_message,
    )
    failure_result = PipelineResult(
        captured_path=None,
        processed_path=None,
        answer=error_message,
        mode=selected_mode_internal or DEFAULT_CAPTURE_INTERNAL_MODE,
        camera_backend_used=CAMERA_BACKEND,
        camera_resolution=None,
        status="error",
    )
    save_latest_result(failure_result, output_path=str(LATEST_RESULT_PATH))
    _write_device_state(
        DeviceState.ERROR,
        selected_mode=selected_mode,
        selected_mode_internal=selected_mode_internal,
        detail="Try again when ready",
        error=friendly_error,
        error_detail=error_message,
        current_step=-1,
    )


def _queue_retryable_pipeline_error(
    selected_mode: str,
    selected_mode_internal: str,
    error: Exception,
) -> bool:
    """Queue retryable AI failures instead of losing the capture outright."""
    queue = OFFLINE_RETRY_QUEUE
    if queue is None or not bool(getattr(error, "retryable", False)):
        return False

    processed_path = getattr(error, "processed_path", None)
    if processed_path is None or not Path(processed_path).is_file():
        return False

    try:
        entry = queue.enqueue(
            selected_mode=selected_mode,
            selected_mode_internal=selected_mode_internal,
            processed_path=processed_path,
            camera_backend_used=getattr(error, "camera_backend_used", None) or CAMERA_BACKEND,
            camera_resolution=getattr(error, "camera_resolution", None),
            error_message=str(error),
            error_category=_humanize_error(str(error)).lower().replace(" ", "_"),
        )
    except (OfflineRetryQueueFullError, OfflineRetryQueueError) as exc:
        LOGGER.exception(
            "Offline retry queue could not store failed request ui_mode=%s internal_mode=%s",
            selected_mode,
            selected_mode_internal,
        )
        _record_error_state(selected_mode, selected_mode_internal, str(exc))
        return True

    queue_position = queue.pending_count()
    friendly_error = _humanize_error(str(error))
    queued_message = (
        "Saved for automatic retry.\n"
        f"Reason: {friendly_error}.\n"
        f"Queue position: {queue_position}.\n"
        "The assistant will retry this capture again when network/OpenAI is available."
    )
    queued_result = PipelineResult(
        captured_path=None,
        processed_path=queue.resolve_processed_path(entry),
        answer=queued_message,
        mode=selected_mode_internal or DEFAULT_CAPTURE_INTERNAL_MODE,
        camera_backend_used=entry.camera_backend_used or CAMERA_BACKEND,
        camera_resolution=entry.camera_resolution,
        status="queued",
        retry_status="queued",
        error_summary=friendly_error,
    )
    save_latest_result(queued_result, output_path=str(LATEST_RESULT_PATH))
    _write_device_state(
        DeviceState.DONE,
        selected_mode=selected_mode,
        selected_mode_internal=selected_mode_internal,
        detail="Will retry automatically",
        answer=queued_message,
        current_step=-1,
        status="Queued for retry",
    )
    LOGGER.warning(
        "Background capture job queued for retry entry=%s ui_mode=%s internal_mode=%s",
        entry.id,
        selected_mode,
        selected_mode_internal,
    )
    return True


def _analyze_offline_retry_entry(entry: OfflineRetryEntry) -> PipelineResult:
    """Re-run AI analysis for a previously captured image from the offline queue."""
    queue = OFFLINE_RETRY_QUEUE
    if queue is None:
        raise PipelineError("Offline retry queue is unavailable.")

    processed_path = queue.resolve_processed_path(entry)
    result = run_analyze(
        mode=entry.selected_mode_internal,
        captured_path=str(processed_path),
        processed_path=str(processed_path),
        grayscale=GRAYSCALE,
        max_dimension=MAX_DIMENSION,
        screen_optimization=SETTINGS.vision.screen_optimization,
    )
    return PipelineResult(
        captured_path=None,
        processed_path=processed_path if processed_path.is_file() else result.processed_path,
        answer=result.answer,
        mode=entry.selected_mode_internal,
        camera_backend_used=entry.camera_backend_used or result.camera_backend_used,
        camera_resolution=entry.camera_resolution or result.camera_resolution,
        status="success",
        warnings=result.warnings,
        model_used=result.model_used,
        duration_seconds=result.duration_seconds,
        retry_status="retry_successful",
    )


def _record_offline_retry_success(entry: OfflineRetryEntry, result: PipelineResult) -> None:
    """Persist a deferred result once the background retry finally succeeds."""
    save_latest_result(result, output_path=str(LATEST_RESULT_PATH))
    _append_result_history(result, entry.selected_mode, entry.selected_mode_internal)
    LOGGER.info(
        "Offline retry succeeded entry=%s ui_mode=%s internal_mode=%s",
        entry.id,
        entry.selected_mode,
        entry.selected_mode_internal,
    )


def _record_offline_retry_failure(
    entry: OfflineRetryEntry,
    error: Exception,
    retryable: bool,
) -> None:
    """Log queued retry failures without interrupting the active screen."""
    if retryable:
        LOGGER.warning(
            "Offline retry deferred again entry=%s ui_mode=%s internal_mode=%s error=%s",
            entry.id,
            entry.selected_mode,
            entry.selected_mode_internal,
            error,
        )
        return

    LOGGER.error(
        "Offline retry dropped entry=%s ui_mode=%s internal_mode=%s error=%s",
        entry.id,
        entry.selected_mode,
        entry.selected_mode_internal,
        error,
    )


def _step_index_for_message(pipeline_message: str) -> int:
    """Map pipeline callback text to the simple screen progress steps."""
    normalized_message = pipeline_message.strip()
    step_lookup = {
        "Capturing image...": 0,
        "Preprocessing image...": 1,
        "Sending image to OpenAI Vision...": 2,
    }
    return step_lookup.get(normalized_message, 2)


def _get_auto_refresh_ms(screen: str) -> int | None:
    """Refresh active screens so the device UI updates without manual reloads."""
    if screen == "processing":
        return UI_PROCESSING_REFRESH_MS
    if screen in HARDWARE_IDLE_SCREENS and GPIO_TRIGGER is not None:
        return UI_IDLE_REFRESH_MS
    return None


def _resolve_orientation() -> str:
    """Resolve the display orientation for the current screen config."""
    if UI_DISPLAY_ORIENTATION == "auto":
        return "landscape" if UI_SCREEN_WIDTH > UI_SCREEN_HEIGHT else "portrait"
    return UI_DISPLAY_ORIENTATION


def _build_progress_steps(current_step: int) -> list[dict[str, str]]:
    """Return progress rows with done/active/pending display states."""
    steps: list[dict[str, str]] = []
    for index, label in enumerate(PROGRESS_STEPS):
        state = "pending"
        if current_step > index:
            state = "done"
        elif current_step == index:
            state = "active"
        steps.append({"label": label, "state": state})
    return steps


def _format_answer_html(answer: str) -> Markup:
    """Render plain-text answers as readable paragraphs and bullet lists."""
    if not answer.strip():
        return Markup("<p class='answer-empty'>No answer yet.</p>")

    parts: list[str] = []
    list_items: list[str] = []

    def flush_list() -> None:
        nonlocal list_items
        if not list_items:
            return
        items = "".join(f"<li>{item}</li>" for item in list_items)
        parts.append(f"<ul>{items}</ul>")
        list_items = []

    for raw_line in answer.splitlines():
        line = raw_line.strip()
        if not line:
            flush_list()
            continue

        bullet_match = re.match("^(?:[-*]|\\u2022|\\d+[.)])\\s+(.*)$", line)
        if bullet_match:
            list_items.append(str(escape(bullet_match.group(1))))
            continue

        flush_list()
        parts.append(f"<p>{escape(line)}</p>")

    flush_list()
    return Markup("".join(parts))


def _humanize_error(error_message: str) -> str:
    """Convert technical errors into short, friendly touchscreen messages."""
    normalized = error_message.strip().lower()
    if any(token in normalized for token in ("camera", "opencv", "webcam", "videocapture")):
        return "Camera disconnected"
    if "could not connect to openai" in normalized or "internet connection" in normalized:
        return "Network unavailable"
    if any(
        token in normalized
        for token in (
            "invalid image",
            "valid image",
            "unsupported image extension",
            "could not load image",
            "cannot identify image file",
        )
    ):
        return "Invalid image"
    if "timed out after" in normalized:
        return "OpenAI request timed out"
    if any(token in normalized for token in ("timed out", "rate limit", "quota reached")):
        return "OpenAI request failed"
    if any(
        token in normalized
        for token in (
            "authentication failed",
            "missing openai api key",
            "permission denied",
            "model '",
            "openai request",
            "openai api error",
            "openai sdk error",
        )
    ):
        return "OpenAI request failed"
    if "empty response" in normalized:
        return "No text detected"
    if "no image available" in normalized:
        return "No image detected"
    return error_message.strip() or "Something went wrong"


def _default_ui_state() -> dict[str, Any]:
    """Return the default ready-state shown on first boot."""
    default_state = _build_idle_state_payload("", "")
    default_state["updated_at"] = _timestamp()
    return default_state


def _timestamp() -> str:
    """Return a small ISO timestamp for state updates."""
    return datetime.now().isoformat(timespec="seconds")


def _processed_metadata_path(image_path: str | Path) -> Path:
    """Return the metadata sidecar path for a processed image file."""
    file_path = Path(image_path)
    return file_path.with_name(f"{file_path.name}.meta.json")


def _cleanup_current_private_media() -> None:
    """Best-effort delete current captured and processed working files."""
    if PRIVATE_CURRENT_PATH.is_dir():
        for entry in list(PRIVATE_CURRENT_PATH.iterdir()):
            if entry.is_dir():
                safe_rmtree(entry)
            else:
                safe_unlink(entry)
        try:
            next(PRIVATE_CURRENT_PATH.iterdir())
        except StopIteration:
            safe_rmtree(PRIVATE_CURRENT_PATH)
        except OSError:
            pass


def _purge_runtime_artifacts(*, delete_all: bool = False) -> None:
    """Purge orphaned private media and trim persisted text history."""
    _cleanup_current_private_media()

    if OFFLINE_RETRY_QUEUE is not None:
        if delete_all:
            OFFLINE_RETRY_QUEUE.clear()
        else:
            OFFLINE_RETRY_QUEUE.prune()

    if delete_all:
        safe_rmtree(PRIVATE_CURRENT_PATH)
        safe_rmtree(PRIVATE_RETRY_PATH)
        safe_unlink(RESULT_HISTORY_PATH)
        safe_unlink(LATEST_RESULT_PATH)
        safe_unlink(UI_STATE_PATH)
        safe_unlink(SETUP_STATE_PATH)
        safe_rmtree(PRIVATE_QUARANTINE_PATH)
        global RESULT_HISTORY_CACHE
        RESULT_HISTORY_CACHE = None
        return

    history_entries = _load_result_history()
    if history_entries or RESULT_HISTORY_PATH.is_file():
        _write_result_history(history_entries)


def _delete_all_user_data() -> None:
    """Delete retained user-facing runtime data while keeping config and code intact."""
    _purge_runtime_artifacts(delete_all=True)
    _clear_and_reset_ui_state(clear_selected_mode=True)
    _write_state(
        {
            "detail": "All local data deleted. Press button to select the mode.",
            "status": "Ready",
        }
    )


def _load_ui_state() -> dict[str, Any]:
    """Read the shared UI state file used by the touchscreen and button."""
    default_state = _default_ui_state()
    with STATE_LOCK:
        if not UI_STATE_PATH.is_file():
            return default_state

        try:
            raw_state = json.loads(UI_STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            quarantine_file(
                UI_STATE_PATH,
                quarantine_dir=PRIVATE_QUARANTINE_PATH,
                reason="invalid-ui-state",
            )
            return default_state

    selected_mode, selected_mode_internal = _resolve_mode_pair(
        raw_state.get("selected_mode", ""),
        raw_state.get("selected_mode_internal", ""),
    )
    screen = str(raw_state.get("screen", "home"))
    device_state = coerce_device_state(
        raw_state.get("device_state"),
        default=_device_state_for_screen(screen),
    )
    if device_state == DeviceState.READY and selected_mode:
        device_state = DeviceState.MODE_SELECTED
    elif device_state == DeviceState.MODE_SELECTED and not selected_mode:
        device_state = DeviceState.READY
    if screen not in VALID_SCREENS:
        screen = screen_for_device_state(device_state)

    try:
        current_step = int(raw_state.get("current_step", -1))
    except (TypeError, ValueError):
        current_step = -1

    state_defaults = build_ui_state_payload(
        device_state,
        selected_mode=selected_mode,
        ready_detail=READY_DETAIL,
    )

    return {
        "screen": screen,
        "device_state": device_state.value,
        "selected_mode": selected_mode,
        "selected_mode_internal": selected_mode_internal,
        "history_entry_id": str(raw_state.get("history_entry_id", "")).strip(),
        "status": str(raw_state.get("status", state_defaults["status"])),
        "detail": str(raw_state.get("detail", state_defaults["detail"])),
        "answer": str(raw_state.get("answer", "")),
        "error": str(raw_state.get("error", "")),
        "error_detail": str(raw_state.get("error_detail", "")),
        "current_step": current_step,
        "updated_at": str(raw_state.get("updated_at", default_state["updated_at"])),
    }


def _write_state(updates: dict[str, Any]) -> None:
    """Persist the shared device UI state in a small local JSON file."""
    next_state = _load_ui_state()
    next_state.update(updates)
    selected_mode, selected_mode_internal = _resolve_mode_pair(
        next_state.get("selected_mode", ""),
        next_state.get("selected_mode_internal", ""),
    )
    next_state["selected_mode"] = selected_mode
    next_state["selected_mode_internal"] = selected_mode_internal
    device_state = coerce_device_state(
        next_state.get("device_state"),
        default=_device_state_for_screen(str(next_state.get("screen", "home"))),
    )
    if device_state == DeviceState.READY and selected_mode:
        device_state = DeviceState.MODE_SELECTED
    elif device_state == DeviceState.MODE_SELECTED and not selected_mode:
        device_state = DeviceState.READY
    next_state["device_state"] = device_state.value
    next_state["screen"] = screen_for_device_state(device_state)
    next_state["updated_at"] = _timestamp()

    UI_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATE_LOCK:
        atomic_write_json(
            UI_STATE_PATH,
            next_state,
            ensure_ascii=False,
            indent=2,
            trailing_newline=False,
        )
    _apply_led_state(device_state)


def _set_selected_mode(mode: str) -> None:
    """Store the user-selected mode in UI-friendly form."""
    _write_state(_build_idle_state_payload(mode))


def _return_to_mode_selection() -> bool:
    """Return to the mode picker when the device is idle."""
    if _is_running() or is_busy_device_state(_get_device_state()):
        LOGGER.info("Ignoring back request while device is busy")
        return False

    _reset_ui_state(clear_saved_result=False, clear_selected_mode=True)
    LOGGER.info("Returned to mode selection")
    return True


def _reset_ui_state(
    clear_saved_result: bool = False,
    clear_selected_mode: bool = False,
) -> None:
    """Return the device to the startup screen, optionally preserving selection."""
    if clear_selected_mode:
        selected_mode = ""
        selected_mode_internal = ""
    else:
        state = _load_ui_state()
        selected_mode, selected_mode_internal = _resolve_mode_pair(
            state.get("selected_mode"),
            state.get("selected_mode_internal"),
        )
    if clear_saved_result:
        clear_latest_result_file(
            LATEST_RESULT_PATH,
            mode=selected_mode_internal or selected_mode,
        )
    _write_state(_build_idle_state_payload(selected_mode, selected_mode_internal))


def _clear_and_reset_ui_state(clear_selected_mode: bool = False) -> None:
    """Clear the saved result file and return to READY."""
    _reset_ui_state(
        clear_saved_result=True,
        clear_selected_mode=clear_selected_mode,
    )


def _write_device_state(
    device_state: DeviceState | str,
    *,
    selected_mode: str,
    selected_mode_internal: str = "",
    history_entry_id: str = "",
    detail: str | None = None,
    answer: str = "",
    error: str = "",
    error_detail: str = "",
    current_step: int | None = None,
    status: str | None = None,
) -> None:
    """Persist the shared device lifecycle state to the UI state file."""
    ui_mode, internal_mode = _resolve_mode_pair(
        selected_mode,
        selected_mode_internal,
    )
    payload = build_ui_state_payload(
        device_state,
        selected_mode=ui_mode,
        ready_detail=READY_DETAIL,
        detail=detail,
        answer=answer,
        error=error,
        error_detail=error_detail,
        current_step=current_step,
        status=status,
    )
    payload["selected_mode_internal"] = internal_mode
    payload["history_entry_id"] = str(history_entry_id).strip()
    _write_state(payload)


def _get_device_state() -> DeviceState:
    """Return the current persisted device lifecycle state."""
    return coerce_device_state(_load_ui_state().get("device_state"))


def _device_state_for_screen(screen: str) -> DeviceState:
    """Infer a lifecycle state from an older persisted screen value."""
    return {
        "home": DeviceState.READY,
        "processing": DeviceState.PROCESSING,
        "result": DeviceState.DONE,
        "error": DeviceState.ERROR,
    }.get(screen, DeviceState.READY)


def _apply_led_state(device_state: DeviceState | str) -> None:
    """Mirror the persisted device state to the optional GPIO LED."""
    LED_INDICATOR.set_state(device_state)


def _is_running() -> bool:
    """Return True when a background capture is already in progress."""
    with RUN_LOCK:
        return RUNNING


def _bootstrap_ui_state() -> None:
    """Return the device to the startup screen after an app restart."""
    state = _load_ui_state()
    LOGGER.info(
        "Resetting UI state on startup previous_screen=%s previous_state=%s",
        state.get("screen"),
        state.get("device_state"),
    )
    _reset_ui_state(clear_selected_mode=True)


def _select_mode_from_hardware(mode: str) -> bool:
    """Apply a physical mode-button press to the persisted UI state."""
    if _is_running() or is_busy_device_state(_get_device_state()):
        LOGGER.info("Ignoring physical mode selection while device is busy mode=%s", mode)
        return False

    _set_selected_mode(mode)
    LOGGER.info("Physical mode selected mode=%s", mode)
    return True


def _ensure_gpio_button_listener_started() -> None:
    """Start the optional GPIO listener so the physical button mirrors touch capture."""
    global GPIO_START_ATTEMPTED, GPIO_TRIGGER

    if not ENABLE_GPIO_BUTTON or not _setup_is_complete() or GPIO_TRIGGER is not None:
        return

    with GPIO_START_LOCK:
        if not ENABLE_GPIO_BUTTON or not _setup_is_complete() or GPIO_TRIGGER is not None:
            return

        GPIO_START_ATTEMPTED = True
        try:
            configured_mode_buttons = {
                mode: pin for mode, pin in MODE_BUTTON_PINS.items() if pin is not None
            }
            GPIO_TRIGGER = GPIOButtonTrigger(
                pin=CAPTURE_BUTTON_PIN,
                debounce_seconds=GPIO_BUTTON_DEBOUNCE_SECONDS,
                hold_seconds=GPIO_BUTTON_HOLD_SECONDS,
                back_button_pin=BACK_BUTTON_PIN,
                mode_buttons=configured_mode_buttons,
                mode_action=_select_mode_from_hardware,
                trigger_action=_start_capture_job,
                back_action=_return_to_mode_selection,
                clear_action=lambda: _clear_and_reset_ui_state(clear_selected_mode=True) or True,
                get_device_state=_get_device_state,
            )
            GPIO_TRIGGER.start()
            LOGGER.info(
                "GPIO controls started capture_pin=%s mode_pins=%s back_pin=%s",
                CAPTURE_BUTTON_PIN,
                configured_mode_buttons,
                BACK_BUTTON_PIN,
            )
        except GPIOButtonError as exc:
            GPIO_TRIGGER = None
            LOGGER.warning("GPIO button listener disabled: %s", exc)


def _initialize_led_indicator() -> None:
    """Log LED startup issues and apply the current persisted state."""
    if ENABLE_GPIO_LED and LED_INDICATOR.disabled_reason:
        LOGGER.warning("GPIO LED disabled: %s", LED_INDICATOR.disabled_reason)
    _apply_led_state(_get_device_state())


def _health_monitor_busy() -> bool:
    """Return True when the device should defer intrusive health checks."""
    preview_active = False
    preview_service = LIVE_PREVIEW
    if hasattr(preview_service, "is_camera_active"):
        try:
            preview_active = bool(preview_service.is_camera_active())
        except Exception:
            preview_active = False
    return _is_running() or is_busy_device_state(_get_device_state()) or preview_active


def _is_live_preview_screen() -> bool:
    """Return True when the home screen is showing the live preview panel."""
    state = _load_ui_state()
    screen = str(state.get("screen", "")).strip().lower()
    selected_mode = str(state.get("selected_mode", "")).strip()
    return screen == "home" and bool(selected_mode)


def _ensure_health_monitor_started() -> None:
    """Start the optional background health monitor once during app startup."""
    global HEALTH_MONITOR

    if (
        not _setup_is_complete()
        or not SETTINGS.reliability.health_monitor_enabled
        or HEALTH_MONITOR is not None
    ):
        return

    HEALTH_MONITOR = HealthMonitor(
        settings=SETTINGS,
        is_busy=_health_monitor_busy,
    )
    if HEALTH_MONITOR.start():
        LOGGER.info("Health monitor started")


def _ensure_offline_retry_started() -> None:
    """Start the background offline retry worker when the feature is enabled."""
    queue = OFFLINE_RETRY_QUEUE
    if queue is None or not _setup_is_complete():
        return

    started = queue.start(
        analyze_func=_analyze_offline_retry_entry,
        success_callback=_record_offline_retry_success,
        failure_callback=_record_offline_retry_failure,
    )
    if started:
        LOGGER.info(
            "Offline retry queue started pending=%s poll_interval_seconds=%s",
            queue.pending_count(),
            SETTINGS.offline_retry.poll_interval_seconds,
        )


PRIVATE_DATA_PATH.mkdir(parents=True, exist_ok=True)
PRIVATE_QUARANTINE_PATH.mkdir(parents=True, exist_ok=True)
if PURGE_ON_STARTUP:
    _purge_runtime_artifacts(delete_all=False)
_bootstrap_ui_state()
_initialize_led_indicator()
_ensure_gpio_button_listener_started()
_ensure_health_monitor_started()
_ensure_offline_retry_started()
LOGGER.info("Flask app startup complete")


if __name__ == "__main__":
    app.run(host=APP_HOST, port=APP_PORT, debug=FLASK_DEBUG)
