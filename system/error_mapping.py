"""Map internal failures to stable, safe messages for the Qt interface."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PublicError:
    """The only error fields allowed to cross from backend logic into QML."""

    title: str
    message: str
    code: str
    can_retry: bool


_API_KEY_PATTERN = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]+\b")
_WINDOWS_PATH_PATTERN = re.compile(r"[A-Za-z]:\\[^\s'\"]+")
_UNIX_PATH_PATTERN = re.compile(r"(?<!\w)/(?:[^\s'\"]+/)+[^\s'\"]*")


def redact_technical_detail(detail: object) -> str:
    """Redact secrets and local paths before technical detail is logged."""
    redacted = str(detail or "")
    redacted = _API_KEY_PATTERN.sub("[REDACTED_API_KEY]", redacted)
    redacted = _WINDOWS_PATH_PATTERN.sub("[REDACTED_PATH]", redacted)
    return _UNIX_PATH_PATTERN.sub("[REDACTED_PATH]", redacted)


def map_public_error(detail: object, *, retryable: bool = False) -> PublicError:
    """Return a stable public error without exposing backend detail."""
    normalized = str(detail or "").lower()
    if "camera" in normalized and ("busy" in normalized or "exclusive camera" in normalized):
        return PublicError(
            "Camera is busy",
            "The camera is still in use. Wait a moment, then try capture again.",
            "CAMERA_BUSY",
            True,
        )
    if "camera" in normalized or "opencv" in normalized or "video capture" in normalized:
        return PublicError(
            "Camera unavailable",
            "VisionDesk could not access the camera. Check the camera connection and try again.",
            "CAMERA_UNAVAILABLE",
            True,
        )
    if "rate limit" in normalized or "429" in normalized:
        return PublicError(
            "Service is busy",
            "The AI service is busy right now. Please try again shortly.",
            "OPENAI_RATE_LIMIT",
            True,
        )
    if "timeout" in normalized or "timed out" in normalized:
        return PublicError(
            "Request timed out",
            "The AI service took too long to respond. Check your connection and try again.",
            "OPENAI_TIMEOUT",
            True,
        )
    if any(
        token in normalized
        for token in ("invalid api", "api key", "api rejected", "authentication", "unauthorized", "401")
    ):
        return PublicError(
            "API key needs attention",
            "The configured AI API key could not be accepted. Update it in Setup and try again.",
            "INVALID_API_KEY",
            False,
        )
    if "retry" in normalized and "queue" in normalized and "full" in normalized:
        return PublicError(
            "Retry queue is full",
            "Saved retry storage is full. Wait for queued work to finish or clear local data.",
            "RETRY_QUEUE_FULL",
            False,
        )
    if any(token in normalized for token in ("network", "connection", "internet", "dns", "offline")):
        return PublicError(
            "Network unavailable",
            "VisionDesk could not reach the AI service. Check the network connection and try again.",
            "NETWORK_OFFLINE",
            True,
        )
    if any(token in normalized for token in ("disk full", "no space", "enospc")):
        return PublicError(
            "Storage is full",
            "VisionDesk needs free storage before it can continue. Clear space and try again.",
            "DISK_FULL",
            False,
        )
    if any(token in normalized for token in ("preprocess", "processing", "image")):
        return PublicError(
            "Image processing failed",
            "VisionDesk could not prepare this image. Try capturing it again.",
            "PROCESSING_FAILED",
            bool(retryable),
        )
    return PublicError(
        "Something went wrong",
        "VisionDesk could not complete that request. Try again when ready.",
        "UNKNOWN_ERROR",
        bool(retryable),
    )
