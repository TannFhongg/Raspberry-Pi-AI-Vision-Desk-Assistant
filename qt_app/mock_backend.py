"""Mock backend services used by the Qt app in development and tests."""

from __future__ import annotations

import io
import threading
import time
from pathlib import Path

from PIL import Image, ImageDraw

from pipeline.runner import PipelineResult


def build_mock_preview_bytes(
    *,
    title: str,
    subtitle: str,
    size: tuple[int, int] = (960, 540),
    background: str = "#d9d9d9",
) -> bytes:
    """Return a simple JPEG placeholder used by mock preview and result flows."""
    image = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 24, size[0] - 24, size[1] - 24), radius=28, outline="#111111", width=4)
    draw.text((48, 54), title, fill="#111111")
    draw.text((48, 104), subtitle, fill="#333333")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88)
    return buffer.getvalue()


class MockLivePreviewService:
    """Small in-memory live-preview replacement for `--mock-hardware` mode."""

    def __init__(self, *, width: int = 960, height: int = 540) -> None:
        self._lock = threading.Lock()
        self._active = False
        self._recent = False
        self._last_error = ""
        self._size = (max(1, width), max(1, height))
        self._frame = build_mock_preview_bytes(
            title="Preview Image Here",
            subtitle="Mock hardware mode is running.",
            size=self._size,
        )
        self._last_success_monotonic = time.monotonic()

    def get_jpeg_frame(self, timeout_seconds: float = 1.0) -> bytes:
        del timeout_seconds
        with self._lock:
            self._recent = self._active
            self._last_success_monotonic = time.monotonic()
            return self._frame

    def pause(self, timeout_seconds: float = 2.0) -> bool:
        del timeout_seconds
        with self._lock:
            self._active = False
            self._recent = False
        return True

    def resume(self) -> None:
        with self._lock:
            self._active = True
            self._recent = True
            self._frame = build_mock_preview_bytes(
                title="Live Preview Ready",
                subtitle="Mock camera frames are updating in memory.",
                size=self._size,
            )
            self._last_success_monotonic = time.monotonic()

    def is_camera_active(self) -> bool:
        with self._lock:
            return self._active

    def has_recent_frame(self, max_age_seconds: float = 10.0) -> bool:
        with self._lock:
            if not self._recent:
                return False
            return (time.monotonic() - self._last_success_monotonic) <= max(0.0, max_age_seconds)

    def latest_error_message(self) -> str:
        with self._lock:
            return self._last_error

    def close(self) -> None:
        return None


def build_mock_pipeline_result(mode: str, *, answer: str | None = None) -> PipelineResult:
    """Return a deterministic pipeline result for `--mock-hardware` mode."""
    normalized_answer = answer or (
        f"# {mode.replace('_', ' ').title()}\n"
        "1. Capture completed in mock mode.\n"
        "2. The backend returned a deterministic sample answer.\n"
        "3. This path is safe for QML and controller tests."
    )
    return PipelineResult(
        captured_path=Path("data/private/current/mock-captured.jpg"),
        processed_path=Path("data/private/current/mock-processed.jpg"),
        answer=normalized_answer,
        mode=mode,
        camera_backend_used="mock-camera",
        camera_resolution=(1920, 1080),
        status="success",
        warnings=("Mock hardware mode is enabled.",),
        model_used="mock-visiondesk",
        duration_seconds=0.42,
    )

