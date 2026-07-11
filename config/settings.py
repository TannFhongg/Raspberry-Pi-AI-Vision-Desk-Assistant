"""Typed device settings loaded from YAML with environment overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml
from ai.modes import get_available_modes, normalize_mode

DEFAULT_CONFIG_PATH = Path("config/device.yaml")
VALID_CAMERA_BACKENDS = ("opencv",)
VALID_AUTOFOCUS_MODES = ("continuous", "auto", "off")
VALID_SCREEN_OPTIMIZATIONS = ("auto", "on", "off")
VALID_DISPLAY_ORIENTATIONS = ("landscape", "portrait", "auto")
VALID_STARTUP_BEHAVIORS = ("kiosk", "service_only", "manual")
VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
DEFAULT_BUTTON_DEBOUNCE_SECONDS = 0.15
DEFAULT_BUTTON_HOLD_SECONDS = 1.2
DEFAULT_LED_ENABLED = False
DEFAULT_LED_PIN = 27
DEFAULT_LED_ACTIVE_HIGH = True
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_MAX_BYTES = 1_048_576
DEFAULT_LOG_BACKUP_COUNT = 5
DEFAULT_HEALTH_MONITOR_ENABLED = True
DEFAULT_HEALTH_CHECK_INTERVAL_SECONDS = 60.0
DEFAULT_CAMERA_PROBE_INTERVAL_SECONDS = 300.0
DEFAULT_OPENAI_TIMEOUT_SECONDS = 30.0
DEFAULT_OPENAI_RETRY_ATTEMPTS = 3
DEFAULT_OPENAI_RETRY_BACKOFF_SECONDS = 2.0


class SettingsError(Exception):
    """Raised when the device settings file or overrides are invalid."""


@dataclass(slots=True)
class ResolutionSettings:
    """Size settings shared by camera and display configuration."""

    width: int
    height: int


@dataclass(slots=True)
class CameraSettings:
    """Camera and preprocessing defaults for the device."""

    backend: str
    index: int
    resolution: ResolutionSettings
    autofocus_mode: str
    exposure: str | int
    brightness: float
    capture_delay_seconds: float
    grayscale: bool
    max_dimension: int


@dataclass(slots=True)
class DisplaySettings:
    """Attached display defaults."""

    size: ResolutionSettings
    orientation: str


@dataclass(slots=True)
class ButtonSettings:
    """GPIO button defaults."""

    enabled: bool
    pin: int
    mode_button_1_pin: int | None
    mode_button_2_pin: int | None
    mode_button_3_pin: int | None
    mode_button_4_pin: int | None
    mode_button_5_pin: int | None
    back_button_pin: int | None
    debounce_seconds: float
    hold_seconds: float


@dataclass(slots=True)
class LEDSettings:
    """Optional GPIO LED defaults."""

    enabled: bool
    pin: int
    active_high: bool


@dataclass(slots=True)
class AISettings:
    """AI-related runtime defaults."""

    default_mode: str


@dataclass(slots=True)
class VisionSettings:
    """Vision pipeline defaults shared across preprocess flows."""

    screen_optimization: str


@dataclass(slots=True)
class StartupSettings:
    """Device startup behavior defaults."""

    behavior: str
    url: str


@dataclass(slots=True)
class ReliabilitySettings:
    """Runtime reliability, logging, and retry defaults."""

    log_level: str
    log_max_bytes: int
    log_backup_count: int
    health_monitor_enabled: bool
    health_check_interval_seconds: float
    camera_probe_interval_seconds: float
    openai_timeout_seconds: float
    openai_retry_attempts: int
    openai_retry_backoff_seconds: float


@dataclass(slots=True)
class DeviceSettings:
    """Top-level typed settings for the standalone device."""

    camera: CameraSettings
    display: DisplaySettings
    button: ButtonSettings
    led: LEDSettings
    ai: AISettings
    vision: VisionSettings
    startup: StartupSettings
    reliability: ReliabilitySettings
    config_path: Path


def load_device_settings(
    config_path: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> DeviceSettings:
    """Load device settings from YAML and apply environment overrides."""
    environment = dict(os.environ if env is None else env)
    resolved_path = Path(
        environment.get("DEVICE_CONFIG_PATH")
        or config_path
        or DEFAULT_CONFIG_PATH
    )
    raw_data = _read_yaml(resolved_path)
    merged = _apply_environment_overrides(raw_data, environment)

    camera = merged.get("camera", {})
    display = merged.get("display", {})
    button = merged.get("button", {})
    led = merged.get("led", {})
    ai = merged.get("ai", {})
    vision = merged.get("vision", {})
    startup = merged.get("startup", {})
    reliability = merged.get("reliability", {})

    return DeviceSettings(
        camera=CameraSettings(
            backend=_parse_choice(
                camera.get("backend"),
                VALID_CAMERA_BACKENDS,
                "camera.backend",
            ),
            index=_parse_int(camera.get("index"), "camera.index", minimum=0),
            resolution=ResolutionSettings(
                width=_parse_int(
                    _nested_get(camera, "resolution", "width"),
                    "camera.resolution.width",
                    minimum=1,
                ),
                height=_parse_int(
                    _nested_get(camera, "resolution", "height"),
                    "camera.resolution.height",
                    minimum=1,
                ),
            ),
            autofocus_mode=_parse_choice(
                camera.get("autofocus_mode"),
                VALID_AUTOFOCUS_MODES,
                "camera.autofocus_mode",
            ),
            exposure=_parse_exposure(camera.get("exposure")),
            brightness=_parse_float(camera.get("brightness"), "camera.brightness"),
            capture_delay_seconds=_parse_float(
                camera.get("capture_delay_seconds"),
                "camera.capture_delay_seconds",
                minimum=0.0,
            ),
            grayscale=_parse_bool(camera.get("grayscale"), "camera.grayscale"),
            max_dimension=_parse_int(
                camera.get("max_dimension"),
                "camera.max_dimension",
                minimum=1,
            ),
        ),
        display=DisplaySettings(
            size=ResolutionSettings(
                width=_parse_int(
                    _nested_get(display, "size", "width"),
                    "display.size.width",
                    minimum=1,
                ),
                height=_parse_int(
                    _nested_get(display, "size", "height"),
                    "display.size.height",
                    minimum=1,
                ),
            ),
            orientation=_parse_choice(
                display.get("orientation"),
                VALID_DISPLAY_ORIENTATIONS,
                "display.orientation",
            ),
        ),
        button=ButtonSettings(
            enabled=_parse_bool(button.get("enabled"), "button.enabled"),
            pin=_parse_int(button.get("pin"), "button.pin", minimum=0),
            mode_button_1_pin=_parse_optional_int(
                button.get("mode_button_1_pin"),
                "button.mode_button_1_pin",
                minimum=0,
            ),
            mode_button_2_pin=_parse_optional_int(
                button.get("mode_button_2_pin"),
                "button.mode_button_2_pin",
                minimum=0,
            ),
            mode_button_3_pin=_parse_optional_int(
                button.get("mode_button_3_pin"),
                "button.mode_button_3_pin",
                minimum=0,
            ),
            mode_button_4_pin=_parse_optional_int(
                button.get("mode_button_4_pin"),
                "button.mode_button_4_pin",
                minimum=0,
            ),
            mode_button_5_pin=_parse_optional_int(
                button.get("mode_button_5_pin"),
                "button.mode_button_5_pin",
                minimum=0,
            ),
            back_button_pin=_parse_optional_int(
                button.get("back_button_pin"),
                "button.back_button_pin",
                minimum=0,
            ),
            debounce_seconds=_parse_float(
                button.get("debounce_seconds", DEFAULT_BUTTON_DEBOUNCE_SECONDS),
                "button.debounce_seconds",
                minimum=0.0,
            ),
            hold_seconds=_parse_float(
                button.get("hold_seconds", DEFAULT_BUTTON_HOLD_SECONDS),
                "button.hold_seconds",
                minimum=0.0,
            ),
        ),
        led=LEDSettings(
            enabled=_parse_bool(led.get("enabled", DEFAULT_LED_ENABLED), "led.enabled"),
            pin=_parse_int(led.get("pin", DEFAULT_LED_PIN), "led.pin", minimum=0),
            active_high=_parse_bool(
                led.get("active_high", DEFAULT_LED_ACTIVE_HIGH),
                "led.active_high",
            ),
        ),
        ai=AISettings(
            default_mode=_parse_mode(ai.get("default_mode"), "ai.default_mode"),
        ),
        vision=VisionSettings(
            screen_optimization=_parse_choice(
                vision.get("screen_optimization", "auto"),
                VALID_SCREEN_OPTIMIZATIONS,
                "vision.screen_optimization",
            ),
        ),
        startup=StartupSettings(
            behavior=_parse_choice(
                startup.get("behavior"),
                VALID_STARTUP_BEHAVIORS,
                "startup.behavior",
            ),
            url=_parse_text(startup.get("url"), "startup.url"),
        ),
        reliability=ReliabilitySettings(
            log_level=_parse_log_level(
                reliability.get("log_level", DEFAULT_LOG_LEVEL),
                "reliability.log_level",
            ),
            log_max_bytes=_parse_int(
                reliability.get("log_max_bytes", DEFAULT_LOG_MAX_BYTES),
                "reliability.log_max_bytes",
                minimum=1,
            ),
            log_backup_count=_parse_int(
                reliability.get("log_backup_count", DEFAULT_LOG_BACKUP_COUNT),
                "reliability.log_backup_count",
                minimum=0,
            ),
            health_monitor_enabled=_parse_bool(
                reliability.get(
                    "health_monitor_enabled",
                    DEFAULT_HEALTH_MONITOR_ENABLED,
                ),
                "reliability.health_monitor_enabled",
            ),
            health_check_interval_seconds=_parse_float(
                reliability.get(
                    "health_check_interval_seconds",
                    DEFAULT_HEALTH_CHECK_INTERVAL_SECONDS,
                ),
                "reliability.health_check_interval_seconds",
                minimum=1.0,
            ),
            camera_probe_interval_seconds=_parse_float(
                reliability.get(
                    "camera_probe_interval_seconds",
                    DEFAULT_CAMERA_PROBE_INTERVAL_SECONDS,
                ),
                "reliability.camera_probe_interval_seconds",
                minimum=1.0,
            ),
            openai_timeout_seconds=_parse_float(
                reliability.get(
                    "openai_timeout_seconds",
                    DEFAULT_OPENAI_TIMEOUT_SECONDS,
                ),
                "reliability.openai_timeout_seconds",
                minimum=0.1,
            ),
            openai_retry_attempts=_parse_int(
                reliability.get(
                    "openai_retry_attempts",
                    DEFAULT_OPENAI_RETRY_ATTEMPTS,
                ),
                "reliability.openai_retry_attempts",
                minimum=1,
            ),
            openai_retry_backoff_seconds=_parse_float(
                reliability.get(
                    "openai_retry_backoff_seconds",
                    DEFAULT_OPENAI_RETRY_BACKOFF_SECONDS,
                ),
                "reliability.openai_retry_backoff_seconds",
                minimum=0.0,
            ),
        ),
        config_path=resolved_path,
    )


def _read_yaml(config_path: Path) -> dict[str, Any]:
    """Read a YAML file into a dictionary."""
    if not config_path.is_file():
        raise SettingsError(f"Device config file not found: '{config_path}'.")

    try:
        raw_data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SettingsError(f"Could not read device config '{config_path}'. {exc}") from exc
    except yaml.YAMLError as exc:
        raise SettingsError(f"Invalid YAML in device config '{config_path}'. {exc}") from exc

    if raw_data is None:
        return {}
    if not isinstance(raw_data, dict):
        raise SettingsError(
            f"Device config '{config_path}' must contain a top-level mapping."
        )
    return raw_data


def _apply_environment_overrides(
    raw_data: dict[str, Any],
    env: Mapping[str, str],
) -> dict[str, Any]:
    """Overlay environment variables on top of YAML defaults."""
    merged = dict(raw_data)
    merged["camera"] = dict(raw_data.get("camera", {}))
    merged["display"] = dict(raw_data.get("display", {}))
    merged["button"] = dict(raw_data.get("button", {}))
    merged["led"] = dict(raw_data.get("led", {}))
    merged["ai"] = dict(raw_data.get("ai", {}))
    merged["vision"] = dict(raw_data.get("vision", {}))
    merged["startup"] = dict(raw_data.get("startup", {}))
    merged["reliability"] = dict(raw_data.get("reliability", {}))

    camera = merged["camera"]
    camera_resolution = dict(camera.get("resolution", {}))
    camera["resolution"] = camera_resolution
    display = merged["display"]
    display_size = dict(display.get("size", {}))
    display["size"] = display_size

    _set_if_present(camera, "backend", env, "VISION_CAMERA_BACKEND")
    _set_if_present(camera, "index", env, "VISION_CAMERA_INDEX")
    _set_if_present(camera_resolution, "width", env, "VISION_CAPTURE_WIDTH")
    _set_if_present(camera_resolution, "height", env, "VISION_CAPTURE_HEIGHT")
    _set_if_present(camera, "grayscale", env, "VISION_GRAYSCALE")
    _set_if_present(camera, "max_dimension", env, "VISION_MAX_DIMENSION")
    _set_if_present(
        camera,
        "autofocus_mode",
        env,
        "VISION_AUTOFOCUS_MODE",
        "VISION_CAMERA_AUTOFOCUS_MODE",
    )
    _set_if_present(camera, "exposure", env, "VISION_EXPOSURE", "VISION_CAMERA_EXPOSURE")
    _set_if_present(
        camera,
        "brightness",
        env,
        "VISION_BRIGHTNESS",
        "VISION_CAMERA_BRIGHTNESS",
    )
    _set_if_present(
        camera,
        "capture_delay_seconds",
        env,
        "VISION_CAPTURE_DELAY_SECONDS",
        "VISION_CAPTURE_DELAY",
    )

    _set_if_present(display_size, "width", env, "UI_SCREEN_WIDTH")
    _set_if_present(display_size, "height", env, "UI_SCREEN_HEIGHT")
    _set_if_present(display, "orientation", env, "UI_DISPLAY_ORIENTATION")

    _set_if_present(merged["button"], "enabled", env, "ENABLE_GPIO_BUTTON")
    _set_if_present(merged["button"], "pin", env, "CAPTURE_BUTTON_PIN", "GPIO_BUTTON_PIN")
    _set_if_present(merged["button"], "mode_button_1_pin", env, "MODE_BUTTON_1_PIN")
    _set_if_present(merged["button"], "mode_button_2_pin", env, "MODE_BUTTON_2_PIN")
    _set_if_present(merged["button"], "mode_button_3_pin", env, "MODE_BUTTON_3_PIN")
    _set_if_present(merged["button"], "mode_button_4_pin", env, "MODE_BUTTON_4_PIN")
    _set_if_present(merged["button"], "mode_button_5_pin", env, "MODE_BUTTON_5_PIN")
    _set_if_present(
        merged["button"],
        "back_button_pin",
        env,
        "BACK_BUTTON_PIN",
        "GPIO_BACK_BUTTON_PIN",
    )
    _set_if_present(
        merged["button"],
        "debounce_seconds",
        env,
        "GPIO_BUTTON_DEBOUNCE_SECONDS",
    )
    _set_if_present(
        merged["button"],
        "hold_seconds",
        env,
        "GPIO_BUTTON_HOLD_SECONDS",
    )

    _set_if_present(merged["led"], "enabled", env, "ENABLE_GPIO_LED")
    _set_if_present(merged["led"], "pin", env, "GPIO_LED_PIN")
    _set_if_present(merged["led"], "active_high", env, "GPIO_LED_ACTIVE_HIGH")

    _set_if_present(merged["ai"], "default_mode", env, "AI_DEFAULT_MODE")
    _set_if_present(
        merged["vision"],
        "screen_optimization",
        env,
        "SCREEN_OPTIMIZATION",
    )

    _set_if_present(merged["startup"], "behavior", env, "STARTUP_BEHAVIOR")
    _set_if_present(merged["startup"], "url", env, "STARTUP_URL")
    _set_if_present(merged["reliability"], "log_level", env, "RELIABILITY_LOG_LEVEL")
    _set_if_present(merged["reliability"], "log_max_bytes", env, "RELIABILITY_LOG_MAX_BYTES")
    _set_if_present(
        merged["reliability"],
        "log_backup_count",
        env,
        "RELIABILITY_LOG_BACKUP_COUNT",
    )
    _set_if_present(
        merged["reliability"],
        "health_monitor_enabled",
        env,
        "RELIABILITY_HEALTH_MONITOR_ENABLED",
    )
    _set_if_present(
        merged["reliability"],
        "health_check_interval_seconds",
        env,
        "RELIABILITY_HEALTH_CHECK_INTERVAL_SECONDS",
    )
    _set_if_present(
        merged["reliability"],
        "camera_probe_interval_seconds",
        env,
        "RELIABILITY_CAMERA_PROBE_INTERVAL_SECONDS",
    )
    _set_if_present(
        merged["reliability"],
        "openai_timeout_seconds",
        env,
        "RELIABILITY_OPENAI_TIMEOUT_SECONDS",
    )
    _set_if_present(
        merged["reliability"],
        "openai_retry_attempts",
        env,
        "RELIABILITY_OPENAI_RETRY_ATTEMPTS",
    )
    _set_if_present(
        merged["reliability"],
        "openai_retry_backoff_seconds",
        env,
        "RELIABILITY_OPENAI_RETRY_BACKOFF_SECONDS",
    )
    return merged


def _set_if_present(
    target: dict[str, Any],
    key: str,
    env: Mapping[str, str],
    *names: str,
) -> None:
    """Copy the first present environment variable onto the merged config."""
    for name in names:
        if name in env and str(env[name]).strip() != "":
            target[key] = env[name]
            return


def _nested_get(source: Mapping[str, Any], *keys: str) -> Any:
    """Safely read a nested mapping path."""
    current: Any = source
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _parse_bool(value: Any, field_name: str) -> bool:
    """Parse a YAML or environment boolean value."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise SettingsError(
        f"Invalid boolean for '{field_name}': {value!r}."
    )


