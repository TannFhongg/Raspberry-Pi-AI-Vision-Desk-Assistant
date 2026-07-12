"""Checks for the native Qt systemd service template."""

from __future__ import annotations

from pathlib import Path


def test_qt_service_sets_display_environment() -> None:
    service_text = Path("deployment/visiondesk-qt.service").read_text(encoding="utf-8")

    assert "Environment=DISPLAY=:0" in service_text
    assert "Environment=XDG_RUNTIME_DIR=/run/user/1000" in service_text
    assert "Environment=XAUTHORITY=/home/pi/.Xauthority" in service_text
    assert "Environment=QT_QPA_PLATFORM=xcb" in service_text


def test_qt_service_runs_qt_entrypoint_and_restarts() -> None:
    service_text = Path("deployment/visiondesk-qt.service").read_text(encoding="utf-8")

    assert "ExecStart=/home/pi/raspberry-pi-ai-vision-assistant/.venv/bin/python -m qt_app.main" in service_text
    assert "Restart=always" in service_text
    assert "RestartSec=3" in service_text


def test_qt_deployment_is_the_only_remaining_ui_service_template() -> None:
    assert Path("deployment/visiondesk-qt.service").is_file()
    assert not Path("deployment/ai-vision-assistant.service").exists()
    assert not Path("deployment/kiosk-launch.sh").exists()
    assert not Path("deployment/labwc-autostart.example").exists()
