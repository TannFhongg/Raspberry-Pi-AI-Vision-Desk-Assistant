"""Shared pipeline runner for camera capture, preprocessing, and AI analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
import time
from typing import Callable

from ai.prompts import normalize_mode
from config import load_device_settings
from camera import CameraCaptureError, capture_image
from system.storage import atomic_write_text
from vision import ImagePreprocessError, preprocess_image, preprocess_output_matches

DEFAULT_CAPTURED_PATH = Path("data/private/current/captured.jpg")
DEFAULT_PROCESSED_PATH = Path("data/private/current/processed.jpg")
DEFAULT_RESULT_PATH = Path("data/latest_result.txt")
TEXT_HEAVY_MODES = frozenset({"document_reader", "math_solver", "meeting_assistant"})
VALID_SCREEN_OPTIMIZATIONS = ("auto", "on", "off")
StatusCallback = Callable[[str], None]
LOGGER = logging.getLogger(__name__)


class PipelineError(Exception):
    """Friendly error raised when a pipeline step fails."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        captured_path: str | Path | None = None,
        processed_path: str | Path | None = None,
        mode: str | None = None,
        camera_backend_used: str | None = None,
        camera_resolution: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.captured_path = Path(captured_path) if captured_path else None
        self.processed_path = Path(processed_path) if processed_path else None
        self.mode = mode
        self.camera_backend_used = camera_backend_used
        self.camera_resolution = camera_resolution

    def attach_context(
        self,
        *,
        captured_path: str | Path | None = None,
        processed_path: str | Path | None = None,
        mode: str | None = None,
        camera_backend_used: str | None = None,
        camera_resolution: tuple[int, int] | None = None,
    ) -> "PipelineError":
        """Backfill any missing pipeline context on an existing error instance."""
        if self.captured_path is None and captured_path:
            self.captured_path = Path(captured_path)
        if self.processed_path is None and processed_path:
            self.processed_path = Path(processed_path)
        if self.mode is None and mode:
            self.mode = mode
        if self.camera_backend_used is None and camera_backend_used:
            self.camera_backend_used = camera_backend_used
        if self.camera_resolution is None and camera_resolution is not None:
            self.camera_resolution = camera_resolution
        return self


@dataclass(slots=True)
class PipelineResult:
    """Result returned from the shared pipeline runner."""

    captured_path: Path | None
    processed_path: Path | None
    answer: str | None
    mode: str
    camera_backend_used: str | None
    camera_resolution: tuple[int, int] | None
    status: str
    warnings: tuple[str, ...] = ()
    model_used: str | None = None
    duration_seconds: float | None = None
    retry_status: str = ""
    error_summary: str = ""


def file_exists(path: str | Path) -> bool:
    """Return True when the given path exists and is a file."""
    return Path(path).is_file()


def file_mtime(path: str | Path) -> float | None:
    """Return the file modified time, or None when the file is missing."""
    file_path = Path(path)
    if not file_path.is_file():
        return None
    return file_path.stat().st_mtime


def is_processed_fresh(
    captured_path: str | Path,
    processed_path: str | Path,
    grayscale: bool = False,
    max_dimension: int = 1600,
    detect_screen: bool = False,
    enhance_text: bool = False,
) -> bool:
    """Return True when the processed image matches the current source and options."""
    return preprocess_output_matches(
        input_path=captured_path,
        output_path=processed_path,
        grayscale=grayscale,
        max_dimension=max_dimension,
        detect_screen=detect_screen,
        enhance_text=enhance_text,
    )


def should_use_screen_optimization(mode: str | None, screen_optimization: str) -> bool:
    """Resolve whether screen/document optimization should run for this mode."""
    normalized_setting = screen_optimization.strip().lower()
    if normalized_setting not in VALID_SCREEN_OPTIMIZATIONS:
        expected = ", ".join(VALID_SCREEN_OPTIMIZATIONS)
        raise ValueError(
            f"Invalid screen optimization setting '{screen_optimization}'. Expected one of: {expected}."
        )

    if normalized_setting == "on":
        return True
    if normalized_setting == "off" or mode is None:
        return False

    return normalize_mode(mode) in TEXT_HEAVY_MODES


