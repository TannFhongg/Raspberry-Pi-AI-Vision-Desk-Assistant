"""Checks for the native Qt systemd service template."""

from __future__ import annotations

from pathlib import Path


def test_qt_service_sets_display_environment() -> None:
    service_text = Path("deployment/visiondesk.service").read_text(encoding="utf-8")
    launcher_text = Path("deployment/visiondesk-launch.sh").read_text(encoding="utf-8")

    assert "ExecStart=/opt/visiondesk/current/deployment/visiondesk-launch.sh" in service_text
    assert "EnvironmentFile=/etc/visiondesk/visiondesk.env" in service_text
    assert 'export DISPLAY=":0"' in launcher_text
    assert 'export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"' in launcher_text


def test_qt_service_can_see_the_host_x11_socket() -> None:
    service_text = Path("deployment/visiondesk.service").read_text(encoding="utf-8")

    assert "PrivateTmp=false" in service_text
    assert "PrivateTmp=true" not in service_text


def test_qt_service_runs_qt_entrypoint_and_restarts() -> None:
    service_text = Path("deployment/visiondesk.service").read_text(encoding="utf-8")

    assert "WorkingDirectory=/opt/visiondesk/current" in service_text
    assert "User=visiondesk" in service_text
    assert "Restart=on-failure" in service_text
    assert "RestartSec=3" in service_text
    assert "ReadWritePaths=/var/lib/visiondesk /var/log/visiondesk /etc/visiondesk" in service_text
    assert "NoNewPrivileges=true" in service_text


def test_qt_deployment_is_the_only_remaining_ui_service_template() -> None:
    assert Path("deployment/visiondesk.service").is_file()
    assert Path("deployment/visiondesk-launch.sh").is_file()
    assert not Path("deployment/visiondesk-qt.service").exists()
    assert not Path("deployment/ai-vision-assistant.service").exists()
    assert not Path("deployment/kiosk-launch.sh").exists()
    assert not Path("deployment/labwc-autostart.example").exists()
