"""Touchscreen-first Flask UI for the Raspberry Pi AI Vision Desk Assistant."""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, Response, redirect, render_template, request, url_for
from markupsafe import Markup, escape

from ai.modes import get_mode, normalize_mode
from camera.live_preview import LivePreviewService
from config import SettingsError, load_device_settings
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
from pipeline import PipelineError, PipelineResult, run_capture_analyze, save_latest_result
from system import HealthMonitor, configure_logging

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
LATEST_RESULT_PATH = Path("data/latest_result.txt")
CAPTURED_IMAGE_PATH = Path("static/captured.jpg")
PROCESSED_IMAGE_PATH = Path("static/processed.jpg")
VALID_SCREENS = {"home", "processing", "result", "error"}
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
RUN_LOCK = threading.Lock()
GPIO_START_LOCK = threading.Lock()
RUNNING = False
GPIO_START_ATTEMPTED = False
GPIO_TRIGGER: GPIOButtonTrigger | None = None
HEALTH_MONITOR: HealthMonitor | None = None


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
ENABLE_GPIO_LED = SETTINGS.led.enabled
GPIO_LED_PIN = SETTINGS.led.pin
GPIO_LED_ACTIVE_HIGH = SETTINGS.led.active_high
UI_DEBUG = _read_bool_env("UI_DEBUG", False)

UI_BASE_FONT_SIZE = _read_int_env("UI_BASE_FONT_SIZE", 20, minimum=16, maximum=42)
UI_TITLE_FONT_SIZE = _read_int_env("UI_TITLE_FONT_SIZE", 34, minimum=24, maximum=72)
UI_STATUS_FONT_SIZE = _read_int_env("UI_STATUS_FONT_SIZE", 28, minimum=20, maximum=64)
UI_BUTTON_FONT_SIZE = _read_int_env("UI_BUTTON_FONT_SIZE", 24, minimum=18, maximum=42)
UI_TOUCH_TARGET = _read_int_env("UI_TOUCH_TARGET", 68, minimum=52, maximum=96)
UI_DISPLAY_ORIENTATION = _read_orientation_env(
    "UI_DISPLAY_ORIENTATION",
    "landscape",
)
LIVE_PREVIEW_REFRESH_MS = 250
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
DEFAULT_CAPTURE_MODE = "solve_problem"
DEFAULT_CAPTURE_INTERNAL_MODE = UI_MODE_TO_INTERNAL_MODE[DEFAULT_CAPTURE_MODE]
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
    autofocus_mode=CAMERA_AUTOFOCUS_MODE,
    exposure=CAMERA_EXPOSURE,
    brightness=CAMERA_BRIGHTNESS,
)


@app.get("/")
def index():
    """Render the current device screen."""
    return render_template("index.html", **_build_template_context())


