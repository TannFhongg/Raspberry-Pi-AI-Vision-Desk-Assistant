"""Tests for the shared VisionDesk path resolver."""

from __future__ import annotations

from pathlib import Path

from visiondesk.paths import resolve_visiondesk_paths


def test_resolve_paths_defaults_to_repo_relative_layout() -> None:
    paths = resolve_visiondesk_paths(env={})

    assert paths.path_mode == "development"
    assert paths.config_path == paths.repo_root / "config" / "device.yaml"
    assert paths.env_file_path == paths.repo_root / ".env"
    assert paths.data_dir == paths.repo_root / "data"
    assert paths.logs_dir == paths.repo_root / "logs"
    assert paths.readiness_path == paths.repo_root / "data" / "runtime" / "readiness.json"


def test_resolve_paths_honors_production_overrides() -> None:
    env = {
        "VISIONDESK_PATH_MODE": "production",
        "DEVICE_CONFIG_PATH": "/etc/visiondesk/device.yaml",
        "VISIONDESK_ENV_FILE": "/etc/visiondesk/visiondesk.env",
        "VISIONDESK_DATA_DIR": "/srv/visiondesk/data",
        "VISIONDESK_LOG_DIR": "/srv/visiondesk/logs",
        "VISIONDESK_APP_DIR": "/srv/visiondesk/current",
    }

    paths = resolve_visiondesk_paths(env=env)

    assert paths.path_mode == "production"
    assert paths.config_path == Path("/etc/visiondesk/device.yaml")
    assert paths.env_file_path == Path("/etc/visiondesk/visiondesk.env")
    assert paths.data_dir == Path("/srv/visiondesk/data")
    assert paths.logs_dir == Path("/srv/visiondesk/logs")
    assert paths.app_root == Path("/srv/visiondesk/current")
    assert paths.readiness_path == Path("/srv/visiondesk/data/runtime/readiness.json")
