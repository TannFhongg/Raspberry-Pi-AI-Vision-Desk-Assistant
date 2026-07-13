"""Production and development filesystem layout helpers for VisionDesk."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

DEFAULT_PATH_MODE = "development"
VALID_PATH_MODES = frozenset({"development", "production"})
_DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent
_PRODUCTION_APP_ROOT = Path("/opt/visiondesk/current")
_PRODUCTION_RELEASES_DIR = Path("/opt/visiondesk/releases")
_PRODUCTION_CONFIG_DIR = Path("/etc/visiondesk")
_PRODUCTION_DATA_DIR = Path("/var/lib/visiondesk")
_PRODUCTION_LOG_DIR = Path("/var/log/visiondesk")
_DEFAULT_ENV_FILE_NAME = "visiondesk.env"
_DEFAULT_CONFIG_FILE_NAME = "device.yaml"


def _coerce_mode(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in VALID_PATH_MODES:
        return normalized
    return DEFAULT_PATH_MODE


@dataclass(frozen=True, slots=True)
class VisionDeskPaths:
    """Resolved application paths for either development or production."""

    path_mode: str
    repo_root: Path
    app_root: Path
    releases_dir: Path
    current_release_link: Path
    config_dir: Path
    config_path: Path
    data_dir: Path
    logs_dir: Path
    env_file_path: Path

    @property
    def setup_state_path(self) -> Path:
        return self.data_dir / "setup_state.json"

    @property
    def health_status_path(self) -> Path:
        return self.data_dir / "health_status.json"

    @property
    def latest_result_path(self) -> Path:
        return self.data_dir / "latest_result.txt"

    @property
    def result_history_path(self) -> Path:
        return self.data_dir / "result_history.json"

    @property
    def private_data_path(self) -> Path:
        return self.data_dir / "private"

    @property
    def private_current_path(self) -> Path:
        return self.private_data_path / "current"

    @property
    def private_retry_path(self) -> Path:
        return self.private_data_path / "retry"

    @property
    def private_quarantine_path(self) -> Path:
        return self.private_data_path / "quarantine"

    @property
    def private_cache_path(self) -> Path:
        return self.private_data_path / "cache"

    @property
    def private_debug_path(self) -> Path:
        return self.private_data_path / "debug"

    @property
    def offline_retry_queue_path(self) -> Path:
        return self.private_data_path / "retry_queue.json"

    @property
    def reset_marker_path(self) -> Path:
        return self.data_dir / "factory_reset_state.json"

    @property
    def readiness_path(self) -> Path:
        return self.data_dir / "runtime" / "readiness.json"

    @property
    def debug_dir(self) -> Path:
        if self.path_mode == "production":
            return self.data_dir / "debug"
        return self.repo_root / "debug"


def resolve_visiondesk_paths(
    *,
    env: Mapping[str, str] | None = None,
    mode: str | None = None,
) -> VisionDeskPaths:
    """Resolve the active filesystem layout for the current process."""
    environment = dict(os.environ if env is None else env)
    resolved_mode = _coerce_mode(mode or environment.get("VISIONDESK_PATH_MODE"))

    repo_root = Path(environment.get("VISIONDESK_REPO_ROOT", _DEFAULT_REPO_ROOT))
    app_root = (
        Path(environment.get("VISIONDESK_APP_DIR", _PRODUCTION_APP_ROOT))
        if resolved_mode == "production"
        else repo_root
    )
    releases_dir = Path(environment.get("VISIONDESK_RELEASES_DIR", _PRODUCTION_RELEASES_DIR))

    default_config_dir = (
        Path(environment.get("VISIONDESK_CONFIG_DIR", _PRODUCTION_CONFIG_DIR))
        if resolved_mode == "production"
        else repo_root / "config"
    )
    config_path = Path(
        environment.get("DEVICE_CONFIG_PATH", default_config_dir / _DEFAULT_CONFIG_FILE_NAME)
    )
    config_dir = config_path.parent

    env_file_default = (
        default_config_dir / _DEFAULT_ENV_FILE_NAME
        if resolved_mode == "production"
        else repo_root / ".env"
    )
    env_file_path = Path(environment.get("VISIONDESK_ENV_FILE", env_file_default))

    data_dir_default = (
        Path(environment.get("VISIONDESK_DATA_DIR", _PRODUCTION_DATA_DIR))
        if resolved_mode == "production"
        else repo_root / "data"
    )
    data_dir = Path(environment.get("VISIONDESK_DATA_DIR", data_dir_default))

    logs_dir_default = (
        Path(environment.get("VISIONDESK_LOG_DIR", _PRODUCTION_LOG_DIR))
        if resolved_mode == "production"
        else repo_root / "logs"
    )
    logs_dir = Path(environment.get("VISIONDESK_LOG_DIR", logs_dir_default))

    return VisionDeskPaths(
        path_mode=resolved_mode,
        repo_root=repo_root,
        app_root=app_root,
        releases_dir=releases_dir,
        current_release_link=app_root if resolved_mode == "production" else repo_root,
        config_dir=config_dir,
        config_path=config_path,
        data_dir=data_dir,
        logs_dir=logs_dir,
        env_file_path=env_file_path,
    )