def resolve_preprocess_options(
    mode: str | None,
    screen_optimization: str,
) -> tuple[bool, bool]:
    """Resolve preprocess flags for screen detection and enhancement."""
    use_screen_optimization = should_use_screen_optimization(mode, screen_optimization)
    return use_screen_optimization, use_screen_optimization


def run_capture(
    output_path: str = str(DEFAULT_CAPTURED_PATH),
    backend: str | None = None,
    camera_index: int | None = None,
    width: int | None = None,
    height: int | None = None,
    autofocus_mode: str | None = None,
    exposure: str | int | None = None,
    brightness: float | None = None,
    capture_delay_seconds: float | None = None,
    status_callback: StatusCallback | None = None,
) -> PipelineResult:
    """Capture an image only and return a shared pipeline result."""
    LOGGER.info(
        "Capture started backend=%s camera_index=%s width=%s height=%s",
        backend or "default",
        camera_index,
        width,
        height,
    )
    try:
        _emit_status(status_callback, "Capturing image...")
        capture_result = capture_image(
            output_path=output_path,
            backend=backend,
            camera_index=camera_index,
            width=width,
            height=height,
            autofocus_mode=autofocus_mode,
            exposure=exposure,
            brightness=brightness,
            capture_delay_seconds=capture_delay_seconds,
        )
    except CameraCaptureError as exc:
        LOGGER.error("Capture failed: %s", exc, exc_info=True)
        raise PipelineError(str(exc)) from exc

    LOGGER.info(
        "Capture succeeded backend=%s resolution=%s warnings=%s",
        capture_result.backend_used,
        capture_result.resolution,
        len(capture_result.warnings),
    )

    return PipelineResult(
        captured_path=capture_result.output_path,
        processed_path=None,
        answer=None,
        mode="capture",
        camera_backend_used=capture_result.backend_used,
        camera_resolution=capture_result.resolution,
        status="success",
        warnings=capture_result.warnings,
    )


def run_preprocess(
    input_path: str = str(DEFAULT_CAPTURED_PATH),
    output_path: str = str(DEFAULT_PROCESSED_PATH),
    mode: str | None = None,
    grayscale: bool | None = None,
    max_dimension: int | None = None,
    screen_optimization: str | None = None,
    status_callback: StatusCallback | None = None,
) -> PipelineResult:
    """Preprocess an image only and return a shared pipeline result."""
    settings = load_device_settings()
    resolved_grayscale = settings.camera.grayscale if grayscale is None else grayscale
    resolved_max_dimension = (
        settings.camera.max_dimension
        if max_dimension is None
        else max_dimension
    )
    resolved_screen_optimization = (
        settings.vision.screen_optimization
        if screen_optimization is None
        else screen_optimization
    )

    try:
        detect_screen, enhance_text = resolve_preprocess_options(
            mode=mode,
            screen_optimization=resolved_screen_optimization,
        )
        LOGGER.info(
            "Preprocess started input=%s output=%s mode=%s detect_screen=%s enhance_text=%s",
            input_path,
            output_path,
            mode,
            detect_screen,
            enhance_text,
        )
        _emit_status(status_callback, "Preprocessing image...")
        preprocess_result = preprocess_image(
            input_path=input_path,
            output_path=output_path,
            grayscale=resolved_grayscale,
            max_dimension=resolved_max_dimension,
            detect_screen=detect_screen,
            enhance_text=enhance_text,
        )
    except (ImagePreprocessError, ValueError) as exc:
        LOGGER.error("Preprocess failed: %s", exc, exc_info=True)
        raise PipelineError(str(exc)) from exc

    LOGGER.info(
        "Preprocess succeeded input=%s output=%s warnings=%s",
        preprocess_result.input_path,
        preprocess_result.output_path,
        len(preprocess_result.warnings),
    )

    return PipelineResult(
        captured_path=preprocess_result.input_path,
        processed_path=preprocess_result.output_path,
        answer=None,
        mode="preprocess",
        camera_backend_used=None,
        camera_resolution=None,
        status="success",
        warnings=preprocess_result.warnings,
    )


