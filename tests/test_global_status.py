"""Tests for the single safe status shown in the global header."""

from __future__ import annotations

from system.ui_presenters import resolve_global_status


def _metric(*, state: str = "healthy", value: str = "OK") -> dict[str, str]:
    return {"state": state, "value": value}


def test_header_status_uses_priority_and_never_raw_metric_values() -> None:
    status = resolve_global_status(
        ui_state={"application_state": "READY", "error_code": ""},
        setup_complete=True,
        cpu_metric=_metric(),
        ram_metric=_metric(),
        wifi_metric=_metric(state="error", value="OFFLINE"),
        camera_metric=_metric(state="error", value="ERROR"),
    )

    assert status == {"text": "Camera unavailable", "tone": "error"}
    assert "CPU" not in status["text"]
    assert "OFFLINE" not in status["text"]


def test_header_status_prefers_setup_then_ready_when_no_problem_exists() -> None:
    common = {
        "ui_state": {"application_state": "READY", "error_code": ""},
        "cpu_metric": _metric(),
        "ram_metric": _metric(),
        "wifi_metric": _metric(),
        "camera_metric": _metric(),
    }

    assert resolve_global_status(setup_complete=False, **common)["text"] == "Setup required"
    assert resolve_global_status(setup_complete=True, **common)["text"] == "Ready"


def test_header_status_maps_ai_failure_to_safe_approved_label() -> None:
    status = resolve_global_status(
        ui_state={"application_state": "ERROR", "error_code": "OPENAI_TIMEOUT"},
        setup_complete=True,
        cpu_metric=_metric(),
        ram_metric=_metric(),
        wifi_metric=_metric(),
        camera_metric=_metric(),
    )

    assert status == {"text": "AI service unavailable", "tone": "warning"}


def test_header_status_uses_update_and_wifi_connecting_labels_only_when_higher_priorities_are_clear() -> None:
    common = {
        "setup_complete": True,
        "cpu_metric": _metric(),
        "ram_metric": _metric(),
        "wifi_metric": _metric(),
        "camera_metric": _metric(),
    }

    assert resolve_global_status(
        ui_state={"application_state": "READY", "error_code": "", "update_available": True},
        **common,
    )["text"] == "Update available"
    assert resolve_global_status(
        ui_state={"application_state": "CONNECTING_WIFI", "error_code": ""},
        **common,
    )["text"] == "Connecting to Wi-Fi"
