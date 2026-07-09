"""Touchscreen-first Flask UI for the Raspberry Pi AI Vision Desk Assistant."""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for
from markupsafe import Markup, escape

from ai.prompts import normalize_mode
from config import SettingsError, load_device_settings
from hardware import (
    DeviceState,
    GPIOButtonError,
    GPIOButtonTrigger,
    LEDIndicator,
    build_ready_state_payload,
    build_ui_state_payload,
    clear_latest_result_file,
    coerce_device_state,
    screen_for_device_state,
)
from pipeline import PipelineError, PipelineResult, run_capture_analyze, save_latest_result

load_dotenv()

try:
    SETTINGS = load_device_settings()
except SettingsError as exc:
    raise RuntimeError(f"Invalid device settings: {exc}") from exc

app = Flask(__name__)

UI_STATE_PATH = Path("data/ui_state.json")
LATEST_RESULT_PATH = Path("data/latest_result.txt")
VALID_SCREENS = {"home", "processing", "result", "error"}
UI_MODE_OPTIONS = [
    ("read_text", "Read Text"),
    ("summarize", "Summarize Document"),
    ("solve_problem", "Solve Problem"),
    ("analyze_image", "Analyze Image"),
    ("professional_assistant", "Professional Assistant"),
]
MODE_LABELS = dict(UI_MODE_OPTIONS)
PROGRESS_STEPS = [
    "Capturing image",
    "Reading text",
    "Analyzing with AI",
    "Preparing answer",
]

STATE_LOCK = threading.Lock()
RUN_LOCK = threading.Lock()
GPIO_START_LOCK = threading.Lock()
RUNNING = False
GPIO_START_ATTEMPTED = False
GPIO_TRIGGER: GPIOButtonTrigger | None = None


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
GPIO_BUTTON_PIN = SETTINGS.button.pin
GPIO_BUTTON_DEBOUNCE_SECONDS = SETTINGS.button.debounce_seconds
GPIO_BUTTON_HOLD_SECONDS = SETTINGS.button.hold_seconds
ENABLE_GPIO_LED = SETTINGS.led.enabled
GPIO_LED_PIN = SETTINGS.led.pin
GPIO_LED_ACTIVE_HIGH = SETTINGS.led.active_high
UI_DEBUG = _read_bool_env("UI_DEBUG", False)

UI_SCREEN_WIDTH = max(240, min(1920, SETTINGS.display.size.width))
UI_SCREEN_HEIGHT = max(240, min(1920, SETTINGS.display.size.height))
UI_BASE_FONT_SIZE = _read_int_env("UI_BASE_FONT_SIZE", 20, minimum=16, maximum=42)
UI_TITLE_FONT_SIZE = _read_int_env("UI_TITLE_FONT_SIZE", 34, minimum=24, maximum=72)
UI_STATUS_FONT_SIZE = _read_int_env("UI_STATUS_FONT_SIZE", 28, minimum=20, maximum=64)
UI_BUTTON_FONT_SIZE = _read_int_env("UI_BUTTON_FONT_SIZE", 24, minimum=18, maximum=42)
UI_TOUCH_TARGET = _read_int_env("UI_TOUCH_TARGET", 68, minimum=52, maximum=96)
UI_DISPLAY_ORIENTATION = _read_orientation_env(
    "UI_DISPLAY_ORIENTATION",
    SETTINGS.display.orientation,
)
UI_PROCESSING_REFRESH_MS = _read_int_env("UI_PROCESSING_REFRESH_MS", 1200, minimum=500, maximum=5000)
UI_IDLE_REFRESH_MS = _read_int_env("UI_IDLE_REFRESH_MS", 2500, minimum=1000, maximum=10000)
DEFAULT_MODE = normalize_mode(SETTINGS.ai.default_mode)
if DEFAULT_MODE == "summarize_document":
    DEFAULT_MODE = "summarize"
if DEFAULT_MODE not in dict(UI_MODE_OPTIONS):
    DEFAULT_MODE = "read_text"
READY_DETAIL = "Tap Capture or press the button" if ENABLE_GPIO_BUTTON else "Tap Capture to begin"
HARDWARE_IDLE_SCREENS = {"home", "result", "error"}

LED_INDICATOR = LEDIndicator.create(
    pin=GPIO_LED_PIN,
    enabled=ENABLE_GPIO_LED,
    active_high=GPIO_LED_ACTIVE_HIGH,
)


