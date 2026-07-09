"""Shared pipeline runner for camera capture, preprocessing, and AI analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from ai.prompts import normalize_mode
from config import load_device_settings
from camera import CameraCaptureError, capture_image
from vision import ImagePreprocessError, preprocess_image

DEFAULT_CAPTURED_PATH = Path("static/captured.jpg")
DEFAULT_PROCESSED_PATH = Path("static/processed.jpg")
DEFAULT_RESULT_PATH = Path("data/latest_result.txt")
StatusCallback = Callable[[str], None]


class PipelineError(Exception):
    """Friendly error raised when a pipeline step fails."""


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


def file_exists(path: str | Path) -> bool:
    """Return True when the given path exists and is a file."""
    return Path(path).is_file()


def file_mtime(path: str | Path) -> float | None:
    """Return the file modified time, or None when the file is missing."""
    file_path = Path(path)
    if not file_path.is_file():
        return None
    return file_path.stat().st_mtime


def is_processed_fresh(captured_path: str | Path, processed_path: str | Path) -> bool:
    """Return True when the processed image is current for the latest capture."""
    captured = Path(captured_path)
    processed = Path(processed_path)

    if not processed.is_file():
        return False
    if not captured.is_file():
        return True
    return processed.stat().st_mtime >= captured.stat().st_mtime


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
        raise PipelineError(str(exc)) from exc

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
    grayscale: bool | None = None,
    max_dimension: int | None = None,
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

    try:
        _emit_status(status_callback, "Preprocessing image...")
        preprocess_result = preprocess_image(
            input_path=input_path,
            output_path=output_path,
            grayscale=resolved_grayscale,
            max_dimension=resolved_max_dimension,
        )
    except ImagePreprocessError as exc:
        raise PipelineError(str(exc)) from exc

    return PipelineResult(
        captured_path=preprocess_result.input_path,
        processed_path=preprocess_result.output_path,
        answer=None,
        mode="preprocess",
        camera_backend_used=None,
        camera_resolution=None,
        status="success",
    )


def run_analyze(
    mode: str,
    captured_path: str = str(DEFAULT_CAPTURED_PATH),
    processed_path: str = str(DEFAULT_PROCESSED_PATH),
    grayscale: bool | None = None,
    max_dimension: int | None = None,
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
    canonical_mode = normalize_mode(mode)
    captured_file = Path(captured_path)
    processed_file = Path(processed_path)

    if not captured_file.is_file() and not processed_file.is_file():
        raise PipelineError("No image available. Please capture an image first.")

    final_processed_path = processed_file
    if captured_file.is_file() and not is_processed_fresh(captured_file, processed_file):
        preprocess_result = run_preprocess(
            input_path=str(captured_file),
            output_path=str(processed_file),
            grayscale=resolved_grayscale,
            max_dimension=resolved_max_dimension,
            status_callback=status_callback,
        )
        final_processed_path = preprocess_result.processed_path or processed_file
    elif not processed_file.is_file() and captured_file.is_file():
        preprocess_result = run_preprocess(
            input_path=str(captured_file),
            output_path=str(processed_file),
            grayscale=resolved_grayscale,
            max_dimension=resolved_max_dimension,
            status_callback=status_callback,
        )
        final_processed_path = preprocess_result.processed_path or processed_file

    try:
        from ai.openai_client import OpenAIVisionClient, VisionClientError
    except ImportError as exc:
        raise PipelineError(
            "OpenAI SDK is not installed. Activate your virtual environment and run: pip install -r requirements.txt"
        ) from exc

    try:
        client = OpenAIVisionClient()
        _emit_status(status_callback, "Sending image to OpenAI Vision...")
        answer = client.analyze_image(
            image_path=str(final_processed_path),
            mode=canonical_mode,
        )
    except VisionClientError as exc:
        raise PipelineError(str(exc)) from exc

    return PipelineResult(
        captured_path=captured_file if captured_file.is_file() else None,
        processed_path=final_processed_path if final_processed_path.is_file() else None,
        answer=answer,
        mode=canonical_mode,
        camera_backend_used=None,
        camera_resolution=None,
        status="success",
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
    autofocus_mode: str | None = None,
    exposure: str | int | None = None,
    brightness: float | None = None,
    capture_delay_seconds: float | None = None,
    status_callback: StatusCallback | None = None,
) -> PipelineResult:
    """Run the full capture -> preprocess -> analyze pipeline."""
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
        grayscale=grayscale,
        max_dimension=max_dimension,
        status_callback=status_callback,
    )
    analyze_result = run_analyze(
        mode=mode,
        captured_path=str(capture_result.captured_path or captured_path),
        processed_path=str(preprocess_result.processed_path or processed_path),
        grayscale=grayscale,
        max_dimension=max_dimension,
        status_callback=status_callback,
    )

    return PipelineResult(
        captured_path=capture_result.captured_path,
        processed_path=preprocess_result.processed_path,
        answer=analyze_result.answer,
        mode=analyze_result.mode,
        camera_backend_used=capture_result.camera_backend_used,
        camera_resolution=capture_result.camera_resolution,
        status="success",
        warnings=capture_result.warnings,
    )


def save_latest_result(
    result: PipelineResult,
    output_path: str = str(DEFAULT_RESULT_PATH),
) -> Path:
    """Save the latest pipeline result as a readable multi-line text file."""
    result_path = Path(output_path)
    result_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"Timestamp: {timestamp}",
        f"Mode: {result.mode}",
        f"Status: {result.status}",
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
    else:
        lines.append(f"Error: {result.answer or 'Unknown error'}")

    result_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
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
