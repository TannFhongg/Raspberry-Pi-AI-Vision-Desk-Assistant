"""Tests for the non-secret application readiness marker."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from system.readiness import clear_readiness_marker, validate_readiness_marker, write_readiness_marker


def test_healthy_readiness_marker_is_current_and_contains_only_safe_fields(tmp_path) -> None:
    marker_path = tmp_path / "runtime" / "readiness.json"
    now = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)

    write_readiness_marker(
        marker_path,
        version="1.0.1",
        state="READY",
        qml_loaded=True,
        pid=4321,
        now=now,
    )

    valid, reason = validate_readiness_marker(
        marker_path,
        expected_version="1.0.1",
        expected_pid=4321,
        max_age_seconds=60,
        now=now + timedelta(seconds=10),
    )
    payload = json.loads(marker_path.read_text(encoding="utf-8"))

    assert valid is True
    assert reason == "ready"
    assert set(payload) == {
        "version",
        "pid",
        "state",
        "qml_loaded",
        "config_loaded",
        "setup_state_loaded",
        "storage_writable",
        "fatal_startup",
        "started_at",
        "updated_at",
    }
    assert not any("key" in field or "secret" in field or "token" in field for field in payload)


def test_readiness_marker_rejects_missing_wrong_version_stale_or_wrong_pid(tmp_path) -> None:
    marker_path = tmp_path / "runtime" / "readiness.json"
    now = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)

    assert validate_readiness_marker(marker_path, expected_version="1.0.1", now=now)[0] is False

    write_readiness_marker(
        marker_path,
        version="1.0.0",
        state="SETUP_REQUIRED",
        qml_loaded=True,
        pid=4321,
        now=now,
    )
    assert validate_readiness_marker(marker_path, expected_version="1.0.1", expected_pid=4321, now=now)[0] is False
    assert validate_readiness_marker(marker_path, expected_version="1.0.0", expected_pid=9999, now=now)[0] is False
    assert (
        validate_readiness_marker(
            marker_path,
            expected_version="1.0.0",
            expected_pid=4321,
            max_age_seconds=5,
            now=now + timedelta(seconds=6),
        )[0]
        is False
    )


def test_readiness_marker_rejects_sensitive_or_incomplete_payloads_and_clears_on_shutdown(tmp_path) -> None:
    marker_path = tmp_path / "runtime" / "readiness.json"
    now = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
    write_readiness_marker(
        marker_path,
        version="1.0.1",
        state="READY",
        qml_loaded=True,
        pid=4321,
        now=now,
    )
    payload = json.loads(marker_path.read_text(encoding="utf-8"))
    payload["api_key"] = "must-not-be-accepted"
    marker_path.write_text(json.dumps(payload), encoding="utf-8")

    assert validate_readiness_marker(marker_path, expected_version="1.0.1", expected_pid=4321, now=now)[0] is False

    clear_readiness_marker(marker_path)
    assert not marker_path.exists()
