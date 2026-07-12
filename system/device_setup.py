"""Helpers for first-boot device setup workflows."""

from __future__ import annotations

import subprocess
import os
from pathlib import Path
from typing import Any, Callable

from system.storage import atomic_write_text

OPENAI_KEY_PLACEHOLDER = "your_openai_api_key_here"
DEFAULT_NMCLI_TIMEOUT_SECONDS = 20.0
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


class DeviceSetupError(Exception):
    """Raised when a setup action fails."""


def has_configured_openai_key(value: str | None) -> bool:
    """Return True when an OpenAI key is present and not a placeholder."""
    if not isinstance(value, str):
        return False
    normalized = value.strip()
    if not normalized:
        return False
    return normalized != OPENAI_KEY_PLACEHOLDER


def upsert_env_value(env_path: str | Path, key: str, value: str) -> Path:
    """Atomically update or append a KEY=value line while preserving comments."""
    destination = Path(env_path)
    lines: list[str] = []
    if destination.is_file():
        lines = destination.read_text(encoding="utf-8").splitlines()

    updated = False
    next_lines: list[str] = []
    prefix = f"{key}="
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#") or not line.startswith(prefix):
            next_lines.append(line)
            continue
        next_lines.append(f"{key}={value}")
        updated = True

    if not updated:
        if next_lines and next_lines[-1] != "":
            next_lines.append("")
        next_lines.append(f"{key}={value}")

    written_path = atomic_write_text(destination, "\n".join(next_lines) + "\n", encoding="utf-8")
    try:
        os.chmod(written_path, 0o600)
    except OSError:
        pass
    return written_path


def remove_env_value(env_path: str | Path, key: str) -> Path:
    """Atomically remove a KEY=value line while preserving other content."""
    destination = Path(env_path)
    if not destination.is_file():
        return destination

    lines = destination.read_text(encoding="utf-8").splitlines()
    prefix = f"{key}="
    next_lines = [line for line in lines if line.lstrip().startswith("#") or not line.startswith(prefix)]
    written_path = atomic_write_text(destination, "\n".join(next_lines).rstrip() + "\n", encoding="utf-8")
    try:
        os.chmod(written_path, 0o600)
    except OSError:
        pass
    return written_path


def scan_wifi_networks(
    *,
    runner: CommandRunner | None = None,
    timeout_seconds: float = DEFAULT_NMCLI_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Return a de-duplicated list of nearby Wi-Fi SSIDs from nmcli."""
    completed = _run_command(
        [
            "nmcli",
            "--terse",
            "--fields",
            "SSID,SIGNAL,SECURITY",
            "device",
            "wifi",
            "list",
        ],
        runner=runner,
        timeout_seconds=timeout_seconds,
    )

    networks: dict[str, dict[str, Any]] = {}
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.rsplit(":", 2)
        if len(parts) < 3:
            continue
        ssid = parts[0].strip()
        if not ssid:
            continue
        try:
            signal = int(parts[1].strip() or "0")
        except ValueError:
            signal = 0
        security = ":".join(parts[2:]).strip() or "open"
        existing = networks.get(ssid)
        if existing is None or signal >= int(existing.get("signal", 0)):
            networks[ssid] = {
                "ssid": ssid,
                "signal": signal,
                "security": security,
            }

    return sorted(
        networks.values(),
        key=lambda item: (-int(item.get("signal", 0)), str(item.get("ssid", ""))),
    )


def connect_wifi_network(
    *,
    ssid: str,
    password: str,
    connection_name: str,
    hidden: bool = False,
    auto_connect: bool = True,
    runner: CommandRunner | None = None,
    timeout_seconds: float = DEFAULT_NMCLI_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Connect to a Wi-Fi network via nmcli and return the persisted metadata."""
    normalized_ssid = ssid.strip()
    if not normalized_ssid:
        raise DeviceSetupError("Wi-Fi SSID cannot be empty.")

    normalized_connection_name = connection_name.strip() or normalized_ssid
    connect_command = ["nmcli", "device", "wifi", "connect", normalized_ssid]
    if password.strip():
        connect_command.extend(["password", password.strip()])
    connect_command.extend(["name", normalized_connection_name])
    if hidden:
        connect_command.extend(["hidden", "yes"])

    _run_command(
        connect_command,
        runner=runner,
        timeout_seconds=timeout_seconds,
    )

    if auto_connect:
        _run_command(
            [
                "nmcli",
                "connection",
                "modify",
                normalized_connection_name,
                "connection.autoconnect",
                "yes",
            ],
            runner=runner,
            timeout_seconds=timeout_seconds,
        )

    return {
        "ssid": normalized_ssid,
        "connection_name": normalized_connection_name,
        "auto_connect": auto_connect,
        "managed_by": "nmcli",
        "message": f"Connected to Wi-Fi network '{normalized_ssid}'.",
    }


def _run_command(
    command: list[str],
    *,
    runner: CommandRunner | None,
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    """Run a setup command and normalize failures into a friendly exception."""
    command_runner = subprocess.run if runner is None else runner
    try:
        completed = command_runner(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise DeviceSetupError(f"Required setup command is unavailable: {command[0]}.") from exc
    except subprocess.TimeoutExpired as exc:
        raise DeviceSetupError(f"Setup command timed out: {' '.join(command)}") from exc
    except OSError as exc:
        raise DeviceSetupError(f"Could not run setup command '{command[0]}'. {exc}") from exc

    if completed.returncode != 0:
        error_text = completed.stderr.strip() or completed.stdout.strip() or "Unknown command failure."
        raise DeviceSetupError(error_text)
    return completed
