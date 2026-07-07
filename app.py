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
from gpio import GPIOButtonError, GPIOButtonTrigger
from pipeline import PipelineError, PipelineResult, run_capture_analyze, save_latest_result

load_dotenv()

app = Flask(__name__)

UI_STATE_PATH = Path("data/ui_state.json")
LATEST_RESULT_PATH = Path("data/latest_result.txt")
DEFAULT_MODE = "read_text"
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


CAMERA_BACKEND = os.getenv("VISION_CAMERA_BACKEND", "auto").strip().lower() or "auto"
CAMERA_INDEX = _read_int_env("VISION_CAMERA_INDEX", 0, minimum=0)
CAPTURE_WIDTH = _read_int_env("VISION_CAPTURE_WIDTH", 1280, minimum=320)
CAPTURE_HEIGHT = _read_int_env("VISION_CAPTURE_HEIGHT", 720, minimum=240)
GRAYSCALE = _read_bool_env("VISION_GRAYSCALE", False)
MAX_DIMENSION = _read_int_env("VISION_MAX_DIMENSION", 1600, minimum=640)
ENABLE_GPIO_BUTTON = _read_bool_env("ENABLE_GPIO_BUTTON", True)
GPIO_BUTTON_PIN = _read_int_env("GPIO_BUTTON_PIN", 17, minimum=0)
UI_DEBUG = _read_bool_env("UI_DEBUG", False)

UI_SCREEN_WIDTH = _read_int_env("UI_SCREEN_WIDTH", 320, minimum=240, maximum=1920)
UI_SCREEN_HEIGHT = _read_int_env("UI_SCREEN_HEIGHT", 480, minimum=240, maximum=1920)
UI_BASE_FONT_SIZE = _read_int_env("UI_BASE_FONT_SIZE", 20, minimum=16, maximum=42)
UI_TITLE_FONT_SIZE = _read_int_env("UI_TITLE_FONT_SIZE", 34, minimum=24, maximum=72)
UI_STATUS_FONT_SIZE = _read_int_env("UI_STATUS_FONT_SIZE", 28, minimum=20, maximum=64)
UI_BUTTON_FONT_SIZE = _read_int_env("UI_BUTTON_FONT_SIZE", 24, minimum=18, maximum=42)
UI_TOUCH_TARGET = _read_int_env("UI_TOUCH_TARGET", 68, minimum=52, maximum=96)
UI_DISPLAY_ORIENTATION = _read_orientation_env("UI_DISPLAY_ORIENTATION", "portrait")
UI_PROCESSING_REFRESH_MS = _read_int_env("UI_PROCESSING_REFRESH_MS", 1200, minimum=500, maximum=5000)
UI_IDLE_REFRESH_MS = _read_int_env("UI_IDLE_REFRESH_MS", 2500, minimum=1000, maximum=10000)


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
@app.post("/clear")
def back():
    """Return to the ready screen while preserving the selected mode."""
    _reset_ui_state()
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
    _write_state(
        {
            "screen": "processing",
            "selected_mode": selected_mode,
            "status": "Capturing",
            "detail": PROGRESS_STEPS[0],
            "answer": "",
            "error": "",
            "error_detail": "",
            "current_step": 0,
        }
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
            status_callback=lambda message: _update_processing_state(selected_mode, message),
        )
        _write_state(
            {
                "screen": "processing",
                "selected_mode": selected_mode,
                "status": "Processing",
                "detail": PROGRESS_STEPS[3],
                "answer": "",
                "error": "",
                "error_detail": "",
                "current_step": 3,
            }
        )
        save_latest_result(result, output_path=str(LATEST_RESULT_PATH))
        _write_state(
            {
                "screen": "result",
                "selected_mode": selected_mode,
                "status": "Done",
                "detail": "Answer ready",
                "answer": result.answer or "",
                "error": "",
                "error_detail": "",
                "current_step": len(PROGRESS_STEPS),
            }
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
    status = "Capturing" if step_index == 0 else "Processing"
    detail = PROGRESS_STEPS[step_index]
    _write_state(
        {
            "screen": "processing",
            "selected_mode": selected_mode,
            "status": status,
            "detail": detail,
            "answer": "",
            "error": "",
            "error_detail": "",
            "current_step": step_index,
        }
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
        status="error",
    )
    save_latest_result(failure_result, output_path=str(LATEST_RESULT_PATH))
    _write_state(
        {
            "screen": "error",
            "selected_mode": selected_mode,
            "status": "Error",
            "detail": "Try again when ready",
            "answer": "",
            "error": friendly_error,
            "error_detail": error_message,
            "current_step": -1,
        }
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
    if screen == "home" and GPIO_TRIGGER is not None:
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
    return {
        "screen": "home",
        "selected_mode": DEFAULT_MODE,
        "status": "Ready",
        "detail": "Tap Capture or press the button",
        "answer": "",
        "error": "",
        "error_detail": "",
        "current_step": -1,
        "updated_at": _timestamp(),
    }


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
    if screen not in VALID_SCREENS:
        screen = "home"

    try:
        current_step = int(raw_state.get("current_step", -1))
    except (TypeError, ValueError):
        current_step = -1

    return {
        "screen": screen,
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
    next_state["screen"] = (
        next_state["screen"] if str(next_state.get("screen")) in VALID_SCREENS else "home"
    )
    next_state["updated_at"] = _timestamp()

    UI_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATE_LOCK:
        UI_STATE_PATH.write_text(
            json.dumps(next_state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _set_selected_mode(mode: str) -> None:
    """Store the user-selected mode in UI-friendly form."""
    _write_state({"selected_mode": _to_ui_mode(mode)})


def _reset_ui_state() -> None:
    """Return the device to the home screen without changing the chosen mode."""
    selected_mode = _load_ui_state()["selected_mode"]
    ready_state = _default_ui_state()
    ready_state["selected_mode"] = selected_mode
    _write_state(ready_state)


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
    if state["screen"] == "processing":
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
                trigger_action=_start_capture_job,
            )
            GPIO_TRIGGER.start()
            app.logger.info("GPIO button listener started on pin %s", GPIO_BUTTON_PIN)
        except GPIOButtonError as exc:
            GPIO_TRIGGER = None
            app.logger.warning("GPIO button listener disabled: %s", exc)


_bootstrap_ui_state()
_ensure_gpio_button_listener_started()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
