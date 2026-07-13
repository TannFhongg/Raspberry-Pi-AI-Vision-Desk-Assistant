"""Shared authoritative setup-state persistence and wizard helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any, Callable

from system.storage import atomic_write_json, quarantine_file, safe_unlink

SCHEMA_VERSION = 2
OPENAI_VERIFICATION_SCHEMA_VERSION = 1
OPENAI_VERIFICATION_MAX_AGE_DAYS = 30


class SetupStateStore:
    """Persist and normalize the first-boot setup wizard state."""

    def __init__(
        self,
        *,
        state_path: str | Path,
        quarantine_dir: str | Path,
        timestamp_provider: Callable[[], str],
        app_version: str,
        setup_steps: tuple[str, ...],
        build_gpio_requirements: Callable[[], list[dict[str, Any]]],
        legacy_setup_is_complete: Callable[[], bool],
        legacy_setup_completed_at: Callable[[], str],
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
        self.app_version = app_version
        self.setup_steps = setup_steps
        self.build_gpio_requirements = build_gpio_requirements
        self.legacy_setup_is_complete = legacy_setup_is_complete
        self.legacy_setup_completed_at = legacy_setup_completed_at
        self.current_wifi_ssid = current_wifi_ssid
        self.current_wifi_connection_name = current_wifi_connection_name
        self.current_wifi_auto_connect = current_wifi_auto_connect
        self.current_wifi_managed_by = current_wifi_managed_by
        self.has_configured_openai_key = has_configured_openai_key
        self.current_openai_key = current_openai_key
        self._state_lock = threading.RLock()
        self._operation_generation = 0

    def begin_operation(self) -> int:
        """Reserve the next generation for a setup action."""
        with self._state_lock:
            self._operation_generation += 1
            return self._operation_generation

    def invalidate_pending_operations(self) -> int:
        """Prevent already-running setup workers from applying stale results."""
        return self.begin_operation()

    def is_operation_current(self, operation_id: int) -> bool:
        """Return whether a worker is still permitted to commit external changes."""
        with self._state_lock:
            return operation_id == self._operation_generation

    @staticmethod
    def _empty_openai_verification() -> dict[str, Any]:
        return {
            "verified": False,
            "verified_at": "",
            "verification_schema_version": OPENAI_VERIFICATION_SCHEMA_VERSION,
            "provider": "openai",
            "model": "",
        }

    def _verification_timestamp_is_fresh(self, value: object) -> bool:
        try:
            verified_at = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
            now = datetime.fromisoformat(self.timestamp_provider().strip().replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return False

        if verified_at.tzinfo is not None:
            verified_at = verified_at.astimezone(timezone.utc).replace(tzinfo=None)
        if now.tzinfo is not None:
            now = now.astimezone(timezone.utc).replace(tzinfo=None)
        age = now - verified_at
        return timedelta(0) <= age <= timedelta(days=OPENAI_VERIFICATION_MAX_AGE_DAYS)

    def _coerce_openai_verification(self, value: Any, *, key_present: bool) -> dict[str, Any]:
        raw_verification = value if isinstance(value, dict) else {}
        try:
            schema_version = int(raw_verification.get("verification_schema_version", 0))
        except (TypeError, ValueError):
            schema_version = 0
        verified_at = str(raw_verification.get("verified_at", "")).strip()
        is_current = (
            key_present
            and bool(raw_verification.get("verified", False))
            and schema_version == OPENAI_VERIFICATION_SCHEMA_VERSION
            and self._verification_timestamp_is_fresh(verified_at)
        )
        return {
            "verified": is_current,
            "verified_at": verified_at if is_current else "",
            "verification_schema_version": OPENAI_VERIFICATION_SCHEMA_VERSION,
            "provider": "openai",
            "model": str(raw_verification.get("model", "")).strip() if is_current else "",
        }

    def coerce_step(self, value: Any) -> str:
        """Normalize a persisted wizard step value."""
        normalized = str(value or "").strip().lower()
        if normalized in self.setup_steps:
            return normalized
        return self.setup_steps[0]

    def default_state(self) -> dict[str, Any]:
        """Return the default authoritative setup-wizard state."""
        required_buttons = self.build_gpio_requirements()
        wifi_ssid = str(self.current_wifi_ssid() or "").strip()
        openai_key_present = self.has_configured_openai_key(self.current_openai_key())
        wifi_status = "pass" if wifi_ssid else "idle"
        openai_status = "idle"
        camera_status = "idle"
        gpio_status = "idle"
        finish_status = "idle"
        current_step = "welcome"

        state = {
            "schema_version": SCHEMA_VERSION,
            "setup_complete": False,
            "completed_at": "",
            "app_version": "",
            "current_step": current_step,
            "warnings_acknowledged": False,
            "finish_message": "",
            "updated_at": self.timestamp_provider(),
            "steps": {
                "welcome": {
                    "status": "idle",
                    "message": "",
                    "checks": [],
                },
                "wifi": {
                    "status": wifi_status,
                    "message": (
                        f"Connected to Wi-Fi network '{wifi_ssid}'."
                        if wifi_status == "pass"
                        else ""
                    ),
                },
                "openai": {
                    "status": openai_status,
                    "message": (
                        "OpenAI API key is already configured."
                        if openai_status == "pass"
                        else ""
                    ),
                },
                "camera": {
                    "status": camera_status,
                    "message": "",
                },
                "gpio": {
                    "status": gpio_status,
                    "message": "",
                },
                "finish": {
                    "status": finish_status,
                    "message": "",
                },
            },
            "wifi": {
                "scan_status": "idle",
                "connect_status": wifi_status,
                "available_networks": [],
                "ssid": wifi_ssid,
                "connection_name": self.current_wifi_connection_name(),
                "message": (
                    f"Connected to Wi-Fi network '{wifi_ssid}'."
                    if wifi_status == "pass"
                    else ""
                ),
                "auto_connect": self.current_wifi_auto_connect(),
                "managed_by": self.current_wifi_managed_by(),
            },
            "openai": {
                "status": openai_status,
                "key_present": openai_key_present,
                "api_key_verified": False,
                "verification": self._empty_openai_verification(),
                "message": "API key saved. Verification required." if openai_key_present else "",
            },
            "camera": {
                "status": camera_status,
                "message": "",
            },
            "gpio": {
                "status": gpio_status,
                "message": "",
                "active": False,
                "required": required_buttons,
                "pressed_labels": [],
                "all_pressed": False,
                "validation_issues": [],
            },
        }
        return self._sync_derived_fields(state)

    def _coerce_device_checks(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            normalized.append(
                {
                    "name": name,
                    "status": str(item.get("status", "unknown")).strip().lower() or "unknown",
                    "message": str(item.get("message", "")).strip(),
                    "required": bool(item.get("required", True)),
                }
            )
        return normalized

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

    @staticmethod
    def _coerce_validation_issues(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

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

    @staticmethod
    def setup_wifi_connected(state: dict[str, Any]) -> bool:
        """Return True when setup has a successful Wi-Fi connection state."""
        wifi = state.get("wifi", {}) if isinstance(state, dict) else {}
        return str(wifi.get("connect_status", "")).strip().lower() == "pass"

    @staticmethod
    def setup_openai_verified(state: dict[str, Any]) -> bool:
        """Return True when setup has a verified OpenAI key state."""
        openai = state.get("openai", {}) if isinstance(state, dict) else {}
        verification = openai.get("verification", {}) if isinstance(openai, dict) else {}
        try:
            verification_schema_version = int(verification.get("verification_schema_version", 0) or 0)
        except (AttributeError, TypeError, ValueError):
            verification_schema_version = 0
        return (
            str(openai.get("status", "")).strip().lower() == "pass"
            and bool(openai.get("key_present", False))
            and bool(openai.get("api_key_verified", False))
            and bool(verification.get("verified", False))
            and verification_schema_version == OPENAI_VERIFICATION_SCHEMA_VERSION
        )

    @staticmethod
    def setup_camera_passed(state: dict[str, Any]) -> bool:
        camera = state.get("camera", {}) if isinstance(state, dict) else {}
        return str(camera.get("status", "")).strip().lower() == "pass"

    def setup_gpio_passed(self, state: dict[str, Any]) -> bool:
        gpio = state.get("gpio", {}) if isinstance(state, dict) else {}
        if self._coerce_validation_issues(gpio.get("validation_issues", [])):
            return False
        if not bool(gpio.get("all_pressed", False)):
            return False
        return str(gpio.get("status", "")).strip().lower() == "pass"

    def setup_ready_to_finish(self, state: dict[str, Any] | None = None) -> bool:
        """Return True when the setup wizard has everything required to finish."""
        current_state = self.load_state() if state is None else state
        return (
            self.setup_wifi_connected(current_state)
            and self.setup_openai_verified(current_state)
            and self.setup_camera_passed(current_state)
            and self.setup_gpio_passed(current_state)
        )

    def is_setup_complete(self, state: dict[str, Any] | None = None) -> bool:
        current_state = self.load_state() if state is None else state
        return bool(current_state.get("setup_complete", False))

    def _welcome_status(self, state: dict[str, Any]) -> tuple[str, str]:
        checks = self._coerce_device_checks(state.get("steps", {}).get("welcome", {}).get("checks", []))
        if not checks:
            return "idle", ""
        required_failures = [
            item for item in checks if item.get("required", True) and item.get("status") == "fail"
        ]
        if required_failures:
            return "fail", required_failures[0]["message"]
        if all(item.get("status") == "pass" for item in checks):
            return "pass", f"{len(checks)} device checks passed."
        return "running", "Device checks completed with warnings."

    def _sync_derived_fields(self, state: dict[str, Any]) -> dict[str, Any]:
        gpio = state.setdefault("gpio", {})
        gpio["pressed_labels"] = sorted(
            {
                str(label).strip()
                for label in gpio.get("pressed_labels", [])
                if str(label).strip()
            }
        )
        gpio["required"] = self.coerce_required_buttons(gpio.get("required", self.build_gpio_requirements()))
        gpio["validation_issues"] = self._coerce_validation_issues(gpio.get("validation_issues", []))
        gpio["all_pressed"] = self.setup_gpio_complete(state)

        wifi_status = str(state.get("wifi", {}).get("connect_status", "idle")).strip().lower() or "idle"
        openai_status = str(state.get("openai", {}).get("status", "idle")).strip().lower() or "idle"
        camera_status = str(state.get("camera", {}).get("status", "idle")).strip().lower() or "idle"
        gpio_status = str(gpio.get("status", "idle")).strip().lower() or "idle"
        welcome_status, welcome_message = self._welcome_status(state)

        steps = state.setdefault("steps", {})
        welcome_step = steps.setdefault("welcome", {})
        welcome_step["checks"] = self._coerce_device_checks(welcome_step.get("checks", []))
        welcome_step["status"] = welcome_status
        welcome_step["message"] = str(welcome_step.get("message", "")).strip() or welcome_message

        steps.setdefault("wifi", {})
        steps["wifi"]["status"] = wifi_status
        steps["wifi"]["message"] = str(state.get("wifi", {}).get("message", "")).strip()

        steps.setdefault("openai", {})
        steps["openai"]["status"] = openai_status
        steps["openai"]["message"] = str(state.get("openai", {}).get("message", "")).strip()

        steps.setdefault("camera", {})
        steps["camera"]["status"] = camera_status
        steps["camera"]["message"] = str(state.get("camera", {}).get("message", "")).strip()

        steps.setdefault("gpio", {})
        if gpio["validation_issues"]:
            steps["gpio"]["status"] = "fail"
            steps["gpio"]["message"] = gpio["validation_issues"][0]
        else:
            steps["gpio"]["status"] = "pass" if gpio["all_pressed"] and gpio_status == "pass" else gpio_status
            steps["gpio"]["message"] = str(gpio.get("message", "")).strip()

        steps.setdefault("finish", {})
        warnings = self.build_warnings(state)
        if bool(state.get("setup_complete", False)):
            steps["finish"]["status"] = "pass"
            steps["finish"]["message"] = "Setup complete."
        elif self.setup_ready_to_finish(state):
            steps["finish"]["status"] = "pass"
            steps["finish"]["message"] = "All required checks passed."
        elif warnings:
            steps["finish"]["status"] = "fail"
            steps["finish"]["message"] = warnings[0]
        else:
            steps["finish"]["status"] = "idle"
            steps["finish"]["message"] = ""
        state["schema_version"] = SCHEMA_VERSION
        state["current_step"] = self.coerce_step(state.get("current_step"))
        state["app_version"] = str(state.get("app_version", "")).strip()
        state["completed_at"] = str(state.get("completed_at", "")).strip()
        if not bool(state.get("setup_complete", False)):
            state["completed_at"] = ""
        return state

    def coerce_state(self, raw_state: Any) -> dict[str, Any]:
        """Normalize any persisted setup state into the supported schema."""
        default_state = self.default_state()
        if not isinstance(raw_state, dict):
            return default_state

        wifi = raw_state.get("wifi", {})
        gpio = raw_state.get("gpio", {})
        steps = raw_state.get("steps", {})
        openai = raw_state.get("openai", {})
        camera = raw_state.get("camera", {})
        key_present = bool(openai.get("key_present", default_state["openai"]["key_present"]))
        verification = self._coerce_openai_verification(openai.get("verification"), key_present=key_present)
        raw_openai_status = str(openai.get("status", default_state["openai"]["status"])).strip().lower()
        if verification["verified"]:
            openai_status = "pass"
            openai_message = "OpenAI API key verified."
        elif raw_openai_status in {"fail", "running"}:
            openai_status = raw_openai_status
            openai_message = str(openai.get("message", "")).strip()
        else:
            openai_status = "idle"
            openai_message = "API key saved. Verification required." if key_present else ""

        normalized_state = {
            "schema_version": int(raw_state.get("schema_version", SCHEMA_VERSION) or SCHEMA_VERSION),
            "setup_complete": bool(raw_state.get("setup_complete", default_state["setup_complete"])),
            "completed_at": str(raw_state.get("completed_at", default_state["completed_at"])).strip(),
            "app_version": str(raw_state.get("app_version", default_state["app_version"])).strip(),
            "current_step": self.coerce_step(raw_state.get("current_step", default_state["current_step"])),
            "warnings_acknowledged": bool(raw_state.get("warnings_acknowledged", False)),
            "finish_message": str(raw_state.get("finish_message", "")),
            "updated_at": str(raw_state.get("updated_at", default_state["updated_at"])),
            "steps": {
                "welcome": {
                    "status": str(steps.get("welcome", {}).get("status", "idle")),
                    "message": str(steps.get("welcome", {}).get("message", "")),
                    "checks": self._coerce_device_checks(steps.get("welcome", {}).get("checks", [])),
                },
                "wifi": {
                    "status": str(steps.get("wifi", {}).get("status", default_state["steps"]["wifi"]["status"])),
                    "message": str(steps.get("wifi", {}).get("message", "")),
                },
                "openai": {
                    "status": str(
                        steps.get("openai", {}).get("status", default_state["steps"]["openai"]["status"])
                    ),
                    "message": str(steps.get("openai", {}).get("message", "")),
                },
                "camera": {
                    "status": str(
                        steps.get("camera", {}).get("status", default_state["steps"]["camera"]["status"])
                    ),
                    "message": str(steps.get("camera", {}).get("message", "")),
                },
                "gpio": {
                    "status": str(steps.get("gpio", {}).get("status", default_state["steps"]["gpio"]["status"])),
                    "message": str(steps.get("gpio", {}).get("message", "")),
                },
                "finish": {
                    "status": str(
                        steps.get("finish", {}).get("status", default_state["steps"]["finish"]["status"])
                    ),
                    "message": str(steps.get("finish", {}).get("message", "")),
                },
            },
            "wifi": {
                "scan_status": str(wifi.get("scan_status", default_state["wifi"]["scan_status"])),
                "connect_status": str(wifi.get("connect_status", default_state["wifi"]["connect_status"])),
                "available_networks": self.coerce_setup_networks(wifi.get("available_networks", [])),
                "ssid": str(wifi.get("ssid", default_state["wifi"]["ssid"])).strip(),
                "connection_name": str(
                    wifi.get("connection_name", default_state["wifi"]["connection_name"])
                ).strip(),
                "message": str(wifi.get("message", "")),
                "auto_connect": bool(wifi.get("auto_connect", default_state["wifi"]["auto_connect"])),
                "managed_by": str(wifi.get("managed_by", default_state["wifi"]["managed_by"])) or "nmcli",
            },
            "openai": {
                "status": openai_status,
                "key_present": key_present,
                "api_key_verified": bool(verification["verified"]),
                "verification": verification,
                "message": openai_message,
            },
            "camera": {
                "status": str(camera.get("status", default_state["camera"]["status"])),
                "message": str(camera.get("message", "")),
            },
            "gpio": {
                "status": str(gpio.get("status", default_state["gpio"]["status"])),
                "message": str(gpio.get("message", "")),
                "active": bool(gpio.get("active", False)),
                "required": self.coerce_required_buttons(gpio.get("required", default_state["gpio"]["required"])),
                "pressed_labels": list(gpio.get("pressed_labels", [])),
                "all_pressed": bool(gpio.get("all_pressed", False)),
                "validation_issues": self._coerce_validation_issues(gpio.get("validation_issues", [])),
            },
        }
        return self._sync_derived_fields(normalized_state)

    def load_state(self) -> dict[str, Any]:
        """Read the persisted setup-wizard state file."""
        with self._state_lock:
            return self._load_state_locked()

    def _load_state_locked(self) -> dict[str, Any]:
        """Read state while the caller holds the setup-state lock."""
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

    def update_state(
        self,
        updates: dict[str, Any] | None = None,
        *,
        operation_id: int | None = None,
    ) -> dict[str, Any] | None:
        """Atomically merge updates unless a newer setup action superseded them."""
        with self._state_lock:
            if operation_id is not None and operation_id != self._operation_generation:
                return None
            next_state = self._load_state_locked()
            if updates:
                merge_nested_state(next_state, updates)
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

    def write_state(
        self,
        updates: dict[str, Any] | None = None,
        *,
        operation_id: int | None = None,
    ) -> dict[str, Any] | None:
        """Backward-compatible alias for the atomic setup-state update helper."""
        return self.update_state(updates, operation_id=operation_id)

    def clear_state(self) -> None:
        """Delete the persisted setup state file."""
        with self._state_lock:
            safe_unlink(self.state_path)

    def write_device_checks(
        self,
        checks: list[dict[str, Any]],
        *,
        operation_id: int | None = None,
    ) -> dict[str, Any] | None:
        """Persist the welcome/device-check results."""
        normalized_checks = self._coerce_device_checks(checks)
        required_failures = [
            item for item in normalized_checks if item.get("required", True) and item.get("status") == "fail"
        ]
        if required_failures:
            status = "fail"
            message = required_failures[0]["message"]
        elif normalized_checks and all(item.get("status") == "pass" for item in normalized_checks):
            status = "pass"
            message = f"{len(normalized_checks)} device checks passed."
        elif normalized_checks:
            status = "running"
            message = "Device checks completed with warnings."
        else:
            status = "idle"
            message = ""
        return self.write_state(
            {
                "current_step": "welcome",
                "steps": {
                    "welcome": {
                        "status": status,
                        "message": message,
                        "checks": normalized_checks,
                    }
                },
            },
            operation_id=operation_id,
        )

    def build_warnings(self, state: dict[str, Any] | None = None) -> list[str]:
        """Return the unresolved warnings shown on the finish step."""
        current_state = self.load_state() if state is None else state
        warnings: list[str] = []
        if not self.setup_wifi_connected(current_state):
            warnings.append("Connect to Wi-Fi before finishing setup.")
        if not self.setup_openai_verified(current_state):
            warnings.append("Verify the OpenAI API key before finishing setup.")
        if not self.setup_camera_passed(current_state):
            warnings.append("Complete the camera test before finishing setup.")
        if not self.setup_gpio_passed(current_state):
            warnings.append("Complete the GPIO button test before finishing setup.")
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


def _unverified_openai_metadata() -> dict[str, Any]:
    return {
        "verified": False,
        "verified_at": "",
        "verification_schema_version": OPENAI_VERIFICATION_SCHEMA_VERSION,
        "provider": "openai",
        "model": "",
    }


def _verified_openai_metadata(store: SetupStateStore, result: Any) -> dict[str, Any]:
    return {
        "verified": True,
        "verified_at": store.timestamp_provider(),
        "verification_schema_version": OPENAI_VERIFICATION_SCHEMA_VERSION,
        "provider": "openai",
        "model": str(getattr(result, "model", "")).strip(),
    }


def _safe_openai_verification_message(result: Any | None) -> str:
    """Convert provider outcomes into fixed setup messages without diagnostic detail."""
    if result is None:
        return "The API key could not be verified. Existing configuration was not changed."
    if bool(getattr(result, "passed", False)):
        return "OpenAI API key verified."

    code = str(getattr(result, "code", "")).strip().lower()
    detail = str(getattr(result, "message", "")).strip().lower()
    if code in {"authentication", "authorization"} or any(
        token in detail for token in ("authentication", "invalid api", "api key", "access denied")
    ):
        return "The API key was not accepted. Check it and try again."
    if code == "network" or any(token in detail for token in ("network", "connection", "internet")):
        return "Network unavailable. The API key was not changed."
    if code == "timeout" or "timed out" in detail or "timeout" in detail:
        return "API verification timed out. The API key was not changed."
    if code == "rate_limit" or "rate limit" in detail or "quota" in detail:
        return "OpenAI is rate limiting verification. Try again later."
    if code in {"service_unavailable", "service_error"} or "service unavailable" in detail:
        return "OpenAI service is unavailable. Try again later."
    return "The API key could not be verified. Existing configuration was not changed."


def _setup_operation_is_current(store: SetupStateStore) -> bool:
    checker = getattr(store, "is_current", None)
    return True if checker is None else bool(checker())


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

    validation_issues = [
        str(issue).strip()
        for issue in snapshot.get("validation_issues", [])
        if str(issue).strip()
    ]
    if validation_issues:
        status = "fail"
        message = validation_issues[0]
    elif snapshot.get("all_pressed"):
        status = "pass"
        message = snapshot.get("message", "All configured GPIO setup buttons were pressed successfully.")
    elif snapshot.get("active"):
        status = "running"
        message = snapshot.get("message", "Press each configured GPIO button once to verify it.")
    else:
        status = state["gpio"].get("status", "idle")
        message = snapshot.get("message", state["gpio"].get("message", ""))

    next_step = "finish" if status == "pass" else "gpio"
    return store.write_state(
        {
            "current_step": next_step,
            "gpio": {
                "status": status,
                "message": message,
                "active": bool(snapshot.get("active", False)),
                "required": normalized_required,
                "pressed_labels": sorted(pressed_labels),
                "all_pressed": bool(snapshot.get("all_pressed", False)),
                "validation_issues": validation_issues,
            },
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
        next_step = "camera" if store.setup_openai_verified(state) else "openai"
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
    check_openai_reachable: Callable[[str], Any],
) -> None:
    """Verify a candidate key before atomically replacing protected credentials."""
    normalized_key = api_key.strip()
    state = store.load_state()
    key_present = bool(state.get("openai", {}).get("key_present", False))

    def write_failure(message: str) -> None:
        store.write_state(
            {
                "current_step": "openai",
                "finish_message": "",
                "openai": {
                    "status": "fail",
                    "key_present": key_present,
                    "api_key_verified": False,
                    "verification": _unverified_openai_metadata(),
                    "message": message,
                },
            }
        )

    if (
        not store.has_configured_openai_key(normalized_key)
        or not looks_like_openai_api_key(normalized_key)
    ):
        write_failure("Enter a valid OPENAI_API_KEY starting with sk- before continuing.")
        return

    # Invalidate any previous verification while the replacement is in flight.
    store.write_state(
        {
            "current_step": "openai",
            "finish_message": "",
            "openai": {
                "status": "running",
                "key_present": key_present,
                "api_key_verified": False,
                "verification": _unverified_openai_metadata(),
                "message": "Verifying API key...",
            },
        }
    )

    try:
        result = check_openai_reachable(normalized_key)
    except Exception:
        result = None

    if result is None or not bool(getattr(result, "passed", False)):
        write_failure(_safe_openai_verification_message(result))
        return

    if not _setup_operation_is_current(store):
        return

    try:
        upsert_env_value(env_file_path, "OPENAI_API_KEY", normalized_key)
    except OSError:
        write_failure("The API key could not be saved. Existing configuration was not changed.")
        return

    os.environ["OPENAI_API_KEY"] = normalized_key
    latest_state = store.load_state()
    next_step = "camera" if store.setup_wifi_connected(latest_state) else "openai"
    store.write_state(
        {
            "current_step": next_step,
            "finish_message": "",
            "openai": {
                "status": "pass",
                "key_present": True,
                "api_key_verified": True,
                "verification": _verified_openai_metadata(store, result),
                "message": _safe_openai_verification_message(result),
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
                "version": SCHEMA_VERSION,
            },
            "localization": {
                "locale": "en",
            },
        }
    )
    store.write_state(
        {
            "setup_complete": True,
            "completed_at": completion_timestamp,
            "app_version": store.app_version,
            "current_step": "finish",
            "finish_message": "Setup complete. Restarting VisionDesk...",
            "wifi": {
                "available_networks": [],
            },
            "steps": {
                "finish": {
                    "status": "pass",
                    "message": "Setup complete.",
                }
            },
        }
    )
    on_completed(completion_timestamp)
    return True
