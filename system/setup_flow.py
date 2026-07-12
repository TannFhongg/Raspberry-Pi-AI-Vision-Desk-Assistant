"""Shared setup-state persistence and setup workflow helpers for Flask and Qt."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any, Callable

from system.storage import atomic_write_json, safe_unlink, quarantine_file


class SetupStateStore:
    """Persist and normalize the first-boot setup wizard state."""

    def __init__(
        self,
        *,
        state_path: str | Path,
        quarantine_dir: str | Path,
        timestamp_provider: Callable[[], str],
        setup_steps: tuple[str, ...],
        build_gpio_requirements: Callable[[], list[dict[str, Any]]],
        setup_is_complete: Callable[[], bool],
        current_wifi_ssid: Callable[[], str],
        current_wifi_connection_name: Callable[[], str],
        current_wifi_auto_connect: Callable[[], bool],
        current_wifi_managed_by: Callable[[], str],
        has_configured_openai_key: Callable[[str | None], bool],
        current_openai_key: Callable[[], str | None],
    ) -> None:
        self.state_path = Path(state_path)
        self.quarantine_dir = Path(quarantine_dir)
        self.timestamp_provider = timestamp_provider
        self.setup_steps = setup_steps
        self.build_gpio_requirements = build_gpio_requirements
        self.setup_is_complete = setup_is_complete
        self.current_wifi_ssid = current_wifi_ssid
        self.current_wifi_connection_name = current_wifi_connection_name
        self.current_wifi_auto_connect = current_wifi_auto_connect
        self.current_wifi_managed_by = current_wifi_managed_by
        self.has_configured_openai_key = has_configured_openai_key
        self.current_openai_key = current_openai_key

    def coerce_step(self, value: Any) -> str:
        """Normalize a persisted wizard step value."""
        normalized = str(value or "").strip().lower()
        if normalized in self.setup_steps:
            return normalized
        return self.setup_steps[0]

    def default_state(self) -> dict[str, Any]:
        """Return the default persisted setup-wizard state."""
        required_buttons = self.build_gpio_requirements()
        wifi_ssid = str(self.current_wifi_ssid() or "").strip()
        wifi_connected = self.setup_is_complete() and bool(wifi_ssid)
        openai_key_present = self.has_configured_openai_key(self.current_openai_key())
        openai_verified = self.setup_is_complete() and openai_key_present
        current_step = (
            "finish"
            if wifi_connected and openai_verified
            else "openai"
            if wifi_connected
            else "wifi"
        )
        return {
            "current_step": current_step,
            "warnings_acknowledged": False,
            "finish_message": "",
            "updated_at": self.timestamp_provider(),
            "wifi": {
                "scan_status": "idle",
                "connect_status": "pass" if wifi_connected else "idle",
                "available_networks": [],
                "ssid": wifi_ssid,
                "connection_name": self.current_wifi_connection_name(),
                "message": (
                    f"Connected to Wi-Fi network '{wifi_ssid}'."
                    if wifi_connected
                    else ""
                ),
                "auto_connect": self.current_wifi_auto_connect(),
                "managed_by": self.current_wifi_managed_by(),
            },
            "openai": {
                "status": "pass" if openai_verified else "idle",
                "key_present": openai_key_present,
                "message": "OpenAI API key is already configured." if openai_verified else "",
            },
            "camera": {
                "status": "idle",
                "message": "",
            },
            "gpio": {
                "status": "idle",
                "message": "",
                "active": False,
                "required": required_buttons,
                "pressed_labels": [],
                "all_pressed": False,
            },
        }

    def coerce_setup_networks(self, value: Any) -> list[dict[str, Any]]:
        """Return a normalized Wi-Fi scan result list."""
        if not isinstance(value, list):
            return []
        networks: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            ssid = str(item.get("ssid", "")).strip()
            if not ssid:
                continue
            try:
                signal = int(item.get("signal", 0))
            except (TypeError, ValueError):
                signal = 0
            security = str(item.get("security", "open")).strip() or "open"
            networks.append({"ssid": ssid, "signal": signal, "security": security})
        return networks

    def coerce_required_buttons(self, value: Any) -> list[dict[str, Any]]:
        """Return a normalized GPIO setup requirements list."""
        if not isinstance(value, list):
            return self.build_gpio_requirements()
        required: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip()
            if not label:
                continue
            try:
                pin = int(item.get("pin"))
            except (TypeError, ValueError):
                continue
            required.append(
                {
                    "label": label,
                    "pin": pin,
                    "pressed": bool(item.get("pressed", False)),
                }
            )
        return required or self.build_gpio_requirements()

    def setup_gpio_complete(self, state: dict[str, Any]) -> bool:
        """Return True when every required GPIO setup button has been pressed once."""
        gpio = state.get("gpio", {})
        required = gpio.get("required", [])
        pressed_labels = {
            str(label).strip()
            for label in gpio.get("pressed_labels", [])
            if str(label).strip()
        }
        required_labels = {
            str(item.get("label", "")).strip()
            for item in required
            if isinstance(item, dict) and str(item.get("label", "")).strip()
        }
        return bool(required_labels) and required_labels.issubset(pressed_labels)

    def coerce_state(self, raw_state: Any) -> dict[str, Any]:
        """Normalize any persisted setup state into the supported schema."""
        default_state = self.default_state()
        if not isinstance(raw_state, dict):
            return default_state

        wifi = raw_state.get("wifi", {})
        gpio = raw_state.get("gpio", {})
        normalized_state = {
            "current_step": self.coerce_step(raw_state.get("current_step")),
            "warnings_acknowledged": bool(raw_state.get("warnings_acknowledged", False)),
            "finish_message": str(raw_state.get("finish_message", "")),
            "updated_at": str(raw_state.get("updated_at", default_state["updated_at"])),
            "wifi": {
                "scan_status": str(wifi.get("scan_status", default_state["wifi"]["scan_status"])),
                "connect_status": str(
                    wifi.get("connect_status", default_state["wifi"]["connect_status"])
                ),
                "available_networks": self.coerce_setup_networks(
                    wifi.get("available_networks", [])
                ),
                "ssid": str(wifi.get("ssid", default_state["wifi"]["ssid"])).strip(),
                "connection_name": str(
                    wifi.get("connection_name", default_state["wifi"]["connection_name"])
                ).strip(),
                "message": str(wifi.get("message", "")),
                "auto_connect": bool(
                    wifi.get("auto_connect", default_state["wifi"]["auto_connect"])
                ),
                "managed_by": str(
                    wifi.get("managed_by", default_state["wifi"]["managed_by"])
                )
                or "nmcli",
            },
            "openai": {
                "status": str(raw_state.get("openai", {}).get("status", default_state["openai"]["status"])),
                "key_present": bool(
                    raw_state.get("openai", {}).get(
                        "key_present",
                        default_state["openai"]["key_present"],
                    )
                ),
                "message": str(raw_state.get("openai", {}).get("message", "")),
            },
            "camera": {
                "status": str(raw_state.get("camera", {}).get("status", default_state["camera"]["status"])),
                "message": str(raw_state.get("camera", {}).get("message", "")),
            },
            "gpio": {
                "status": str(gpio.get("status", default_state["gpio"]["status"])),
                "message": str(gpio.get("message", "")),
                "active": bool(gpio.get("active", False)),
                "required": self.coerce_required_buttons(
                    gpio.get("required", default_state["gpio"]["required"])
                ),
                "pressed_labels": sorted(
                    {
                        str(label).strip()
                        for label in gpio.get("pressed_labels", [])
                        if str(label).strip()
                    }
                ),
                "all_pressed": bool(gpio.get("all_pressed", False)),
            },
        }
        normalized_state["gpio"]["all_pressed"] = self.setup_gpio_complete(normalized_state)
        return normalized_state

    def load_state(self) -> dict[str, Any]:
        """Read the persisted setup-wizard state file."""
        default_state = self.default_state()
        if not self.state_path.is_file():
            return default_state
        try:
            raw_state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            quarantine_file(
                self.state_path,
                quarantine_dir=self.quarantine_dir,
                reason="invalid-setup-state",
            )
            return default_state
        return self.coerce_state(raw_state)

    def write_state(self, updates: dict[str, Any] | None = None) -> dict[str, Any]:
        """Persist merged setup-wizard state to disk."""
        next_state = self.load_state()
        if updates:
            merge_nested_state(next_state, updates)
        next_state["current_step"] = self.coerce_step(next_state.get("current_step"))
        next_state["updated_at"] = self.timestamp_provider()
        next_state = self.coerce_state(next_state)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(
            self.state_path,
            next_state,
            ensure_ascii=False,
            indent=2,
        )
        return next_state

    def clear_state(self) -> None:
        """Delete the persisted setup state file."""
        safe_unlink(self.state_path)

    @staticmethod
    def setup_wifi_connected(state: dict[str, Any]) -> bool:
        """Return True when setup has a successful Wi-Fi connection state."""
        wifi = state.get("wifi", {}) if isinstance(state, dict) else {}
        return str(wifi.get("connect_status", "")).strip().lower() == "pass"

    @staticmethod
    def setup_openai_verified(state: dict[str, Any]) -> bool:
        """Return True when setup has a verified OpenAI key state."""
        openai = state.get("openai", {}) if isinstance(state, dict) else {}
        return str(openai.get("status", "")).strip().lower() == "pass"

    def setup_ready_to_finish(self, state: dict[str, Any] | None = None) -> bool:
        """Return True when the setup wizard has everything required to finish."""
        current_state = self.load_state() if state is None else state
        return self.setup_wifi_connected(current_state) and self.setup_openai_verified(current_state)

    def build_warnings(self, state: dict[str, Any] | None = None) -> list[str]:
        """Return the unresolved warnings shown on the finish step."""
        current_state = self.load_state() if state is None else state
        warnings: list[str] = []
        if not self.setup_wifi_connected(current_state):
            warnings.append("Connect to Wi-Fi before finishing setup.")
        if not self.setup_openai_verified(current_state):
            warnings.append("Verify the OpenAI API key before finishing setup.")
        return warnings


def merge_nested_state(target: dict[str, Any], updates: dict[str, Any]) -> None:
    """Recursively merge nested state dictionaries in-place."""
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge_nested_state(target[key], value)
        else:
            target[key] = value


def looks_like_openai_api_key(value: str) -> bool:
    """Return True when a key matches the supported setup input formats."""
    normalized = value.strip()
    return normalized.startswith("sk-")


def mask_secret_value(value: str | None) -> str:
    """Return a commercially safe masked representation of a secret value."""
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    if normalized.startswith("sk-proj-"):
        prefix = "sk-proj-"
    elif normalized.startswith("sk-"):
        prefix = "sk-"
    else:
        prefix = normalized[: min(4, len(normalized))]
    masked_count = max(8, len(normalized) - len(prefix))
    return f"{prefix}{'*' * masked_count}"


def sync_setup_gpio_state(
    store: SetupStateStore,
    snapshot_setup_gpio_progress: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """Merge the latest GPIO setup progress into the persisted setup state."""
    state = store.load_state()
    snapshot = snapshot_setup_gpio_progress()
    pressed_labels = {
        str(label).strip()
        for label in snapshot.get("pressed_labels", [])
        if str(label).strip()
    }
    normalized_required: list[dict[str, Any]] = []
    for item in snapshot.get("required", store.build_gpio_requirements()):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        if not label:
            continue
        try:
            pin = int(item.get("pin"))
        except (TypeError, ValueError):
            continue
        normalized_required.append(
            {
                "label": label,
                "pin": pin,
                "pressed": label in pressed_labels or bool(item.get("pressed", False)),
            }
        )
    if not normalized_required:
        normalized_required = store.build_gpio_requirements()
    return store.write_state(
        {
            "gpio": {
                "status": (
                    "pass"
                    if snapshot.get("all_pressed")
                    else "running"
                    if snapshot.get("active")
                    else state["gpio"].get("status", "idle")
                ),
                "message": snapshot.get("message", state["gpio"].get("message", "")),
                "active": bool(snapshot.get("active", False)),
                "required": normalized_required,
                "pressed_labels": sorted(pressed_labels),
                "all_pressed": bool(snapshot.get("all_pressed", False)),
            }
        }
    )


def run_setup_wifi_connect(
    store: SetupStateStore,
    *,
    selected_ssid: str,
    manual_ssid: str,
    password: str,
    connection_name: str,
    connect_wifi_network: Callable[..., dict[str, Any]],
    update_device_config: Callable[[dict[str, Any]], Any],
) -> None:
    """Connect to Wi-Fi, persist metadata, and update setup state."""
    state = store.load_state()
    requested_ssid = manual_ssid.strip() or selected_ssid.strip()
    hidden = bool(manual_ssid.strip()) and requested_ssid not in {
        str(item.get("ssid", "")).strip()
        for item in state["wifi"].get("available_networks", [])
        if isinstance(item, dict)
    }
    try:
        wifi_details = connect_wifi_network(
            ssid=requested_ssid,
            password=password,
            connection_name=connection_name.strip() or requested_ssid,
            hidden=hidden,
            auto_connect=True,
        )
        update_device_config(
            {
                "network": {
                    "wifi": {
                        "ssid": wifi_details["ssid"],
                        "connection_name": wifi_details["connection_name"],
                        "auto_connect": True,
                        "managed_by": "nmcli",
                    }
                }
            }
        )
        next_step = "finish" if store.setup_openai_verified(state) else "openai"
        store.write_state(
            {
                "current_step": next_step,
                "finish_message": "",
                "wifi": {
                    "connect_status": "pass",
                    "ssid": wifi_details["ssid"],
                    "connection_name": wifi_details["connection_name"],
                    "message": wifi_details["message"],
                    "auto_connect": True,
                    "managed_by": "nmcli",
                },
            }
        )
    except Exception as exc:
        store.write_state(
            {
                "current_step": "wifi",
                "finish_message": "",
                "wifi": {
                    "connect_status": "fail",
                    "ssid": requested_ssid,
                    "connection_name": connection_name.strip() or requested_ssid,
                    "message": str(exc),
                },
            }
        )


def run_setup_openai_key(
    store: SetupStateStore,
    *,
    api_key: str,
    env_file_path: str | Path,
    upsert_env_value: Callable[[str | Path, str, str], Path],
    check_openai_reachable: Callable[[], Any],
) -> None:
    """Persist and verify the OpenAI API key for the device."""
    normalized_key = api_key.strip()
    if not store.has_configured_openai_key(normalized_key) or not looks_like_openai_api_key(normalized_key):
        store.write_state(
            {
                "current_step": "openai",
                "finish_message": "",
                "openai": {
                    "status": "fail",
                    "key_present": False,
                    "message": "Enter a valid OPENAI_API_KEY starting with sk- before continuing.",
                },
            }
        )
        return

    upsert_env_value(env_file_path, "OPENAI_API_KEY", normalized_key)
    os.environ["OPENAI_API_KEY"] = normalized_key
    state = store.load_state()
    result = check_openai_reachable()
    next_step = "finish" if result.passed and store.setup_wifi_connected(state) else "openai"
    store.write_state(
        {
            "current_step": next_step,
            "finish_message": "",
            "openai": {
                "status": "pass" if result.passed else "fail",
                "key_present": True,
                "message": result.message,
            },
        }
    )


def run_setup_camera_test(
    store: SetupStateStore,
    *,
    check_camera: Callable[[], Any],
) -> None:
    """Run the configured one-shot camera diagnostic."""
    result = check_camera()
    next_step = "gpio" if result.passed else "camera"
    store.write_state(
        {
            "current_step": next_step,
            "finish_message": "",
            "camera": {
                "status": "pass" if result.passed else "fail",
                "message": result.message,
            },
        }
    )


def finish_setup(
    store: SetupStateStore,
    *,
    update_device_config: Callable[[dict[str, Any]], Any],
    on_completed: Callable[[str], None],
) -> bool:
    """Persist setup completion and notify the caller to restart the UI process."""
    state = store.load_state()
    warnings = store.build_warnings(state)
    if warnings:
        store.write_state(
            {
                "current_step": "finish",
                "warnings_acknowledged": False,
                "finish_message": warnings[0],
            }
        )
        return False

    completion_timestamp = datetime.now().isoformat(timespec="seconds")
    update_device_config(
        {
            "setup": {
                "completed": True,
                "completed_at": completion_timestamp,
                "version": 1,
            },
            "localization": {
                "locale": "en",
            },
        }
    )
    store.clear_state()
    on_completed(completion_timestamp)
    return True
