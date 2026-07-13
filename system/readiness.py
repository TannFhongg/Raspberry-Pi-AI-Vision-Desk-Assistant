"""Non-secret application readiness markers used by the updater."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from typing import Any

from system.storage import atomic_write_json, safe_unlink

ACCEPTED_APPLICATION_STATES = frozenset({"SETUP_REQUIRED", "READY", "HOME"})
READINESS_FILE_NAME = "readiness.json"
_SENSITIVE_FIELD_TOKENS = frozenset({"api_key", "token", "secret", "password", "credential"})


def readiness_path(data_dir: str | Path) -> Path:
    """Return the persistent runtime marker path outside release directories."""
    return Path(data_dir) / "runtime" / READINESS_FILE_NAME


def write_readiness_marker(
    path: str | Path,
    *,
    version: str,
    state: str,
    qml_loaded: bool,
    config_loaded: bool = True,
    setup_state_loaded: bool = True,
    storage_writable: bool = True,
    pid: int | None = None,
    now: datetime | None = None,
) -> Path:
    """Atomically publish the minimal, non-sensitive app startup state."""
    timestamp = _utc_now(now).isoformat()
    payload = {
        "version": str(version).strip(),
        "pid": int(os.getpid() if pid is None else pid),
        "state": str(state).strip(),
        "qml_loaded": bool(qml_loaded),
        "config_loaded": bool(config_loaded),
        "setup_state_loaded": bool(setup_state_loaded),
        "storage_writable": bool(storage_writable),
        "fatal_startup": False,
        "started_at": timestamp,
        "updated_at": timestamp,
    }
    destination = Path(path)
    written = atomic_write_json(destination, payload, ensure_ascii=True, indent=2)
    try:
        os.chmod(written, 0o644)
    except OSError:
        pass
    return written


def clear_readiness_marker(path: str | Path) -> None:
    """Remove an old marker so a restarted process must publish a fresh one."""
    safe_unlink(path)


def validate_readiness_marker(
    path: str | Path,
    *,
    expected_version: str,
    expected_pid: int | None = None,
    max_age_seconds: float = 90.0,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """Validate a marker without exposing untrusted marker contents to logs."""
    marker_path = Path(path)
    try:
        import json

        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, "readiness marker is unavailable"
    if not isinstance(payload, dict):
        return False, "readiness marker is invalid"
    if any(token in str(key).lower() for key in payload for token in _SENSITIVE_FIELD_TOKENS):
        return False, "readiness marker contains disallowed fields"
    if str(payload.get("version", "")).strip() != str(expected_version).strip():
        return False, "readiness marker version does not match"
    try:
        marker_pid = int(payload.get("pid", 0))
    except (TypeError, ValueError):
        return False, "readiness marker PID is invalid"
    if marker_pid <= 0 or (expected_pid is not None and marker_pid != int(expected_pid)):
        return False, "readiness marker PID does not match"
    if str(payload.get("state", "")).strip() not in ACCEPTED_APPLICATION_STATES:
        return False, "readiness marker state is not accepted"
    if not all(
        payload.get(field) is True
        for field in ("qml_loaded", "config_loaded", "setup_state_loaded", "storage_writable")
    ):
        return False, "readiness marker startup checks are incomplete"
    if payload.get("fatal_startup") is not False:
        return False, "readiness marker reports a startup failure"
    try:
        updated_at = datetime.fromisoformat(str(payload.get("updated_at", "")).replace("Z", "+00:00"))
    except ValueError:
        return False, "readiness marker timestamp is invalid"
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    age = _utc_now(now) - updated_at.astimezone(timezone.utc)
    if age < timedelta(0) or age > timedelta(seconds=max(0.0, max_age_seconds)):
        return False, "readiness marker is stale"
    return True, "ready"


def _utc_now(value: datetime | None) -> datetime:
    now = value or datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)