def run_analyze(
    mode: str,
    captured_path: str = str(DEFAULT_CAPTURED_PATH),
    processed_path: str = str(DEFAULT_PROCESSED_PATH),
    grayscale: bool | None = None,
    max_dimension: int | None = None,
    screen_optimization: str | None = None,
    status_callback: StatusCallback | None = None,
) -> PipelineResult:
    """Analyze the latest available image, preprocessing when needed."""
    settings = load_device_settings()
    resolved_grayscale = settings.camera.grayscale if grayscale is None else grayscale
    resolved_max_dimension = (
        settings.camera.max_dimension
        if max_dimension is None
        else max_dimension
    )
    resolved_screen_optimization = (
        settings.vision.screen_optimization
        if screen_optimization is None
        else screen_optimization
    )
    canonical_mode = normalize_mode(mode)
    captured_file = Path(captured_path)
    processed_file = Path(processed_path)
    preprocess_warnings: tuple[str, ...] = ()

    try:
        detect_screen, enhance_text = resolve_preprocess_options(
            mode=canonical_mode,
            screen_optimization=resolved_screen_optimization,
        )
    except ValueError as exc:
        raise PipelineError(str(exc)) from exc

    if not captured_file.is_file() and not processed_file.is_file():
        LOGGER.error(
            "Analyze failed before request because no image was available captured=%s processed=%s",
            captured_file,
            processed_file,
        )
        raise PipelineError("No image available. Please capture an image first.")

    final_processed_path = processed_file
    if captured_file.is_file() and not is_processed_fresh(
        captured_file,
        processed_file,
        grayscale=resolved_grayscale,
        max_dimension=resolved_max_dimension,
        detect_screen=detect_screen,
        enhance_text=enhance_text,
    ):
        preprocess_result = run_preprocess(
            input_path=str(captured_file),
            output_path=str(processed_file),
            mode=canonical_mode,
            grayscale=resolved_grayscale,
            max_dimension=resolved_max_dimension,
            screen_optimization=resolved_screen_optimization,
            status_callback=status_callback,
        )
        final_processed_path = preprocess_result.processed_path or processed_file
        preprocess_warnings = preprocess_result.warnings
    elif not processed_file.is_file() and captured_file.is_file():
        preprocess_result = run_preprocess(
            input_path=str(captured_file),
            output_path=str(processed_file),
            mode=canonical_mode,
            grayscale=resolved_grayscale,
            max_dimension=resolved_max_dimension,
            screen_optimization=resolved_screen_optimization,
            status_callback=status_callback,
        )
        final_processed_path = preprocess_result.processed_path or processed_file
        preprocess_warnings = preprocess_result.warnings

    try:
        from ai.openai_client import OpenAIVisionClient, VisionClientError
    except ImportError as exc:
        LOGGER.error("OpenAI SDK import failed", exc_info=True)
        raise PipelineError(
            "OpenAI SDK is not installed. Activate your virtual environment and run: pip install -r requirements.txt"
        ) from exc

    try:
        client = OpenAIVisionClient()
        LOGGER.info(
            "AI analysis started mode=%s captured=%s processed=%s",
            canonical_mode,
            captured_file,
            final_processed_path,
        )
        _emit_status(status_callback, "Sending image to OpenAI Vision...")
        request_started = time.monotonic()
        answer = client.analyze_image(
            image_path=str(final_processed_path),
            mode=canonical_mode,
        )
        request_duration_seconds = time.monotonic() - request_started
    except VisionClientError as exc:
        LOGGER.error("AI analysis failed: %s", exc, exc_info=True)
        raise PipelineError(
            str(exc),
            retryable=bool(getattr(exc, "retryable", False)),
            captured_path=captured_file if captured_file.is_file() else None,
            processed_path=final_processed_path if final_processed_path.is_file() else None,
            mode=canonical_mode,
        ) from exc

    LOGGER.info(
        "AI analysis succeeded mode=%s answer_chars=%s",
        canonical_mode,
        len(answer),
    )

    return PipelineResult(
        captured_path=captured_file if captured_file.is_file() else None,
        processed_path=final_processed_path if final_processed_path.is_file() else None,
        answer=answer,
        mode=canonical_mode,
        camera_backend_used=None,
        camera_resolution=None,
        status="success",
        warnings=preprocess_warnings,
        model_used=getattr(client, "last_model_used", None),
        duration_seconds=round(request_duration_seconds, 3),
    )