def _parse_int(
    value: Any,
    field_name: str,
    minimum: int | None = None,
) -> int:
    """Parse an integer with optional lower bound."""
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SettingsError(f"Invalid integer for '{field_name}': {value!r}.") from exc

    if minimum is not None and parsed < minimum:
        raise SettingsError(
            f"Value for '{field_name}' must be at least {minimum}, got {parsed}."
        )
    return parsed


def _parse_optional_int(
    value: Any,
    field_name: str,
    minimum: int | None = None,
) -> int | None:
    """Parse an optional integer with optional lower bound."""
    if value is None:
        return None
    return _parse_int(value, field_name, minimum=minimum)


def _parse_float(
    value: Any,
    field_name: str,
    minimum: float | None = None,
) -> float:
    """Parse a float with optional lower bound."""
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise SettingsError(f"Invalid number for '{field_name}': {value!r}.") from exc

    if minimum is not None and parsed < minimum:
        raise SettingsError(
            f"Value for '{field_name}' must be at least {minimum}, got {parsed}."
        )
    return parsed


def _parse_choice(value: Any, valid_values: tuple[str, ...], field_name: str) -> str:
    """Normalize and validate a text choice."""
    text = _parse_text(value, field_name).lower()
    if text not in valid_values:
        expected = ", ".join(valid_values)
        raise SettingsError(
            f"Invalid value for '{field_name}': {value!r}. Expected one of: {expected}."
        )
    return text