@app.get("/")
def index():
    """Render the current device screen."""
    return render_template("index.html", **_build_template_context())


@app.get("/mode")
def mode_select():
    """Render the simple mode selection screen."""
    if _is_running():
        return redirect(url_for("index"))
    return render_template("index.html", **_build_template_context(screen_override="mode_select"))


@app.post("/mode/select")
def select_mode():
    """Persist a touch-friendly mode selection and return home."""
    if _is_running():
        return redirect(url_for("index"))

    requested_mode = request.form.get("mode", DEFAULT_MODE)
    _set_selected_mode(requested_mode)
    _reset_ui_state()
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
    """Return to the ready screen while preserving the selected mode."""
    _reset_ui_state(clear_saved_result=False)
    return redirect(url_for("index"))


@app.post("/clear")
def clear():
    """Clear the saved result/error and return to the ready screen."""
    _clear_and_reset_ui_state()
    return redirect(url_for("index"))


def _build_template_context(screen_override: str | None = None) -> dict[str, Any]:
    """Build the render context for the current screen."""
    state = _load_ui_state()
    screen = screen_override or state["screen"]
    if screen not in VALID_SCREENS and screen != "mode_select":
        screen = "home"

    selected_mode = _to_ui_mode(state["selected_mode"])
    selected_mode_label = MODE_LABELS.get(selected_mode, MODE_LABELS[DEFAULT_MODE])

    return {
        "screen": screen,
        "status": state["status"],
        "detail": state["detail"],
        "error": state["error"],
        "error_detail": state["error_detail"],
        "answer_html": _format_answer_html(state["answer"]),
        "selected_mode": selected_mode,
        "selected_mode_label": selected_mode_label,
        "mode_options": UI_MODE_OPTIONS,
        "progress_steps": _build_progress_steps(state["current_step"]),
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
            return False
        RUNNING = True

    selected_mode = _load_ui_state()["selected_mode"]
    _write_device_state(
        DeviceState.CAPTURING,
        selected_mode=selected_mode,
        detail=PROGRESS_STEPS[0],
        current_step=0,
    )

    worker = threading.Thread(
        target=_run_capture_job,
        args=(selected_mode,),
        daemon=True,
        name="touch-capture-worker",
    )
    worker.start()
    return True


def _run_capture_job(selected_mode: str) -> None:
    """Run the capture pipeline in the background and persist screen state."""
    global RUNNING

    try:
        result = run_capture_analyze(
            mode=normalize_mode(selected_mode),
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
            status_callback=lambda message: _update_processing_state(selected_mode, message),
        )
        _write_device_state(
            DeviceState.PROCESSING,
            selected_mode=selected_mode,
            detail=PROGRESS_STEPS[3],
            current_step=3,
        )
        save_latest_result(result, output_path=str(LATEST_RESULT_PATH))
        _write_device_state(
            DeviceState.DONE,
            selected_mode=selected_mode,
            detail="Answer ready",
            answer=result.answer or "",
            current_step=len(PROGRESS_STEPS),
        )
    except (PipelineError, ValueError) as exc:
        _record_error_state(selected_mode, str(exc))
    except Exception as exc:
        _record_error_state(selected_mode, f"Unexpected error: {exc}")
    finally:
        with RUN_LOCK:
            RUNNING = False


def _update_processing_state(selected_mode: str, pipeline_message: str) -> None:
    """Translate shared pipeline updates into small-screen UI text."""
    step_index = _step_index_for_message(pipeline_message)
    detail = PROGRESS_STEPS[step_index]
    _write_device_state(
        DeviceState.CAPTURING if step_index == 0 else DeviceState.PROCESSING,
        selected_mode=selected_mode,
        detail=detail,
        current_step=step_index,
    )


def _record_error_state(selected_mode: str, error_message: str) -> None:
    """Persist a short, readable error state for the touchscreen."""
    friendly_error = _humanize_error(error_message)
    failure_result = PipelineResult(
        captured_path=None,
        processed_path=None,
        answer=error_message,
        mode=normalize_mode(selected_mode),
        camera_backend_used=CAMERA_BACKEND,
        camera_resolution=None,
        status="error",
    )
    save_latest_result(failure_result, output_path=str(LATEST_RESULT_PATH))
    _write_device_state(
        DeviceState.ERROR,
        selected_mode=selected_mode,
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
        return "Camera not found"
    if "could not connect to openai" in normalized or "internet connection" in normalized:
        return "Network unavailable"
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
    default_state = build_ready_state_payload(
        selected_mode=DEFAULT_MODE,
        ready_detail=READY_DETAIL,
    )
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

    selected_mode = _to_ui_mode(str(raw_state.get("selected_mode", DEFAULT_MODE)))
    screen = str(raw_state.get("screen", "home"))
    device_state = coerce_device_state(
        raw_state.get("device_state"),
        default=_device_state_for_screen(screen),
    )
    if screen not in VALID_SCREENS:
        screen = screen_for_device_state(device_state)

    try:
        current_step = int(raw_state.get("current_step", -1))
    except (TypeError, ValueError):
        current_step = -1

    return {
        "screen": screen,
        "device_state": device_state.value,
        "selected_mode": selected_mode,
        "status": str(raw_state.get("status", default_state["status"])),
        "detail": str(raw_state.get("detail", default_state["detail"])),
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
    next_state["selected_mode"] = _to_ui_mode(str(next_state.get("selected_mode", DEFAULT_MODE)))
    device_state = coerce_device_state(
        next_state.get("device_state"),
        default=_device_state_for_screen(str(next_state.get("screen", "home"))),
    )
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
    _write_state({"selected_mode": _to_ui_mode(mode)})


def _reset_ui_state(clear_saved_result: bool = False) -> None:
    """Return the device to the home screen without changing the chosen mode."""
    selected_mode = _load_ui_state()["selected_mode"]
    if clear_saved_result:
        clear_latest_result_file(LATEST_RESULT_PATH, mode=selected_mode)
    _write_state(
        build_ready_state_payload(
            selected_mode=selected_mode,
            ready_detail=READY_DETAIL,
        )
    )


def _clear_and_reset_ui_state() -> None:
    """Clear the saved result file and return to READY."""
    _reset_ui_state(clear_saved_result=True)


def _write_device_state(
    device_state: DeviceState | str,
    *,
    selected_mode: str,
    detail: str | None = None,
    answer: str = "",
    error: str = "",
    error_detail: str = "",
    current_step: int | None = None,
) -> None:
    """Persist the shared device lifecycle state to the UI state file."""
    _write_state(
        build_ui_state_payload(
            device_state,
            selected_mode=_to_ui_mode(selected_mode),
            ready_detail=READY_DETAIL,
            detail=detail,
            answer=answer,
            error=error,
            error_detail=error_detail,
            current_step=current_step,
        )
    )


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


def _to_ui_mode(mode: str) -> str:
    """Normalize internal mode names into the simplified UI values."""
    normalized = normalize_mode(mode)
    if normalized == "summarize_document":
        return "summarize"
    if normalized not in MODE_LABELS:
        return DEFAULT_MODE
    return normalized


def _is_running() -> bool:
    """Return True when a background capture is already in progress."""
    with RUN_LOCK:
        return RUNNING


def _bootstrap_ui_state() -> None:
    """Repair stale processing state after a restart."""
    state = _load_ui_state()
    if _get_device_state() in {DeviceState.CAPTURING, DeviceState.PROCESSING}:
        _reset_ui_state()


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
            GPIO_TRIGGER = GPIOButtonTrigger(
                pin=GPIO_BUTTON_PIN,
                debounce_seconds=GPIO_BUTTON_DEBOUNCE_SECONDS,
                hold_seconds=GPIO_BUTTON_HOLD_SECONDS,
                trigger_action=_start_capture_job,
                clear_action=lambda: _clear_and_reset_ui_state() or True,
                get_device_state=_get_device_state,
            )
            GPIO_TRIGGER.start()
            app.logger.info("GPIO button listener started on pin %s", GPIO_BUTTON_PIN)
        except GPIOButtonError as exc:
            GPIO_TRIGGER = None
            app.logger.warning("GPIO button listener disabled: %s", exc)


def _initialize_led_indicator() -> None:
    """Log LED startup issues and apply the current persisted state."""
    if ENABLE_GPIO_LED and LED_INDICATOR.disabled_reason:
        app.logger.warning("GPIO LED disabled: %s", LED_INDICATOR.disabled_reason)
    _apply_led_state(_get_device_state())


_bootstrap_ui_state()
_initialize_led_indicator()
_ensure_gpio_button_listener_started()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
