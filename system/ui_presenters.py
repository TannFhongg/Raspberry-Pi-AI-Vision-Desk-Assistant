"""Shared UI presenter helpers for the native VisionDesk app."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Callable

from hardware.status import DeviceState, coerce_device_state
from markupsafe import Markup, escape

from system.ui_catalog import (
    MODE_LABELS,
    PIPELINE_PROGRESS_DETAILS,
    PROCESSING_MODE_COPY,
    PROGRESS_STEPS,
    RESULT_MODE_TITLES,
    normalize_progress_state,
)


def processing_copy_for_mode(selected_mode: str, default_capture_mode: str) -> dict[str, str]:
    """Return the processing-screen title and subtitle for the selected UI mode."""
    return PROCESSING_MODE_COPY.get(selected_mode, PROCESSING_MODE_COPY[default_capture_mode])


def processing_status_tone(progress_state: str) -> str:
    """Return the small status-card tone for the current processing state."""
    normalized_state = normalize_progress_state(progress_state)
    if normalized_state == "DONE":
        return "done"
    if normalized_state == "RETRY_QUEUED":
        return "queued"
    if normalized_state == "ERROR":
        return "error"
    return "active"


def processing_status_message(progress_state: str, *, detail: str = "", error: str = "") -> str:
    """Return the concise live processing status shown in the sidebar."""
    normalized_state = normalize_progress_state(progress_state)
    if normalized_state == "ERROR" and error:
        return error
    if detail.strip():
        return detail.strip()
    return PIPELINE_PROGRESS_DETAILS.get(normalized_state, "Processing...")


def build_processing_view(
    selected_mode: str,
    *,
    selected_mode_label: str,
    progress_state: str,
    detail: str,
    error: str,
    default_capture_mode: str,
) -> dict[str, str]:
    """Return the processing-screen copy derived from the selected mode and stage."""
    mode_copy = processing_copy_for_mode(selected_mode, default_capture_mode)
    mode_label = selected_mode_label or MODE_LABELS.get(default_capture_mode, "Read Text")
    return {
        "title": mode_copy["title"],
        "subtitle": mode_copy["subtitle"],
        "mode_label": mode_label.upper(),
        "status_message": processing_status_message(
            progress_state,
            detail=detail,
            error=error,
        ),
        "status_tone": processing_status_tone(progress_state),
    }


def result_title_for_mode(selected_mode: str) -> str:
    """Return the result-panel title for the selected UI mode."""
    return RESULT_MODE_TITLES.get(selected_mode, "Result")


def result_state_for_payload(status: str, answer_text: str, error_text: str = "") -> str:
    """Return the visual result state for the current completed screen payload."""
    normalized_status = status.strip().lower()
    if any(token in normalized_status for token in ("queued", "retry")):
        return "RETRY_PENDING"
    if any(token in normalized_status for token in ("failed", "error")) or error_text.strip():
        return "ERROR"
    if not answer_text.strip():
        return "NO_RESULT"
    return "RESULT_READY"


def build_result_view(
    selected_mode: str,
    *,
    selected_mode_label: str,
    status: str,
    answer_text: str,
    error_text: str = "",
    default_capture_mode: str,
) -> dict[str, Any]:
    """Return the result-screen title and content derived from the current UI state."""
    result_state = result_state_for_payload(status, answer_text, error_text)
    normalized_status = status.strip()
    body_text = answer_text.strip()
    note = ""

    if result_state == "RETRY_PENDING":
        title = "Retry queued"
        note = "Waiting for retry."
        if ("queued" in normalized_status.lower() or "retry" in normalized_status.lower()) and not body_text:
            body_text = "This capture was saved for automatic retry."
    elif result_state == "ERROR":
        title = "Analysis failed"
        if not body_text:
            body_text = error_text.strip() or "Analysis failed. Please go back and try again."
    elif result_state == "NO_RESULT":
        title = "No answer received"
        note = "No result available."
        if not body_text:
            body_text = "No answer was received for this capture."
    else:
        title = result_title_for_mode(selected_mode)

    return {
        "state": result_state,
        "mode_label": (
            selected_mode_label or MODE_LABELS.get(default_capture_mode, "Read Text")
        ).upper(),
        "title": title,
        "note": note,
        "body_text": body_text,
        "body_html": format_answer_html(body_text),
    }


def load_latest_result_summary(latest_result_path: str | Path | None) -> dict[str, Any]:
    """Return the non-sensitive metadata saved in the latest result text file."""
    summary: dict[str, Any] = {
        "status": "",
        "model_used": "",
        "duration_seconds": None,
        "camera_backend": "",
        "camera_resolution": "",
        "warnings": [],
    }
    if latest_result_path in {None, ""}:
        return summary
    latest_result_file = Path(latest_result_path)
    if not latest_result_file.is_file():
        return summary

    try:
        lines = latest_result_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return summary

    in_warnings = False
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            in_warnings = False
            continue

        if in_warnings:
            if line.startswith("- "):
                warning = line[2:].strip()
                if warning:
                    summary["warnings"].append(warning)
                continue
            in_warnings = False

        if line == "Warnings:":
            in_warnings = True
            continue

        if ":" not in line:
            continue

        raw_key, raw_value = line.split(":", 1)
        key = raw_key.strip().lower()
        value = raw_value.strip()
        if not value or value.lower() == "n/a":
            continue

        if key == "status":
            summary["status"] = value
        elif key == "model":
            summary["model_used"] = value
        elif key == "duration seconds":
            summary["duration_seconds"] = coerce_optional_float(value)
        elif key == "camera backend":
            summary["camera_backend"] = value
        elif key == "camera resolution":
            summary["camera_resolution"] = value

    if str(summary["status"]).strip().lower() == "cleared":
        return {
            "status": "",
            "model_used": "",
            "duration_seconds": None,
            "camera_backend": "",
            "camera_resolution": "",
            "warnings": [],
        }

    return summary


def format_result_duration(value: Any) -> str:
    """Return a compact processing-time label for the result detail card."""
    duration = coerce_optional_float(value)
    if duration is None:
        return ""
    if duration >= 60.0:
        minutes = int(duration // 60)
        seconds = int(round(duration % 60))
        return f"{minutes}m {seconds}s"
    if duration >= 10.0:
        return f"{duration:.1f} seconds"
    return f"{duration:.2f} seconds"


def result_detail_heading_for_mode(selected_mode: str) -> str:
    """Return the answer-derived section heading for the detail card."""
    headings = {
        "read_text": "Text Highlights",
        "summarize_document": "Summary Highlights",
        "analyze_image": "Scene Highlights",
        "professional_assistant": "Recommendation Highlights",
        "solve_problem": "Solution Highlights",
    }
    return headings.get(selected_mode, "AI Answer Highlights")


def split_answer_sentences(text: str) -> list[str]:
    """Split a plain answer line into sentence-like chunks."""
    normalized_text = text.strip()
    if not normalized_text:
        return []
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", normalized_text)
        if sentence.strip()
    ] or [normalized_text]


def normalize_answer_detail_item(text: str, *, max_chars: int = 180) -> str:
    """Return a compact single-line detail item derived from the AI answer."""
    compact = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text).strip()
    compact = re.sub(r"\s+", " ", compact)
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def is_structural_answer_label(text: str) -> bool:
    """Return True when a short line looks like a section label rather than content."""
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    if not normalized:
        return True
    if text.endswith(":"):
        return True
    common_labels = {
        "summary",
        "what s visible",
        "what is visible",
        "key points",
        "key takeaways",
        "details",
        "observations",
        "analysis",
        "recommendations",
        "next steps",
    }
    return normalized in common_labels


def extract_answer_detail_items(answer_text: str, *, max_items: int = 4) -> list[str]:
    """Extract concise supplementary bullets from the AI answer without copying the full answer."""
    if not answer_text.strip():
        return []

    list_candidates: list[str] = []
    sentence_candidates: list[str] = []

    for raw_line in answer_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if re.match(r"^#{1,3}\s+", line):
            continue

        numbered_match = re.match(r"^\d+[.)]\s+(.*)$", line)
        if numbered_match:
            candidate = normalize_answer_detail_item(numbered_match.group(1))
            if candidate:
                list_candidates.append(candidate)
            continue

        bullet_match = re.match(r"^(?:[-*]|\u2022)\s+(.*)$", line)
        if bullet_match:
            candidate = normalize_answer_detail_item(bullet_match.group(1))
            if candidate:
                list_candidates.append(candidate)
            continue

        plain_line = normalize_answer_detail_item(line)
        if not plain_line or is_structural_answer_label(plain_line):
            continue

        if re.match(r"^[A-Z][A-Za-z0-9 '&()/.-]{1,30}:\s+.+$", plain_line):
            list_candidates.append(plain_line)
            continue

        for sentence in split_answer_sentences(plain_line):
            candidate = normalize_answer_detail_item(sentence)
            if candidate and not is_structural_answer_label(candidate):
                sentence_candidates.append(candidate)

    prioritized_candidates = list_candidates if len(list_candidates) >= 2 else list_candidates + sentence_candidates
    if len(prioritized_candidates) < max_items:
        prioritized_candidates.extend(sentence_candidates)

    detail_items: list[str] = []
    seen_keys: set[str] = set()
    for candidate in prioritized_candidates:
        dedupe_key = re.sub(r"[^a-z0-9]+", " ", candidate.lower()).strip()
        if not dedupe_key or dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        detail_items.append(candidate)
        if len(detail_items) >= max_items:
            break

    return detail_items


def build_result_detail_view(
    *,
    selected_mode: str,
    answer_text: str,
    result_state: str,
    detail_text: str,
    error_text: str,
    latest_result_path: str | Path | None,
    history_entry: dict[str, Any] | None = None,
    history_entry_camera_resolution: Callable[[dict[str, Any]], tuple[int, int] | None] | None = None,
) -> dict[str, Any]:
    """Build the supplementary detail card using existing backend data only."""
    latest_result_summary = load_latest_result_summary(latest_result_path)
    entry = history_entry or {}
    detail_sections: list[str] = []

    answer_detail_items = extract_answer_detail_items(answer_text)
    if answer_detail_items:
        detail_sections.append(f"### {result_detail_heading_for_mode(selected_mode)}")
        detail_sections.extend(f"- {item}" for item in answer_detail_items)

    technical_detail = error_text.strip()
    if technical_detail and result_state in {"ERROR", "RETRY_PENDING"}:
        detail_sections.extend(
            [
                "### Technical Detail",
                technical_detail,
            ]
        )

    metadata_items: list[str] = []
    model_used = str(entry.get("model_used") or latest_result_summary.get("model_used", "")).strip()
    if model_used:
        metadata_items.append(f"Model: {model_used}")

    duration_label = format_result_duration(
        entry.get("duration_seconds", latest_result_summary.get("duration_seconds"))
    )
    if duration_label:
        metadata_items.append(f"Processing time: {duration_label}")

    camera_backend = str(
        entry.get("camera_backend_used") or latest_result_summary.get("camera_backend", "")
    ).strip()
    if camera_backend:
        metadata_items.append(f"Camera backend: {camera_backend}")

    camera_resolution = ""
    if entry and history_entry_camera_resolution is not None:
        resolution = history_entry_camera_resolution(entry)
        if resolution is not None:
            camera_resolution = f"{resolution[0]} x {resolution[1]}"
    if not camera_resolution:
        camera_resolution = str(latest_result_summary.get("camera_resolution", "")).strip()
    if camera_resolution:
        metadata_items.append(f"Camera resolution: {camera_resolution}")

    retry_status = str(entry.get("retry_status", "")).strip().replace("_", " ")
    if retry_status:
        metadata_items.append(f"Retry status: {retry_status.title()}")

    error_summary = str(entry.get("error_summary", "")).strip()
    if error_summary and error_summary != technical_detail:
        metadata_items.append(f"Error summary: {error_summary}")

    if metadata_items:
        detail_sections.append("### Processing Metadata")
        detail_sections.extend(f"- {item}" for item in metadata_items)

    warnings = latest_result_summary.get("warnings", [])
    if warnings:
        detail_sections.append("### Warnings")
        detail_sections.extend(f"- {warning}" for warning in warnings if str(warning).strip())

    detail_body_text = "\n".join(section for section in detail_sections if section).strip()
    if not detail_body_text and detail_text.strip() not in {
        "",
        PIPELINE_PROGRESS_DETAILS["DONE"],
        PIPELINE_PROGRESS_DETAILS["RETRY_QUEUED"],
        PIPELINE_PROGRESS_DETAILS["ERROR"],
    }:
        detail_body_text = detail_text.strip()

    return {
        "title": "Additional Detail",
        "has_content": bool(detail_body_text),
        "body_html": (
            format_answer_html(detail_body_text)
            if detail_body_text
            else Markup("<p class='answer-empty'>No additional detail available.</p>")
        ),
    }


def processing_error_step(progress_state: str, current_step: int) -> int:
    """Return which visual step should show an error for a failed pipeline stage."""
    normalized_state = normalize_progress_state(progress_state)
    if normalized_state == "CAPTURING" or current_step <= 0:
        return 0
    return 1


def pipeline_progress_to_step_index(progress_state: str, *, progress_error_step: int = -1) -> int:
    """Return the legacy numeric progress index used by the persisted UI state."""
    normalized_state = normalize_progress_state(progress_state)
    if normalized_state == "CAPTURING":
        return 0
    if normalized_state in {"PREPROCESSING", "ANALYZING"}:
        return 1
    if normalized_state == "DONE":
        return len(PROGRESS_STEPS)
    if normalized_state in {"RETRY_QUEUED", "ERROR"}:
        if 0 <= progress_error_step < len(PROGRESS_STEPS):
            return progress_error_step
        return 1
    return -1


def processing_progress_for_message(pipeline_message: str) -> tuple[str, int, str]:
    """Map shared pipeline callback text into UI-safe stage metadata."""
    normalized_message = pipeline_message.strip()
    message_lookup = {
        "Capturing image...": ("CAPTURING", 0, PIPELINE_PROGRESS_DETAILS["CAPTURING"]),
        "Preprocessing image...": (
            "PREPROCESSING",
            1,
            PIPELINE_PROGRESS_DETAILS["PREPROCESSING"],
        ),
        "Sending image to OpenAI Vision...": (
            "ANALYZING",
            1,
            PIPELINE_PROGRESS_DETAILS["ANALYZING"],
        ),
    }
    return message_lookup.get(
        normalized_message,
        ("ANALYZING", 1, PIPELINE_PROGRESS_DETAILS["ANALYZING"]),
    )


def build_progress_steps(
    progress_state: str,
    *,
    progress_error_step: int = -1,
) -> list[dict[str, str]]:
    """Return Figma-style processing steps for the current pipeline state."""
    steps: list[dict[str, str]] = []
    normalized_state = normalize_progress_state(progress_state)
    visual_states = ["pending"] * len(PROGRESS_STEPS)

    if normalized_state == "CAPTURING":
        visual_states[0] = "active"
    elif normalized_state in {"PREPROCESSING", "ANALYZING"}:
        visual_states[0] = "complete"
        visual_states[1] = "active"
    elif normalized_state == "DONE":
        visual_states = ["complete"] * len(PROGRESS_STEPS)
    elif normalized_state in {"RETRY_QUEUED", "ERROR"}:
        resolved_error_step = progress_error_step
        if resolved_error_step < 0 or resolved_error_step >= len(PROGRESS_STEPS):
            resolved_error_step = 1
        for index in range(resolved_error_step):
            visual_states[index] = "complete"
        visual_states[resolved_error_step] = "error"

    for index, label in enumerate(PROGRESS_STEPS):
        state = visual_states[index]
        steps.append(
            {
                "label": label,
                "state": state,
                "state_label": state.replace("_", " ").title(),
            }
        )
    return steps


def format_answer_html(answer: str) -> Markup:
    """Render plain-text answers as readable headings, paragraphs, and lists."""
    if not answer.strip():
        return Markup("<p class='answer-empty'>No answer yet.</p>")

    parts: list[str] = []
    list_items: list[str] = []
    list_kind = ""

    def flush_list() -> None:
        nonlocal list_items, list_kind
        if not list_items:
            return
        items = "".join(f"<li>{item}</li>" for item in list_items)
        tag_name = "ol" if list_kind == "ol" else "ul"
        parts.append(f"<{tag_name}>{items}</{tag_name}>")
        list_items = []
        list_kind = ""

    def format_inline(text: str) -> str:
        rendered: list[str] = []
        tokens = re.split(r"(\*\*.*?\*\*|__.*?__)", text)
        for token in tokens:
            if not token:
                continue
            if (token.startswith("**") and token.endswith("**")) or (
                token.startswith("__") and token.endswith("__")
            ):
                rendered.append(f"<strong>{escape(token[2:-2])}</strong>")
            else:
                rendered.append(str(escape(token)))
        return "".join(rendered)

    def split_plain_paragraphs(text: str) -> list[str]:
        normalized_text = text.strip()
        if len(normalized_text) < 220:
            return [normalized_text]

        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", normalized_text)
            if sentence.strip()
        ]
        if len(sentences) < 2:
            return [normalized_text]

        paragraphs: list[str] = []
        current: list[str] = []
        current_length = 0
        for sentence in sentences:
            projected_length = current_length + len(sentence) + (1 if current else 0)
            if current and (projected_length > 220 or len(current) >= 2):
                paragraphs.append(" ".join(current))
                current = [sentence]
                current_length = len(sentence)
                continue

            current.append(sentence)
            current_length = projected_length

        if current:
            paragraphs.append(" ".join(current))
        return paragraphs or [normalized_text]

    for raw_line in answer.splitlines():
        line = raw_line.strip()
        if not line:
            flush_list()
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading_match:
            flush_list()
            heading_level = min(5, 2 + len(heading_match.group(1)))
            parts.append(
                f"<h{heading_level}>{format_inline(heading_match.group(2))}</h{heading_level}>"
            )
            continue

        numbered_match = re.match(r"^\d+[.)]\s+(.*)$", line)
        if numbered_match:
            if list_kind not in {"", "ol"}:
                flush_list()
            list_kind = "ol"
            list_items.append(format_inline(numbered_match.group(1)))
            continue

        bullet_match = re.match(r"^(?:[-*]|\u2022)\s+(.*)$", line)
        if bullet_match:
            if list_kind not in {"", "ul"}:
                flush_list()
            list_kind = "ul"
            list_items.append(format_inline(bullet_match.group(1)))
            continue

        flush_list()
        for paragraph in split_plain_paragraphs(line):
            parts.append(f"<p>{format_inline(paragraph)}</p>")

    flush_list()
    return Markup("".join(parts))


def humanize_error(error_message: str) -> str:
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


def classify_health_value_size(value: str) -> str:
    """Return a CSS/QML-friendly size bucket for compact health pill values."""
    normalized_value = re.sub(r"\s+", "", str(value or "N/A"))
    if len(normalized_value) >= 10:
        return "very-long"
    if len(normalized_value) >= 8:
        return "long"
    return "normal"


def build_health_metric(
    *,
    key: str,
    label: str,
    value: str,
    state: str,
    message: str,
    aria_label: str,
    **extra: Any,
) -> dict[str, Any]:
    """Return one header metric payload."""
    metric = {
        "key": key,
        "label": label,
        "value": value,
        "value_size": classify_health_value_size(value),
        "state": state,
        "message": message,
        "title": message,
        "aria_label": aria_label,
    }
    metric.update(extra)
    return metric


def metric_state_for_thresholds(
    value: float,
    *,
    warning_threshold: float,
    error_threshold: float,
) -> str:
    """Map a numeric value into healthy, warning, or error states."""
    if value >= error_threshold:
        return "error"
    if value >= warning_threshold:
        return "warning"
    return "healthy"


def normalize_metric_state(value: Any) -> str:
    """Normalize pass/warn/fail/unknown values into shared UI states."""
    normalized = str(value or "").strip().lower()
    if normalized == "pass":
        return "healthy"
    if normalized in {"warning", "warn"}:
        return "warning"
    if normalized == "fail":
        return "error"
    return "unavailable"


@dataclass(slots=True)
class HealthSummaryBuilder:
    """Build the shared live health/header payload for the native UI."""

    load_ui_state: Callable[[], dict[str, Any]]
    resolve_mode_pair: Callable[[Any, Any], tuple[str, str]]
    resolve_render_screen: Callable[[Any, str], str]
    load_health_snapshot: Callable[[], dict[str, Any] | None]
    load_setup_state: Callable[[], dict[str, Any]]
    setup_is_complete: Callable[[], bool]
    live_preview_runtime_status: Callable[[], tuple[bool, str]]
    is_live_preview_screen: Callable[[str | None], bool]
    camera_autofocus_mode: str
    cpu_warning_threshold: float
    cpu_error_threshold: float
    memory_warning_threshold: float
    memory_error_threshold: float
    offline_retry_enabled: bool

    def build_summary(self, *, render_screen: str | None = None) -> dict[str, Any]:
        """Return the shared header health summary for every device screen."""
        ui_state = self.load_ui_state()
        selected_mode, _selected_mode_internal = self.resolve_mode_pair(
            ui_state.get("selected_mode"),
            ui_state.get("selected_mode_internal"),
        )
        if render_screen is None:
            render_screen = self.resolve_render_screen(ui_state.get("screen", "home"), selected_mode)

        snapshot = self.load_health_snapshot()
        setup_state = self.load_setup_state() if render_screen == "setup" or not self.setup_is_complete() else None
        cpu_metric = self.build_cpu_health_metric(snapshot)
        ram_metric = self.build_ram_health_metric(snapshot)
        wifi_metric = self.build_wifi_health_metric(
            snapshot,
            render_screen=render_screen,
            setup_state=setup_state,
        )
        camera_metric = self.build_camera_health_metric(
            snapshot,
            render_screen=render_screen,
            ui_state=ui_state,
        )
        system_metric = self.build_system_health_metric(
            snapshot=snapshot,
            ui_state=ui_state,
            render_screen=render_screen,
            cpu_metric=cpu_metric,
            ram_metric=ram_metric,
            wifi_metric=wifi_metric,
            camera_metric=camera_metric,
        )
        metrics = [
            system_metric,
            cpu_metric,
            ram_metric,
            wifi_metric,
            camera_metric,
        ]
        updated_at = str(snapshot.get("updated_at", "")) if snapshot else str(ui_state.get("updated_at", ""))

        return {
            "updated_at": updated_at,
            "metrics": metrics,
            "system": system_metric,
            "cpu": cpu_metric,
            "ram": ram_metric,
            "wifi": wifi_metric,
            "camera": camera_metric,
            "camera_preview": self.build_camera_preview_summary(render_screen=render_screen),
            "camera_analysis": self.build_camera_analysis_summary(render_screen=render_screen),
        }

    def build_cpu_health_metric(self, snapshot: dict[str, Any] | None) -> dict[str, Any]:
        """Return the CPU header metric."""
        if not snapshot or not isinstance(snapshot.get("cpu"), dict):
            return build_health_metric(
                key="cpu",
                label="CPU",
                value="N/A",
                state="unavailable",
                message="CPU temperature is unavailable.",
                aria_label="CPU temperature unavailable",
                temperature_c=None,
            )

        cpu = snapshot["cpu"]
        temperature_c = cpu.get("temperature_c")
        if not isinstance(temperature_c, (int, float)):
            return build_health_metric(
                key="cpu",
                label="CPU",
                value="N/A",
                state="unavailable",
                message=str(cpu.get("message", "CPU temperature is unavailable.")),
                aria_label="CPU temperature unavailable",
                temperature_c=None,
            )

        rounded_temperature = int(float(temperature_c) + 0.5)
        state = metric_state_for_thresholds(
            float(temperature_c),
            warning_threshold=self.cpu_warning_threshold,
            error_threshold=self.cpu_error_threshold,
        )
        return build_health_metric(
            key="cpu",
            label="CPU",
            value=f"{rounded_temperature}\N{DEGREE SIGN}C",
            state=state,
            message=str(cpu.get("message", "CPU temperature is unavailable.")),
            aria_label=f"CPU temperature: {rounded_temperature} degrees Celsius",
            temperature_c=rounded_temperature,
        )

    def build_ram_health_metric(self, snapshot: dict[str, Any] | None) -> dict[str, Any]:
        """Return the RAM header metric."""
        if not snapshot or not isinstance(snapshot.get("memory"), dict):
            return build_health_metric(
                key="ram",
                label="RAM",
                value="N/A",
                state="unavailable",
                message="Memory usage is unavailable.",
                aria_label="RAM usage unavailable",
                usage_percent=None,
            )

        memory = snapshot["memory"]
        used_percent = memory.get("used_percent")
        if not isinstance(used_percent, (int, float)):
            return build_health_metric(
                key="ram",
                label="RAM",
                value="N/A",
                state="unavailable",
                message=str(memory.get("message", "Memory usage is unavailable.")),
                aria_label="RAM usage unavailable",
                usage_percent=None,
            )

        rounded_percent = int(float(used_percent) + 0.5)
        state = metric_state_for_thresholds(
            float(used_percent),
            warning_threshold=self.memory_warning_threshold,
            error_threshold=self.memory_error_threshold,
        )
        return build_health_metric(
            key="ram",
            label="RAM",
            value=f"{rounded_percent}%",
            state=state,
            message=str(memory.get("message", "Memory usage is unavailable.")),
            aria_label=f"RAM usage: {rounded_percent} percent",
            usage_percent=rounded_percent,
        )

    def build_wifi_health_metric(
        self,
        snapshot: dict[str, Any] | None,
        *,
        render_screen: str | None = None,
        setup_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return the Wi-Fi header metric."""
        wifi_state = setup_state.get("wifi", {}) if isinstance(setup_state, dict) else {}
        connect_status = str(wifi_state.get("connect_status", "")).strip().lower()
        scan_status = str(wifi_state.get("scan_status", "")).strip().lower()
        setup_message = str(wifi_state.get("message", "")).strip()

        if render_screen == "setup":
            if connect_status in {"running", "connecting"} or scan_status in {"running", "connecting"}:
                return build_health_metric(
                    key="wifi",
                    label="WIFI",
                    value="CONNECTING",
                    state="warning",
                    message=setup_message or "Wi-Fi setup is in progress.",
                    aria_label="Wi-Fi status: connecting",
                )
            if connect_status == "pass":
                return build_health_metric(
                    key="wifi",
                    label="WIFI",
                    value="OK",
                    state="healthy",
                    message=setup_message or "Wi-Fi is connected.",
                    aria_label="Wi-Fi status: OK",
                )
            if connect_status == "fail" or scan_status == "fail":
                return build_health_metric(
                    key="wifi",
                    label="WIFI",
                    value="ERROR",
                    state="error",
                    message=setup_message or "Wi-Fi setup failed.",
                    aria_label="Wi-Fi status: error",
                )

        if not snapshot or not isinstance(snapshot.get("network"), dict):
            return build_health_metric(
                key="wifi",
                label="WIFI",
                value="N/A",
                state="unavailable",
                message="Wi-Fi status is unavailable.",
                aria_label="Wi-Fi status unavailable",
            )

        network = snapshot["network"]
        normalized_status = normalize_metric_state(network.get("status"))
        message = str(network.get("message", "Wi-Fi status is unavailable."))

        if normalized_status == "healthy":
            return build_health_metric(
                key="wifi",
                label="WIFI",
                value="OK",
                state="healthy",
                message=message,
                aria_label="Wi-Fi status: OK",
            )
        if normalized_status == "warning":
            return build_health_metric(
                key="wifi",
                label="WIFI",
                value="CONNECTING",
                state="warning",
                message=message,
                aria_label="Wi-Fi status: connecting",
            )
        if normalized_status == "error":
            return build_health_metric(
                key="wifi",
                label="WIFI",
                value="OFFLINE",
                state="unavailable",
                message=message,
                aria_label="Wi-Fi status: offline",
            )

        return build_health_metric(
            key="wifi",
            label="WIFI",
            value="N/A",
            state="unavailable",
            message=message,
            aria_label="Wi-Fi status unavailable",
        )

    def build_camera_health_metric(
        self,
        snapshot: dict[str, Any] | None,
        *,
        render_screen: str | None = None,
        ui_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return the camera header metric with live-preview-aware overrides."""
        current_ui_state = ui_state or self.load_ui_state()
        device_state = coerce_device_state(current_ui_state.get("device_state"))
        has_recent_frame, latest_error = self.live_preview_runtime_status()

        if device_state == DeviceState.CAPTURING:
            return build_health_metric(
                key="camera",
                label="CAM",
                value="CAPTURING",
                state="warning",
                message="A capture is in progress.",
                aria_label="Camera status: capturing",
            )

        if has_recent_frame:
            return build_health_metric(
                key="camera",
                label="CAM",
                value="OK",
                state="healthy",
                message="Live preview is receiving camera frames normally.",
                aria_label="Camera status: OK",
            )

        if snapshot and isinstance(snapshot.get("camera"), dict):
            camera = snapshot["camera"]
            normalized_status = normalize_metric_state(camera.get("status"))
            message = str(camera.get("message", "Camera status is unavailable."))
            if normalized_status == "healthy":
                return build_health_metric(
                    key="camera",
                    label="CAM",
                    value="OK",
                    state="healthy",
                    message=message,
                    aria_label="Camera status: OK",
                )
            if normalized_status == "error":
                return build_health_metric(
                    key="camera",
                    label="CAM",
                    value="ERROR",
                    state="error",
                    message=message,
                    aria_label="Camera status: error",
                )

        if self.is_live_preview_screen(render_screen):
            return build_health_metric(
                key="camera",
                label="CAM",
                value="PREPARING",
                state="warning",
                message=latest_error or "Live preview is warming up the camera feed.",
                aria_label="Camera status: preparing",
            )

        if latest_error:
            return build_health_metric(
                key="camera",
                label="CAM",
                value="ERROR",
                state="error",
                message=latest_error,
                aria_label="Camera status: error",
            )

        return build_health_metric(
            key="camera",
            label="CAM",
            value="N/A",
            state="unavailable",
            message="Camera status is unavailable.",
            aria_label="Camera status unavailable",
        )

    def build_system_health_metric(
        self,
        *,
        snapshot: dict[str, Any] | None,
        ui_state: dict[str, Any],
        render_screen: str,
        cpu_metric: dict[str, Any],
        ram_metric: dict[str, Any],
        wifi_metric: dict[str, Any],
        camera_metric: dict[str, Any],
    ) -> dict[str, Any]:
        """Return the overall system header metric using live UI and hardware state."""
        device_state = coerce_device_state(ui_state.get("device_state"))
        updated_at = str(snapshot.get("updated_at", "")) if snapshot else ""

        if (
            device_state == DeviceState.ERROR
            or cpu_metric["state"] == "error"
            or ram_metric["state"] == "error"
            or camera_metric["state"] == "error"
        ):
            message = "Critical device attention is required."
            if updated_at:
                message = f"{message} Last update: {updated_at}."
            return build_health_metric(
                key="system",
                label="SYS",
                value="ERROR",
                state="error",
                message=message,
                aria_label="System status: error",
            )

        preparing_values = {"PREPARING", "CONNECTING", "CAPTURING"}
        if (
            not self.setup_is_complete()
            or render_screen == "setup"
            or device_state in {DeviceState.CAPTURING, DeviceState.PROCESSING}
            or snapshot is None
            or camera_metric["value"] in preparing_values
            or wifi_metric["value"] == "CONNECTING"
        ):
            message = "The application is preparing hardware or pipeline state."
            if updated_at:
                message = f"{message} Last update: {updated_at}."
            return build_health_metric(
                key="system",
                label="SYS",
                value="PREPARING",
                state="warning",
                message=message,
                aria_label="System status: preparing",
            )

        if (
            cpu_metric["state"] == "warning"
            or ram_metric["state"] == "warning"
            or wifi_metric["value"] == "OFFLINE"
        ):
            if wifi_metric["value"] == "OFFLINE" and self.offline_retry_enabled:
                message = "Network is offline, but offline retry remains available."
            else:
                message = "The device is running with a warning condition."
            if updated_at:
                message = f"{message} Last update: {updated_at}."
            return build_health_metric(
                key="system",
                label="SYS",
                value="WARNING",
                state="warning",
                message=message,
                aria_label="System status: warning",
            )

        message = "The application and monitored hardware are running normally."
        if updated_at:
            message = f"{message} Last update: {updated_at}."
        return build_health_metric(
            key="system",
            label="SYS",
            value="OK",
            state="healthy",
            message=message,
            aria_label="System status: OK",
        )

    def build_camera_preview_summary(self, *, render_screen: str | None = None) -> dict[str, Any]:
        """Return the preview placeholder or error message for the camera screen."""
        has_recent_frame, latest_error = self.live_preview_runtime_status()
        if has_recent_frame:
            return {
                "status": "pass",
                "screen_state": "PREVIEW_READY",
                "title": "",
                "message": "",
                "show_placeholder": False,
            }

        if latest_error:
            return {
                "status": "fail",
                "screen_state": "ERROR",
                "title": "Camera unavailable",
                "message": latest_error,
                "show_placeholder": True,
            }

        if self.is_live_preview_screen(render_screen):
            return {
                "status": "unknown",
                "screen_state": "PREVIEW_LOADING",
                "title": "Preview Image Here",
                "message": "Live preview is starting.",
                "show_placeholder": True,
            }

        return {
            "status": "unknown",
            "screen_state": "READY",
            "title": "Preview Image Here",
            "message": "Select a mode to open the live preview.",
            "show_placeholder": True,
        }

    def build_camera_analysis_summary(
        self,
        *,
        render_screen: str | None = None,
    ) -> dict[str, dict[str, str]]:
        """Return frontend-friendly camera-analysis status pills using current real signals."""
        has_recent_frame, latest_error = self.live_preview_runtime_status()
        preview_visible = self.is_live_preview_screen(render_screen)

        if latest_error:
            return {
                "autofocus": {
                    "status": "fail",
                    "label": "ERROR",
                    "message": latest_error,
                },
                "lighting": {
                    "status": "unknown",
                    "label": "UNAVAILABLE",
                    "message": "Lighting analysis is unavailable while the camera preview is failing.",
                },
                "sharpness": {
                    "status": "unknown",
                    "label": "UNAVAILABLE",
                    "message": "Sharpness analysis is unavailable while the camera preview is failing.",
                },
            }

        if has_recent_frame and self.camera_autofocus_mode != "off":
            autofocus_status = "pass"
            autofocus_label = "READY"
            autofocus_message = "Autofocus is enabled and the preview is receiving live frames."
        elif self.camera_autofocus_mode == "off":
            autofocus_status = "unknown"
            autofocus_label = "UNAVAILABLE"
            autofocus_message = "Autofocus is disabled in the current camera configuration."
        elif preview_visible:
            autofocus_status = "unknown"
            autofocus_label = "UNAVAILABLE"
            autofocus_message = "Autofocus status will update after the live preview receives frames."
        else:
            autofocus_status = "unknown"
            autofocus_label = "UNAVAILABLE"
            autofocus_message = "Select a mode to open the live preview."

        if has_recent_frame:
            lighting_status = "pass"
            lighting_label = "GOOD"
            lighting_message = "Preview lighting looks suitable for capture."
            sharpness_status = "pass"
            sharpness_label = "READY"
            sharpness_message = "Preview frames are arriving and appear stable."
        elif preview_visible:
            lighting_status = "unknown"
            lighting_label = "UNAVAILABLE"
            lighting_message = "Lighting analysis will update after the live preview receives frames."
            sharpness_status = "unknown"
            sharpness_label = "UNAVAILABLE"
            sharpness_message = "Sharpness analysis will update after the live preview receives frames."
        else:
            lighting_status = "unknown"
            lighting_label = "UNAVAILABLE"
            lighting_message = "Open the live preview to inspect lighting."
            sharpness_status = "unknown"
            sharpness_label = "UNAVAILABLE"
            sharpness_message = "Open the live preview to inspect sharpness."

        return {
            "autofocus": {
                "status": autofocus_status,
                "label": autofocus_label,
                "message": autofocus_message,
            },
            "lighting": {
                "status": lighting_status,
                "label": lighting_label,
                "message": lighting_message,
            },
            "sharpness": {
                "status": sharpness_status,
                "label": sharpness_label,
                "message": sharpness_message,
            },
        }


def coerce_optional_float(value: Any) -> float | None:
    """Return a float value when a persisted payload contains one."""
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
