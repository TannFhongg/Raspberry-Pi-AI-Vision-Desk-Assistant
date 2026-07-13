"""Tests for safe, stable backend-to-QML error mapping."""

from __future__ import annotations

import pytest

from system.error_mapping import map_public_error, redact_technical_detail


@pytest.mark.parametrize(
    ("detail", "code", "can_retry"),
    [
        ("camera device busy", "CAMERA_BUSY", True),
        ("camera device unavailable", "CAMERA_UNAVAILABLE", True),
        ("network connection offline", "NETWORK_OFFLINE", True),
        ("OpenAI request timed out", "OPENAI_TIMEOUT", True),
        ("OpenAI rate limit 429", "OPENAI_RATE_LIMIT", True),
        ("invalid API key 401", "INVALID_API_KEY", False),
        ("disk full ENOSPC", "DISK_FULL", False),
        ("offline retry queue full", "RETRY_QUEUE_FULL", False),
        ("preprocess image failed", "PROCESSING_FAILED", False),
        ("unrecognized backend failure", "UNKNOWN_ERROR", False),
    ],
)
def test_common_backend_failures_map_to_stable_public_codes(detail, code, can_retry) -> None:
    mapped = map_public_error(detail)

    assert mapped.code == code
    assert mapped.can_retry is can_retry
    assert mapped.message


def test_mapping_never_uses_raw_traceback_paths_or_api_keys() -> None:
    raw_detail = (
        "Traceback: request failed for sk-proj-super-secret at "
        "C:\\Users\\Admin\\VisionDesk\\private\\image.jpg and /var/lib/visiondesk/private/image.jpg"
    )
    mapped = map_public_error(raw_detail)
    redacted = redact_technical_detail(raw_detail)

    public_text = f"{mapped.title} {mapped.message} {mapped.code}"
    assert "Traceback" not in public_text
    assert "sk-proj" not in public_text
    assert "C:\\Users" not in public_text
    assert "/var/lib" not in public_text
    assert "sk-proj-super-secret" not in redacted
    assert "C:\\Users" not in redacted
    assert "/var/lib" not in redacted