@app.get("/camera/live-frame.jpg")
def live_preview_frame():
    """Return the latest live camera frame for the touchscreen preview."""
    frame_bytes = LIVE_PREVIEW.get_jpeg_frame()
    return Response(
        frame_bytes,
        mimetype="image/jpeg",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


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


@app.post("/back")
def back():
    """Return to the startup ready screen."""
    _reset_ui_state(clear_saved_result=False, clear_selected_mode=True)
    return redirect(url_for("index"))


@app.post("/clear")
def clear():
    """Clear the saved result/error and return to the ready screen."""
    _clear_and_reset_ui_state(clear_selected_mode=True)
    return redirect(url_for("index"))


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
    return payload


def _build_live_preview_url() -> str:
    """Return the cache-busted live preview endpoint for the UI."""
    return f"{url_for('live_preview_frame')}?t={int(datetime.now().timestamp() * 1000)}"


def _build_template_context(screen_override: str | None = None) -> dict[str, Any]:
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
    display_status = state["status"]
    if screen == "processing":
        display_status = state["detail"] or "Processing..."
    elif screen == "result":
        display_status = "Done"

    active_mode_definition = None
    if selected_mode_internal:
        active_mode_definition = get_mode(selected_mode_internal)

    return {
        "screen": screen,
        "status": state["status"],
        "display_status": display_status,
        "detail": state["detail"],
        "error": state["error"],
        "error_detail": state["error_detail"],
        "answer_html": _format_answer_html(state["answer"]),
        "selected_mode": selected_mode,
        "selected_mode_internal": selected_mode_internal,
        "selected_mode_label": selected_mode_label,
        "selected_mode_description": selected_mode_description,
        "active_mode_name": active_mode_definition.name if active_mode_definition else "",
        "has_mode_selected": bool(selected_mode),
        "mode_options": UI_MODE_OPTIONS,
        "progress_steps": _build_progress_steps(state["current_step"]),
        "live_preview_url": _build_live_preview_url(),
        "live_preview_refresh_ms": LIVE_PREVIEW_REFRESH_MS,
        "default_capture_mode_label": MODE_LABELS[DEFAULT_CAPTURE_MODE],
        "auto_refresh_ms": _get_auto_refresh_ms(screen),
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
    LIVE_PREVIEW.pause()
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


def _run_capture_job(selected_mode: str, selected_mode_internal: str) -> None:
    """Run the capture pipeline in the background and persist screen state."""
    global RUNNING

    try:
        result = run_capture_analyze(
            mode=selected_mode_internal,
            backend=CAMERA_BACKEND,
            camera_index=CAMERA_INDEX,
            width=CAPTURE_WIDTH,
            height=CAPTURE_HEIGHT,
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
        _write_device_state(
            DeviceState.DONE,
            selected_mode=selected_mode,
            selected_mode_internal=selected_mode_internal,
            detail="Done",
            answer=result.answer or "",
            current_step=len(PROGRESS_STEPS),
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
        LIVE_PREVIEW.resume()
        with RUN_LOCK:
            RUNNING = False


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
    if any(token in normalized for token in ("camera", "picamera2", "opencv")):
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


def _load_ui_state() -> dict[str, Any]:
    """Read the shared UI state file used by the touchscreen and button."""
    default_state = _default_ui_state()
    with STATE_LOCK:
        if not UI_STATE_PATH.is_file():
            return default_state

        try:
            raw_state = json.loads(UI_STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
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
        UI_STATE_PATH.write_text(
            json.dumps(next_state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    _apply_led_state(device_state)


def _set_selected_mode(mode: str) -> None:
    """Store the user-selected mode in UI-friendly form."""
    _write_state(_build_idle_state_payload(mode))


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
    detail: str | None = None,
    answer: str = "",
    error: str = "",
    error_detail: str = "",
    current_step: int | None = None,
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
    )
    payload["selected_mode_internal"] = internal_mode
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

    if not ENABLE_GPIO_BUTTON or GPIO_START_ATTEMPTED:
        return

    with GPIO_START_LOCK:
        if not ENABLE_GPIO_BUTTON or GPIO_START_ATTEMPTED:
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
                mode_buttons=configured_mode_buttons,
                mode_action=_select_mode_from_hardware,
                trigger_action=_start_capture_job,
                clear_action=lambda: _clear_and_reset_ui_state(clear_selected_mode=True) or True,
                get_device_state=_get_device_state,
            )
            GPIO_TRIGGER.start()
            LOGGER.info(
                "GPIO controls started capture_pin=%s mode_pins=%s",
                CAPTURE_BUTTON_PIN,
                configured_mode_buttons,
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
    return _is_running() or is_busy_device_state(_get_device_state())


def _ensure_health_monitor_started() -> None:
    """Start the optional background health monitor once during app startup."""
    global HEALTH_MONITOR

    if not SETTINGS.reliability.health_monitor_enabled or HEALTH_MONITOR is not None:
        return

    HEALTH_MONITOR = HealthMonitor(
        settings=SETTINGS,
        is_busy=_health_monitor_busy,
    )
    if HEALTH_MONITOR.start():
        LOGGER.info("Health monitor started")


_bootstrap_ui_state()
_initialize_led_indicator()
_ensure_gpio_button_listener_started()
_ensure_health_monitor_started()
LOGGER.info("Flask app startup complete")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
