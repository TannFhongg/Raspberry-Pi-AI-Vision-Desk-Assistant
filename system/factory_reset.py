"""Shared factory-reset helpers for the VisionDesk appliance."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from config import DeviceSettings, load_device_settings
from system.device_setup import remove_env_value
from system.storage import atomic_write_json, atomic_write_text, safe_rmtree, safe_unlink
from visiondesk.paths import VisionDeskPaths, resolve_visiondesk_paths
from visiondesk.version import __version__

CONFIGURATION_RESET = "configuration"
USER_DATA_RESET = "user_data"
FULL_FACTORY_RESET = "factory_reset"
RESET_MODES = (CONFIGURATION_RESET, USER_DATA_RESET, FULL_FACTORY_RESET)
CONFIRMATION_PHRASE = "ERASE VISIONDESK"


class FactoryResetError(Exception):
    """Raised when a factory reset operation cannot complete safely."""


class FactoryResetExecutionGuard:
    """Permit a reset operation to run once for a single CLI invocation."""

    def __init__(self) -> None:
        self._executed = False

    def execute(self, operation: Callable[[], FactoryResetSummary]) -> FactoryResetSummary:
        """Run the destructive operation once and reject duplicate execution."""
        if self._executed:
            raise FactoryResetError("Factory reset execution was already requested for this invocation.")
        self._executed = True
        return operation()


@dataclass(slots=True)
class FactoryResetSummary:
    """Public summary returned by planned or completed reset operations."""

    mode: str
    removed_wifi_profile: bool
    removed_paths: list[str]
    preserved_paths: list[str]
    app_version: str
    setup_required: bool
    dry_run: bool = False


def _timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write_reset_marker(
    marker_path: str | Path,
    *,
    mode: str,
    remove_wifi_profile: bool,
    status: str,
    error: str = "",
) -> Path:
    payload = {
        "schema_version": 1,
        "mode": mode,
        "remove_wifi_profile": bool(remove_wifi_profile),
        "status": status,
        "error": str(error or ""),
        "updated_at": _timestamp(),
        "app_version": __version__,
    }
    return atomic_write_json(marker_path, payload, ensure_ascii=True, indent=2)


def load_reset_marker(marker_path: str | Path) -> dict[str, Any] | None:
    path = Path(marker_path)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def clear_reset_marker(marker_path: str | Path) -> None:
    safe_unlink(marker_path)


def _write_incomplete_setup_state(paths: VisionDeskPaths) -> None:
    payload = {
        "schema_version": 1,
        "setup_complete": False,
        "completed_at": "",
        "app_version": "",
        "current_step": "welcome",
        "warnings_acknowledged": False,
        "finish_message": "",
        "updated_at": _timestamp(),
        "steps": {
            "welcome": {"status": "idle", "message": "", "checks": []},
            "wifi": {"status": "idle", "message": ""},
            "openai": {"status": "idle", "message": ""},
            "camera": {"status": "idle", "message": ""},
            "gpio": {"status": "idle", "message": ""},
            "finish": {"status": "idle", "message": ""},
        },
        "wifi": {
            "scan_status": "idle",
            "connect_status": "idle",
            "available_networks": [],
            "ssid": "",
            "connection_name": "",
            "message": "",
            "auto_connect": True,
            "managed_by": "nmcli",
        },
        "openai": {
            "status": "idle",
            "key_present": False,
            "api_key_verified": False,
            "message": "",
        },
        "camera": {
            "status": "idle",
            "message": "",
        },
        "gpio": {
            "status": "idle",
            "message": "",
            "active": False,
            "required": [],
            "pressed_labels": [],
            "all_pressed": False,
            "validation_issues": [],
        },
    }
    atomic_write_json(paths.setup_state_path, payload, ensure_ascii=False, indent=2)


def _restore_default_config(
    *,
    config_path: str | Path,
    default_config_source: str | Path,
) -> None:
    source = Path(default_config_source)
    destination = Path(config_path)
    if not source.is_file():
        raise FactoryResetError(f"Default config template is missing: '{source}'.")
    content = source.read_text(encoding="utf-8")
    if content and not content.endswith("\n"):
        content += "\n"
    atomic_write_text(destination, content, encoding="utf-8")


def _clear_user_data(paths: VisionDeskPaths) -> None:
    targets = [
        paths.private_current_path,
        paths.private_retry_path,
        paths.private_cache_path,
        paths.private_quarantine_path,
    ]
    for target in targets:
        if target.exists():
            safe_rmtree(target)
    for file_path in (
        paths.result_history_path,
        paths.latest_result_path,
        paths.offline_retry_queue_path,
    ):
        if file_path.exists():
            safe_unlink(file_path)

    paths.private_data_path.mkdir(parents=True, exist_ok=True)
    paths.private_quarantine_path.mkdir(parents=True, exist_ok=True)


def _forget_wifi_profile(settings: DeviceSettings, *, runner=subprocess.run) -> bool:
    connection_name = str(settings.network.wifi.connection_name or settings.network.wifi.ssid).strip()
    if not connection_name:
        return False
    try:
        completed = runner(
            ["nmcli", "connection", "delete", connection_name],
            check=False,
            capture_output=True,
            text=True,
            timeout=15.0,
        )
    except FileNotFoundError as exc:
        raise FactoryResetError("NetworkManager (nmcli) is unavailable.") from exc
    except subprocess.TimeoutExpired as exc:
        raise FactoryResetError("Timed out while removing the saved Wi-Fi profile.") from exc
    except OSError as exc:
        raise FactoryResetError(f"Could not remove the saved Wi-Fi profile. {exc}") from exc

    if completed.returncode != 0:
        raise FactoryResetError(
            completed.stderr.strip()
            or completed.stdout.strip()
            or f"Could not remove Wi-Fi profile '{connection_name}'."
        )
    return True


def plan_factory_reset(
    *,
    mode: str,
    paths: VisionDeskPaths | None = None,
    remove_wifi_profile: bool = False,
) -> FactoryResetSummary:
    """Describe which locations a reset mode will touch."""
    if mode not in RESET_MODES:
        expected = ", ".join(RESET_MODES)
        raise FactoryResetError(f"Unsupported factory reset mode '{mode}'. Expected one of: {expected}.")
    if remove_wifi_profile and mode != FULL_FACTORY_RESET:
        raise FactoryResetError("Wi-Fi profile removal is only supported during full factory reset.")

    resolved_paths = paths or resolve_visiondesk_paths()
    removed_paths: list[str] = []

    if mode in {CONFIGURATION_RESET, FULL_FACTORY_RESET}:
        removed_paths.extend(
            [
                str(resolved_paths.env_file_path),
                str(resolved_paths.config_path),
                str(resolved_paths.setup_state_path),
            ]
        )
    if mode in {USER_DATA_RESET, FULL_FACTORY_RESET}:
        removed_paths.extend(
            [
                str(resolved_paths.private_current_path),
                str(resolved_paths.private_retry_path),
                str(resolved_paths.private_cache_path),
                str(resolved_paths.private_quarantine_path),
                str(resolved_paths.result_history_path),
                str(resolved_paths.latest_result_path),
                str(resolved_paths.offline_retry_queue_path),
            ]
        )

    preserved_paths = [
        str(resolved_paths.app_root),
        str(resolved_paths.releases_dir),
        str(resolved_paths.logs_dir),
    ]
    if mode == USER_DATA_RESET:
        preserved_paths.extend(
            [
                str(resolved_paths.env_file_path),
                str(resolved_paths.config_path),
                str(resolved_paths.setup_state_path),
            ]
        )

    return FactoryResetSummary(
        mode=mode,
        removed_wifi_profile=bool(remove_wifi_profile),
        removed_paths=sorted(set(removed_paths)),
        preserved_paths=sorted(set(preserved_paths)),
        app_version=__version__,
        setup_required=mode in {CONFIGURATION_RESET, FULL_FACTORY_RESET},
    )


def perform_factory_reset(
    *,
    mode: str,
    paths: VisionDeskPaths | None = None,
    settings: DeviceSettings | None = None,
    remove_wifi_profile: bool = False,
    dry_run: bool = False,
    runner=subprocess.run,
) -> FactoryResetSummary:
    """Run one of the supported factory-reset modes."""
    resolved_paths = paths or resolve_visiondesk_paths()
    summary = plan_factory_reset(
        mode=mode,
        paths=resolved_paths,
        remove_wifi_profile=remove_wifi_profile,
    )
    if dry_run:
        summary.dry_run = True
        return summary

    resolved_settings = settings or load_device_settings(config_path=resolved_paths.config_path)
    default_config_source = resolved_paths.app_root / "config" / "device.yaml"
    removed_wifi = False

    write_reset_marker(
        resolved_paths.reset_marker_path,
        mode=mode,
        remove_wifi_profile=remove_wifi_profile,
        status="pending",
    )

    try:
        if mode in {CONFIGURATION_RESET, FULL_FACTORY_RESET}:
            remove_env_value(resolved_paths.env_file_path, "OPENAI_API_KEY")
            os.environ.pop("OPENAI_API_KEY", None)
            _restore_default_config(
                config_path=resolved_paths.config_path,
                default_config_source=default_config_source,
            )
            _write_incomplete_setup_state(resolved_paths)
            if remove_wifi_profile:
                removed_wifi = _forget_wifi_profile(resolved_settings, runner=runner)

        if mode in {USER_DATA_RESET, FULL_FACTORY_RESET}:
            _clear_user_data(resolved_paths)

        clear_reset_marker(resolved_paths.reset_marker_path)
        summary.removed_wifi_profile = removed_wifi
        return summary
    except Exception as exc:
        write_reset_marker(
            resolved_paths.reset_marker_path,
            mode=mode,
            remove_wifi_profile=remove_wifi_profile,
            status="failed",
            error=str(exc),
        )
        if isinstance(exc, FactoryResetError):
            raise
        raise FactoryResetError(str(exc)) from exc


def resume_pending_factory_reset(
    *,
    paths: VisionDeskPaths | None = None,
    settings: DeviceSettings | None = None,
    runner=subprocess.run,
) -> FactoryResetSummary | None:
    """Resume a previously interrupted factory reset if a recovery marker exists."""
    resolved_paths = paths or resolve_visiondesk_paths()
    marker = load_reset_marker(resolved_paths.reset_marker_path)
    if marker is None or marker.get("status") not in {"pending", "failed"}:
        return None
    return perform_factory_reset(
        mode=str(marker.get("mode", CONFIGURATION_RESET)),
        paths=resolved_paths,
        settings=settings,
        remove_wifi_profile=bool(marker.get("remove_wifi_profile", False)),
        runner=runner,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Factory reset VisionDesk without uninstalling it.")
    parser.add_argument("--mode", choices=RESET_MODES, required=True)
    parser.add_argument("--remove-wifi", action="store_true", help="Also delete the saved Wi-Fi connection profile.")
    parser.add_argument("--yes", action="store_true", help="Skip interactive confirmation.")
    parser.add_argument(
        "--phrase",
        default="",
        help=f"Safety phrase for full factory reset. Required value: '{CONFIRMATION_PHRASE}'.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show affected locations without deleting anything.")
    parser.add_argument("--json", action="store_true", help="Print the final summary as JSON.")
    return parser


def _print_summary(summary: FactoryResetSummary, *, planned: bool = False) -> None:
    verb = "Would modify" if summary.dry_run else ("Will modify" if planned else "Removed or reset")
    print(f"Factory reset mode: {summary.mode}")
    for path in summary.removed_paths:
        print(f"{verb}: {path}")
    for path in summary.preserved_paths:
        print(f"Preserved: {path}")
    if summary.removed_wifi_profile:
        print("Wi-Fi profile: saved profile will also be removed.")
    if summary.setup_required:
        print("Next launch: Setup Wizard will be required.")


def _confirm_reset() -> bool:
    """Request explicit confirmation without allowing EOF to trigger a reset."""
    try:
        return input("Type YES to continue: ").strip() == "YES"
    except EOFError:
        print("Factory reset cancelled because confirmation input was unavailable.")
        return False


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint used by factory-reset.sh and manual recovery flows."""
    args = _build_parser().parse_args(argv)

    if args.mode == FULL_FACTORY_RESET and args.phrase != CONFIRMATION_PHRASE:
        print(f"Full factory reset requires --phrase '{CONFIRMATION_PHRASE}'.")
        return 1

    summary = plan_factory_reset(
        mode=args.mode,
        remove_wifi_profile=args.remove_wifi,
    )
    if args.dry_run:
        summary.dry_run = True
        if args.json:
            print(json.dumps(asdict(summary), ensure_ascii=True, indent=2))
        else:
            _print_summary(summary)
        return 0

    if not args.json:
        _print_summary(summary, planned=True)
    if not args.yes and not _confirm_reset():
        print("Factory reset cancelled.")
        return 1

    executor = FactoryResetExecutionGuard()
    summary = executor.execute(
        lambda: perform_factory_reset(
            mode=args.mode,
            remove_wifi_profile=args.remove_wifi,
        )
    )
    if args.json:
        print(json.dumps(asdict(summary), ensure_ascii=True, indent=2))
    else:
        print("Factory reset completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
