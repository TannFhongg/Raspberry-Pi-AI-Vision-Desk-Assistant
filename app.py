"""Flask web dashboard for the Raspberry Pi AI Vision Desk Assistant."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for

from ai.prompts import normalize_mode
from pipeline import (
    PipelineError,
    file_exists,
    is_processed_fresh,
    run_analyze,
    run_capture,
    run_capture_analyze,
)

load_dotenv()

app = Flask(__name__)
# Development fallback only. Set FLASK_SECRET_KEY in .env or the shell for real deployments.
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")

CAPTURED_IMAGE_PATH = Path("static/captured.jpg")
PROCESSED_IMAGE_PATH = Path("static/processed.jpg")
WEB_FEEDBACK_PATH = Path("data/web_feedback.json")
DEFAULT_MODE = "read_text"
UI_MODE_OPTIONS = [
    ("read_text", "Read Text"),
    ("summarize", "Summarize Document"),
    ("solve_problem", "Solve Problem"),
    ("professional_assistant", "Professional Assistant"),
]


@app.get("/")
def index():
    """Render the dashboard with the latest session and image state."""
    _cleanup_legacy_session_fields()
    selected_mode = _get_selected_mode_from_session()
    feedback_state = _load_feedback_state()
    captured_exists = file_exists(CAPTURED_IMAGE_PATH)
    processed_exists = file_exists(PROCESSED_IMAGE_PATH)
    processed_fresh = is_processed_fresh(CAPTURED_IMAGE_PATH, PROCESSED_IMAGE_PATH)

    captured_url = _build_image_url("captured.jpg", CAPTURED_IMAGE_PATH) if captured_exists else None
    processed_url = (
        _build_image_url("processed.jpg", PROCESSED_IMAGE_PATH)
        if processed_exists and processed_fresh
        else None
    )
    processed_note = None
    if processed_exists and not processed_fresh:
        processed_note = (
            "Processed image is outdated. Click Analyze Image or Capture + Analyze "
            "to generate a new processed image."
        )

    return render_template(
        "index.html",
        mode_options=UI_MODE_OPTIONS,
        selected_mode=selected_mode,
        status=feedback_state["status"],
        error=feedback_state["error"],
        answer=feedback_state["answer"],
        captured_exists=captured_exists,
        captured_url=captured_url,
        processed_exists=processed_exists,
        processed_url=processed_url,
        processed_note=processed_note,
    )


@app.post("/capture")
def capture():
    """Capture a new image and return to the dashboard."""
    try:
        selected_mode = _store_selected_mode_from_request()
        _set_feedback(answer="")
        result = run_capture(backend="auto", camera_index=0)
        _set_feedback(
            status=f"Image captured successfully. Camera backend used: {result.camera_backend_used}",
            error="",
        )
        session["selected_mode"] = _to_ui_mode(selected_mode)
    except (PipelineError, ValueError) as exc:
        _set_feedback(error=str(exc), status="")
    except Exception as exc:
        _set_feedback(error=f"Unexpected error: {exc}", status="")

    return redirect(url_for("index"))


@app.post("/analyze")
def analyze():
    """Analyze the latest available image, auto-preprocessing when needed."""
    try:
        selected_mode = _store_selected_mode_from_request()
        _set_feedback(answer="")
        status_prefix = ""
        if file_exists(CAPTURED_IMAGE_PATH) and not is_processed_fresh(
            CAPTURED_IMAGE_PATH, PROCESSED_IMAGE_PATH
        ):
            status_prefix = "Preprocessing latest captured image..."
        result = run_analyze(mode=selected_mode, grayscale=False, max_dimension=1600)
        status_message = "Analyzing processed image... Answer received."
        if status_prefix:
            status_message = f"{status_prefix} {status_message}"
        _set_feedback(
            status=status_message,
            answer=result.answer,
            error="",
        )
    except (PipelineError, ValueError) as exc:
        _set_feedback(error=str(exc), status="")
    except Exception as exc:
        _set_feedback(error=f"Unexpected error: {exc}", status="")

    return redirect(url_for("index"))


@app.post("/capture-analyze")
def capture_analyze():
    """Capture, preprocess, and analyze a fresh image in one action."""
    try:
        selected_mode = _store_selected_mode_from_request()
        _set_feedback(answer="")
        result = run_capture_analyze(
            mode=selected_mode,
            backend="auto",
            camera_index=0,
            grayscale=False,
            max_dimension=1600,
        )
        _set_feedback(
            status=(
                f"Image captured successfully. Camera backend used: {result.camera_backend_used}. "
                "Preprocessing image... Analyzing processed image... Answer received."
            ),
            answer=result.answer,
            error="",
        )
    except (PipelineError, ValueError) as exc:
        _set_feedback(error=str(exc), status="")
    except Exception as exc:
        _set_feedback(error=f"Unexpected error: {exc}", status="")

    return redirect(url_for("index"))


@app.post("/clear")
def clear():
    """Clear text state while preserving images and selected mode."""
    selected_mode = _get_selected_mode_from_session()
    session["selected_mode"] = selected_mode
    _clear_feedback_state()
    return redirect(url_for("index"))


def _store_selected_mode_from_request() -> str:
    """Validate the submitted mode, store it in session, and return the canonical mode."""
    _cleanup_legacy_session_fields()
    requested_mode = request.form.get("mode", DEFAULT_MODE).strip().lower()
    valid_modes = {mode for mode, _ in UI_MODE_OPTIONS} | {"summarize_document"}
    if requested_mode not in valid_modes:
        valid_display_modes = ", ".join(mode for mode, _ in UI_MODE_OPTIONS)
        raise ValueError(f"Invalid mode '{requested_mode}'. Use one of: {valid_display_modes}")

    canonical_mode = normalize_mode(requested_mode)
    session["selected_mode"] = _to_ui_mode(canonical_mode)
    return canonical_mode


def _get_selected_mode_from_session() -> str:
    """Return the current UI mode stored in session, or the default mode."""
    stored_mode = session.get("selected_mode", DEFAULT_MODE)
    return _to_ui_mode(normalize_mode(stored_mode))


def _to_ui_mode(mode: str) -> str:
    """Map internal mode names to the user-facing dropdown values."""
    if normalize_mode(mode) == "summarize_document":
        return "summarize"
    return normalize_mode(mode)


def _build_image_url(filename: str, path: Path) -> str:
    """Add a cache-busting timestamp so the browser shows the latest image."""
    timestamp = int(path.stat().st_mtime)
    return f"{url_for('static', filename=filename)}?v={timestamp}"


def _set_feedback(status: str | None = None, answer: str | None = None, error: str | None = None) -> None:
    """Update the main dashboard text state in a small local file."""
    feedback_state = _load_feedback_state()
    if status is not None:
        feedback_state["status"] = status
    if answer is not None:
        feedback_state["answer"] = answer
    if error is not None:
        feedback_state["error"] = error
    _write_feedback_state(feedback_state)


def _load_feedback_state() -> dict[str, str]:
    """Load the dashboard feedback state without relying on large session cookies."""
    default_state = {"status": "", "answer": "", "error": ""}
    if not WEB_FEEDBACK_PATH.is_file():
        return default_state

    try:
        raw_state = json.loads(WEB_FEEDBACK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_state

    return {
        "status": str(raw_state.get("status", "")),
        "answer": str(raw_state.get("answer", "")),
        "error": str(raw_state.get("error", "")),
    }


def _write_feedback_state(feedback_state: dict[str, str]) -> None:
    """Persist the dashboard feedback state on disk for the local web UI."""
    WEB_FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEB_FEEDBACK_PATH.write_text(
        json.dumps(feedback_state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _clear_feedback_state() -> None:
    """Reset the stored dashboard feedback while preserving image artifacts."""
    _write_feedback_state({"status": "", "answer": "", "error": ""})


def _cleanup_legacy_session_fields() -> None:
    """Remove large feedback keys from older cookie-based dashboard sessions."""
    session.pop("status", None)
    session.pop("answer", None)
    session.pop("error", None)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