def run_capture_analyze(
    mode: str,
    backend: str | None = None,
    camera_index: int | None = None,
    width: int | None = None,
    height: int | None = None,
    captured_path: str = str(DEFAULT_CAPTURED_PATH),
    processed_path: str = str(DEFAULT_PROCESSED_PATH),
    grayscale: bool | None = None,
    max_dimension: int | None = None,
    screen_optimization: str | None = None,
    autofocus_mode: str | None = None,
    exposure: str | int | None = None,
    brightness: float | None = None,
    capture_delay_seconds: float | None = None,
    status_callback: StatusCallback | None = None,
) -> PipelineResult:
    """Run the full capture -> preprocess -> analyze pipeline."""
    LOGGER.info("Full capture-analyze pipeline started mode=%s", mode)
    capture_result = run_capture(
        output_path=captured_path,
        backend=backend,
        camera_index=camera_index,
        width=width,
        height=height,
        autofocus_mode=autofocus_mode,
        exposure=exposure,
        brightness=brightness,
        capture_delay_seconds=capture_delay_seconds,
        status_callback=status_callback,
    )
    preprocess_result = run_preprocess(
        input_path=str(capture_result.captured_path or captured_path),
        output_path=processed_path,
        mode=mode,
        grayscale=grayscale,
        max_dimension=max_dimension,
        screen_optimization=screen_optimization,
        status_callback=status_callback,
    )
    try:
        analyze_result = run_analyze(
            mode=mode,
            captured_path=str(capture_result.captured_path or captured_path),
            processed_path=str(preprocess_result.processed_path or processed_path),
            grayscale=grayscale,
            max_dimension=max_dimension,
            screen_optimization=screen_optimization,
            status_callback=status_callback,
        )
    except PipelineError as exc:
        raise exc.attach_context(
            captured_path=capture_result.captured_path or captured_path,
            processed_path=preprocess_result.processed_path or processed_path,
            mode=normalize_mode(mode),
            camera_backend_used=capture_result.camera_backend_used,
            camera_resolution=capture_result.camera_resolution,
        )

    LOGGER.info(
        "Full capture-analyze pipeline succeeded mode=%s backend=%s",
        analyze_result.mode,
        capture_result.camera_backend_used,
    )

    return PipelineResult(
        captured_path=capture_result.captured_path,
        processed_path=preprocess_result.processed_path,
        answer=analyze_result.answer,
        mode=analyze_result.mode,
        camera_backend_used=capture_result.camera_backend_used,
        camera_resolution=capture_result.camera_resolution,
        status="success",
        warnings=(
            *capture_result.warnings,
            *preprocess_result.warnings,
            *analyze_result.warnings,
        ),
    )


def save_latest_result(
    result: PipelineResult,
    output_path: str = str(DEFAULT_RESULT_PATH),
) -> Path:
    """Save the latest pipeline result as a readable multi-line text file."""
    result_path = Path(output_path)
    result_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        display_mode = normalize_mode(result.mode)
    except ValueError:
        display_mode = result.mode

    lines = [
        f"Timestamp: {timestamp}",
        f"Mode: {display_mode}",
        f"Status: {result.status}",
        f"Model: {result.model_used or 'n/a'}",
        f"Duration seconds: {result.duration_seconds if result.duration_seconds is not None else 'n/a'}",
        f"Camera backend: {result.camera_backend_used or 'n/a'}",
        f"Camera resolution: {_format_resolution(result.camera_resolution)}",
        f"Captured image: {result.captured_path or 'n/a'}",
        f"Processed image: {result.processed_path or 'n/a'}",
        "",
    ]

    if result.warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in result.warnings)
        lines.append("")

    if result.status == "success":
        lines.append(f"Answer: {result.answer or ''}")
    elif result.status == "queued":
        lines.append(f"Message: {result.answer or 'Saved for retry'}")
    else:
        lines.append(f"Error: {result.answer or 'Unknown error'}")

    atomic_write_text(result_path, "\n".join(lines) + "\n", encoding="utf-8")
    LOGGER.info("Saved latest pipeline result to %s with status=%s", result_path, result.status)
    return result_path


def _emit_status(status_callback: StatusCallback | None, message: str) -> None:
    """Send a status update to any caller that wants human-readable progress output."""
    if status_callback is not None:
        status_callback(message)


def _format_resolution(resolution: tuple[int, int] | None) -> str:
    """Format a camera resolution tuple for result files."""
    if resolution is None:
        return "n/a"
    return f"{resolution[0]}x{resolution[1]}"
