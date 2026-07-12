"""Shared UI mode, progress, and copy constants for Flask and Qt frontends."""

from __future__ import annotations

from typing import Any

from ai.modes import normalize_mode

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

UI_MODE_OPTIONS = (
    {
        "id": "read_text",
        "name": "Read Text",
        "description": "Hear printed text clearly",
        "button_label": "BUTTON 1",
        "internal_mode": "document_reader",
    },
    {
        "id": "summarize_document",
        "name": "Summarize Document",
        "description": "Get the key points quickly",
        "button_label": "BUTTON 2",
        "internal_mode": "document_reader",
    },
    {
        "id": "analyze_image",
        "name": "Analyze Image",
        "description": "Understand what you see",
        "button_label": "BUTTON 3",
        "internal_mode": "general_vision",
    },
    {
        "id": "professional_assistant",
        "name": "Professional Assistant",
        "description": "Write, plan, and organize",
        "button_label": "BUTTON 4",
        "internal_mode": "general_vision",
    },
    {
        "id": "solve_problem",
        "name": "Solve Problem",
        "description": "Work through questions step by step",
        "button_label": "BUTTON 5",
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

PROGRESS_STEPS = ("Image captured", "Processing", "Result")
PIPELINE_PROGRESS_STATES = frozenset(
    {
        "IDLE",
        "CAPTURING",
        "PREPROCESSING",
        "ANALYZING",
        "RETRY_QUEUED",
        "DONE",
        "ERROR",
    }
)
PIPELINE_PROGRESS_DETAILS = {
    "CAPTURING": "Capturing image...",
    "PREPROCESSING": "Preprocessing image...",
    "ANALYZING": "Sending to AI...",
    "RETRY_QUEUED": "Saved for retry",
    "DONE": "Result ready",
    "ERROR": "Error",
}
PROCESSING_MODE_COPY = {
    "read_text": {
        "title": "Reading Text",
        "subtitle": "Reading printed text",
    },
    "summarize_document": {
        "title": "Summarizing Document",
        "subtitle": "Analyzing structure and text",
    },
    "summarize": {
        "title": "Summarizing Document",
        "subtitle": "Analyzing structure and text",
    },
    "analyze_image": {
        "title": "Analyzing Image",
        "subtitle": "Understanding the captured image",
    },
    "professional_assistant": {
        "title": "Professional Assistant",
        "subtitle": "Organizing a professional response",
    },
    "solve_problem": {
        "title": "Solving Problem",
        "subtitle": "Working through the problem step by step",
    },
}
RESULT_MODE_TITLES = {
    "read_text": "Extracted Text",
    "summarize_document": "Key Takeaways",
    "summarize": "Key Takeaways",
    "analyze_image": "Image Analysis",
    "professional_assistant": "Recommendations",
    "solve_problem": "Solution",
}

READY_DETAIL = "Press button to select the mode."
MODE_SELECTED_DETAIL = "Selected mode ready. Press Button Main to capture."


def default_ui_mode_for_internal(internal_mode: str | None, fallback: str = "read_text") -> str:
    """Return the touchscreen UI mode that best matches an internal pipeline mode."""
    normalized_internal = normalize_internal_mode(internal_mode)
    if normalized_internal:
        return INTERNAL_TO_UI_MODE.get(normalized_internal, fallback)
    return fallback


def normalize_internal_mode(mode: Any) -> str:
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


def normalize_ui_mode(mode: Any) -> str:
    """Resolve saved mode values into one of the current five Raspberry Pi UI modes."""
    if not isinstance(mode, str):
        return ""

    normalized_mode = mode.strip().lower()
    if not normalized_mode:
        return ""
    if normalized_mode in UI_MODE_BY_ID:
        return normalized_mode

    internal_mode = normalize_internal_mode(normalized_mode)
    if not internal_mode:
        return ""
    return INTERNAL_TO_UI_MODE.get(internal_mode, "")


def resolve_mode_pair(
    selected_mode: Any,
    selected_mode_internal: Any = None,
    *,
    fallback_to_default: bool = False,
    default_capture_mode: str = "read_text",
    default_capture_internal_mode: str = "document_reader",
) -> tuple[str, str]:
    """Return the UI mode id and canonical internal mode for the current state."""
    ui_mode = normalize_ui_mode(selected_mode)
    internal_mode = normalize_internal_mode(selected_mode_internal)

    if ui_mode and not internal_mode:
        internal_mode = UI_MODE_TO_INTERNAL_MODE[ui_mode]
    if internal_mode and not ui_mode:
        ui_mode = INTERNAL_TO_UI_MODE.get(internal_mode, "")

    if fallback_to_default and not internal_mode:
        return default_capture_mode, default_capture_internal_mode
    return ui_mode, internal_mode


def normalize_progress_state(value: Any, *, default: str = "IDLE") -> str:
    """Normalize any persisted pipeline-progress marker into a supported value."""
    normalized = str(value or "").strip().upper()
    if normalized in PIPELINE_PROGRESS_STATES:
        return normalized
    return default