def _parse_log_level(value: Any, field_name: str) -> str:
    """Parse and validate a supported Python logging level name."""
    text = _parse_text(value, field_name).upper()
    if text not in VALID_LOG_LEVELS:
        expected = ", ".join(VALID_LOG_LEVELS)
        raise SettingsError(
            f"Invalid value for '{field_name}': {value!r}. Expected one of: {expected}."
        )
    return text


def _parse_text(value: Any, field_name: str) -> str:
    """Parse a non-empty string value."""
    if not isinstance(value, str):
        raise SettingsError(f"Invalid text value for '{field_name}': {value!r}.")
    text = value.strip()
    if not text:
        raise SettingsError(f"Value for '{field_name}' cannot be empty.")
    return text


def _parse_mode(value: Any, field_name: str) -> str:
    """Parse and normalize a supported assistant mode."""
    raw_mode = _parse_text(value, field_name)
    try:
        return normalize_mode(raw_mode)
    except ValueError as exc:
        expected = ", ".join(get_available_modes())
        raise SettingsError(
            f"Invalid value for '{field_name}': {value!r}. Expected one of: {expected}."
        ) from exc


def _parse_exposure(value: Any) -> str | int:
    """Parse a camera exposure setting."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "auto":
            return "auto"
        try:
            parsed = int(normalized)
        except ValueError as exc:
            raise SettingsError(
                f"Invalid value for 'camera.exposure': {value!r}. Use 'auto' or an integer microsecond value."
            ) from exc
        if parsed <= 0:
            raise SettingsError("camera.exposure must be 'auto' or a positive integer.")
        return parsed

    try:
        parsed_int = int(value)
    except (TypeError, ValueError) as exc:
        raise SettingsError(
            f"Invalid value for 'camera.exposure': {value!r}. Use 'auto' or an integer microsecond value."
        ) from exc

    if parsed_int <= 0:
        raise SettingsError("camera.exposure must be 'auto' or a positive integer.")
    return parsed_int
