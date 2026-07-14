"""GPIO button controller with capture, mode, and non-touch navigation actions."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from ai.modes import normalize_mode
from config import load_device_settings
from hardware.led import LEDIndicator
from hardware.status import (
    DeviceState,
    clear_latest_result_file,
    coerce_device_state,
    is_busy_device_state,
)
from pipeline import (
    PipelineError,
    PipelineResult,
    build_capture_session_paths,
    run_capture_analyze,
    save_latest_result,
)
from visiondesk.paths import resolve_visiondesk_paths

ButtonFactory = Callable[..., Any]
LOGGER = logging.getLogger(__name__)
DEFAULT_RESULT_PATH = str(resolve_visiondesk_paths().latest_result_path)


class GPIOButtonError(Exception):
    """Friendly error raised when GPIO button setup or runtime fails."""


class GPIOButtonTrigger:
    """GPIO control panel with debounce, hold detection, and busy guards."""

    def __init__(
        self,
        pin: int | None = None,
        debounce_seconds: float | None = None,
        hold_seconds: float | None = None,
        back_button_pin: int | None = None,
        navigation_up_pin: int | None = None,
        navigation_down_pin: int | None = None,
        navigation_select_pin: int | None = None,
        mode: str | None = None,
        backend: str | None = None,
        camera_index: int | None = None,
        width: int | None = None,
        height: int | None = None,
        grayscale: bool | None = None,
        max_dimension: int | None = None,
        autofocus_mode: str | None = None,
        exposure: str | int | None = None,
        brightness: float | None = None,
        capture_delay_seconds: float | None = None,
        result_path: str = DEFAULT_RESULT_PATH,
        trigger_action: Callable[[], bool] | None = None,
        clear_action: Callable[[], bool] | None = None,
        back_action: Callable[[], bool] | None = None,
        navigation_up_action: Callable[[], bool] | None = None,
        navigation_down_action: Callable[[], bool] | None = None,
        navigation_select_action: Callable[[], bool] | None = None,
        mode_buttons: dict[str, int] | None = None,
        mode_action: Callable[[str], bool] | None = None,
        get_device_state: Callable[[], DeviceState | str] | None = None,
        led_indicator: LEDIndicator | None = None,
        button_factory: ButtonFactory | None = None,
    ) -> None:
        settings = load_device_settings()
        camera_settings = settings.camera
        button_settings = settings.button
        self.pin = button_settings.pin if pin is None else pin
        self.debounce_seconds = (
            button_settings.debounce_seconds if debounce_seconds is None else debounce_seconds
        )
        self.hold_seconds = button_settings.hold_seconds if hold_seconds is None else hold_seconds
        self.mode = normalize_mode(settings.ai.default_mode if mode is None else mode)
        self.backend = camera_settings.backend if backend is None else backend
        self.camera_index = camera_settings.index if camera_index is None else camera_index
        self.width = camera_settings.resolution.width if width is None else width
        self.height = camera_settings.resolution.height if height is None else height
        self.grayscale = camera_settings.grayscale if grayscale is None else grayscale
        self.max_dimension = (
            camera_settings.max_dimension if max_dimension is None else max_dimension
        )
        self.autofocus_mode = (
            camera_settings.autofocus_mode if autofocus_mode is None else autofocus_mode
        )
        self.exposure = camera_settings.exposure if exposure is None else exposure
        self.brightness = camera_settings.brightness if brightness is None else brightness
        self.capture_delay_seconds = (
            camera_settings.capture_delay_seconds
            if capture_delay_seconds is None
            else capture_delay_seconds
        )
        self.result_path = result_path
        self.trigger_action = trigger_action or self._run_managed_pipeline
        self.clear_action = clear_action or self._run_managed_clear
        self.mode_buttons = self._normalize_mode_buttons(mode_buttons)
        reserved_action_pins = {self.pin}
        reserved_action_pins.update(self.mode_buttons.values())
        configured_back_pin = (
            button_settings.back_button_pin if back_button_pin is None else back_button_pin
        )
        self.back_button_pin = self._normalize_auxiliary_pin(
            configured_back_pin,
            reserved_pins=reserved_action_pins,
        )
        if self.back_button_pin is not None:
            reserved_action_pins.add(self.back_button_pin)
        navigation_pin_inputs = {
            "up": (
                getattr(button_settings, "navigation_up_pin", None)
                if navigation_up_pin is None
                else navigation_up_pin
            ),
            "down": (
                getattr(button_settings, "navigation_down_pin", None)
                if navigation_down_pin is None
                else navigation_down_pin
            ),
            "select": (
                getattr(button_settings, "navigation_select_pin", None)
                if navigation_select_pin is None
                else navigation_select_pin
            ),
        }
        self.navigation_pins: dict[str, int] = {}
        for action, configured_pin in navigation_pin_inputs.items():
            resolved_pin = self._normalize_auxiliary_pin(
                configured_pin,
                reserved_pins=reserved_action_pins,
            )
            if resolved_pin is not None:
                self.navigation_pins[action] = resolved_pin
                reserved_action_pins.add(resolved_pin)
        self.back_action = back_action or self._run_managed_back
        self.navigation_actions = {
            "up": navigation_up_action or (lambda: False),
            "down": navigation_down_action or (lambda: False),
            "select": navigation_select_action or (lambda: False),
        }
        self.mode_action = mode_action or self._set_managed_mode
        self.get_device_state = get_device_state
        self.led_indicator = led_indicator
        self.button_factory = button_factory
        self._lock = threading.Lock()
        self._busy = False
        self._hold_fired = False
        self._button = None
        self._mode_button_devices: list[Any] = []
        self._back_button = None
        self._navigation_button_devices: list[Any] = []
        self._managed_pipeline = trigger_action is None
        self._device_state = DeviceState.READY

        if self.led_indicator is not None and self._managed_pipeline:
            self.led_indicator.set_state(DeviceState.READY)

    def start(self) -> None:
        """Initialize gpiozero and begin listening for button interactions."""
        button_class = self.button_factory or _import_button_factory()

        try:
            self._button = button_class(
                self.pin,
                pull_up=True,
                bounce_time=self.debounce_seconds,
                hold_time=self.hold_seconds,
            )
            if hasattr(self._button, "hold_repeat"):
                self._button.hold_repeat = False
            self._button.when_held = self._handle_hold
            self._button.when_released = self._handle_release
            self._bind_mode_buttons(button_class)
            self._bind_back_button(button_class)
            self._bind_navigation_buttons(button_class)
            LOGGER.info(
                "GPIO button listener started capture_pin=%s mode_pins=%s back_pin=%s navigation_pins=%s",
                self.pin,
                self.mode_buttons,
                self.back_button_pin,
                self.navigation_pins,
            )
        except Exception as exc:
            self.close()
            raise GPIOButtonError(
                f"Could not initialize GPIO button on pin {self.pin}. {exc}"
            ) from exc

    def wait_forever(self) -> None:
        """Keep the listener alive until the process is interrupted."""
        if self._button is None:
            raise GPIOButtonError("GPIO button listener has not been started yet.")

        try:
            while True:
                time.sleep(1)
        finally:
            self.close()

    def close(self) -> None:
        """Clean up the GPIO button resource when the script exits."""
        if self._button is not None:
            try:
                self._button.close()
            except Exception:
                pass
            self._button = None
        for button in self._mode_button_devices:
            try:
                button.close()
            except Exception:
                pass
        self._mode_button_devices = []
        if self._back_button is not None:
            try:
                self._back_button.close()
            except Exception:
                pass
            self._back_button = None
        for button in self._navigation_button_devices:
            try:
                button.close()
            except Exception:
                pass
        self._navigation_button_devices = []

    def _bind_mode_buttons(self, button_class: ButtonFactory) -> None:
        """Create optional mode-selection buttons alongside the capture button."""
        for mode, pin in self.mode_buttons.items():
            button = button_class(
                pin,
                pull_up=True,
                bounce_time=self.debounce_seconds,
            )
            button.when_released = lambda mode=mode: self._handle_mode_release(mode)
            self._mode_button_devices.append(button)

    def _bind_back_button(self, button_class: ButtonFactory) -> None:
        """Create an optional back button that returns the device to mode selection."""
        if self.back_button_pin is None:
            return

        self._back_button = button_class(
            self.back_button_pin,
            pull_up=True,
            bounce_time=self.debounce_seconds,
        )
        self._back_button.when_released = self._handle_back_release

    def _bind_navigation_buttons(self, button_class: ButtonFactory) -> None:
        """Bind optional Up, Down, and Select buttons for non-touch navigation."""
        for action, pin in self.navigation_pins.items():
            button = button_class(
                pin,
                pull_up=True,
                bounce_time=self.debounce_seconds,
            )
            button.when_released = lambda action=action: self._handle_navigation_release(action)
            self._navigation_button_devices.append(button)

    def _normalize_mode_buttons(self, mode_buttons: dict[str, int] | None) -> dict[str, int]:
        """Return a cleaned map of mode ids to GPIO pins."""
        if not mode_buttons:
            return {}

        normalized: dict[str, int] = {}
        for mode, pin in mode_buttons.items():
            if not isinstance(mode, str):
                continue
            try:
                resolved_pin = int(pin)
            except (TypeError, ValueError):
                continue
            if resolved_pin < 0 or resolved_pin == self.pin:
                continue
            normalized[mode.strip().lower()] = resolved_pin
        return normalized

    def _normalize_auxiliary_pin(
        self,
        pin: int | None,
        *,
        reserved_pins: set[int],
    ) -> int | None:
        """Return a cleaned optional GPIO pin that does not overlap reserved pins."""
        if pin is None:
            return None

        try:
            resolved_pin = int(pin)
        except (TypeError, ValueError):
            return None

        if resolved_pin < 0 or resolved_pin in reserved_pins:
            return None
        return resolved_pin

    def _handle_hold(self) -> None:
        """Trigger a clear action for a long press and suppress short release."""
        with self._lock:
            self._hold_fired = True

        if self._input_is_blocked():
            print("Device is busy. Ignoring button input.")
            LOGGER.info("Ignoring GPIO hold because device is busy pin=%s", self.pin)
            return

        worker = threading.Thread(
            target=self._run_clear_action,
            daemon=True,
            name="gpio-button-clear",
        )
        worker.start()

    def _handle_release(self) -> None:
        """Trigger a capture action for short presses when the device is idle."""
        with self._lock:
            if self._hold_fired:
                self._hold_fired = False
                return
            if self._busy:
                print("Pipeline is already running. Ignoring button press.")
                LOGGER.info("Ignoring GPIO press because pipeline is already running pin=%s", self.pin)
                return
            if is_busy_device_state(self._current_device_state()):
                print("Device is busy. Ignoring button input.")
                LOGGER.info("Ignoring GPIO press because device state is busy pin=%s", self.pin)
                return
            self._busy = True

        worker = threading.Thread(
            target=self._run_trigger_action,
            daemon=True,
            name="gpio-button-trigger",
        )
        worker.start()

    def _handle_mode_release(self, mode: str) -> None:
        """Trigger a mode-selection action when the device is idle."""
        if self._input_is_blocked():
            print("Device is busy. Ignoring button input.")
            LOGGER.info("Ignoring GPIO mode press because device is busy mode=%s", mode)
            return

        worker = threading.Thread(
            target=self._run_mode_action,
            args=(mode,),
            daemon=True,
            name=f"gpio-mode-{mode}",
        )
        worker.start()

    def _handle_back_release(self) -> None:
        """Trigger a back action when the device is idle."""
        if self._input_is_blocked():
            print("Device is busy. Ignoring button input.")
            LOGGER.info("Ignoring GPIO back press because device is busy pin=%s", self.back_button_pin)
            return

        worker = threading.Thread(
            target=self._run_back_action,
            daemon=True,
            name="gpio-button-back",
        )
        worker.start()

    def _handle_navigation_release(self, action: str) -> None:
        """Trigger a non-touch navigation action when the device is idle."""
        if action not in self.navigation_actions:
            return
        if self._input_is_blocked():
            print("Device is busy. Ignoring button input.")
            LOGGER.info("Ignoring GPIO navigation press because device is busy action=%s", action)
            return

        worker = threading.Thread(
            target=self._run_navigation_action,
            args=(action,),
            daemon=True,
            name=f"gpio-navigation-{action}",
        )
        worker.start()

    def _run_trigger_action(self) -> None:
        """Run the configured short-press action behind a duplicate-trigger guard."""
        try:
            started = self.trigger_action()
            if not started and not self._managed_pipeline:
                print("Pipeline is already running. Ignoring button press.")
                LOGGER.info("External trigger_action rejected duplicate GPIO press pin=%s", self.pin)
            elif started and not self._managed_pipeline:
                print("Button pressed")
                LOGGER.info("GPIO button press accepted pin=%s", self.pin)
        except Exception as exc:
            print(f"Error: {exc}")
            LOGGER.exception("GPIO trigger action failed pin=%s", self.pin)
        finally:
            with self._lock:
                self._busy = False

    def _run_clear_action(self) -> None:
        """Run the configured long-press clear action."""
        try:
            cleared = self.clear_action()
            if cleared and not self._managed_pipeline:
                print("Result cleared")
                LOGGER.info("GPIO clear action succeeded pin=%s", self.pin)
        except Exception as exc:
            print(f"Error: {exc}")
            LOGGER.exception("GPIO clear action failed pin=%s", self.pin)

    def _run_back_action(self) -> None:
        """Run the configured back action."""
        try:
            changed = self.back_action()
            if changed:
                print("Returned to mode selection")
                LOGGER.info("GPIO back action succeeded pin=%s", self.back_button_pin)
        except Exception as exc:
            print(f"Error: {exc}")
            LOGGER.exception("GPIO back action failed pin=%s", self.back_button_pin)

    def _run_mode_action(self, mode: str) -> None:
        """Run the configured mode-selection action."""
        try:
            changed = self.mode_action(mode)
            if changed:
                print(f"Mode selected: {mode}")
                LOGGER.info("GPIO mode action succeeded mode=%s pin=%s", mode, self.mode_buttons.get(mode))
        except Exception as exc:
            print(f"Error: {exc}")
            LOGGER.exception("GPIO mode action failed mode=%s", mode)

    def _run_navigation_action(self, action: str) -> None:
        """Run one queued navigation action and record whether QML accepted it."""
        try:
            changed = self.navigation_actions[action]()
            if changed:
                LOGGER.info(
                    "GPIO navigation action accepted action=%s pin=%s",
                    action,
                    self.navigation_pins.get(action),
                )
        except Exception:
            LOGGER.exception("GPIO navigation action failed action=%s", action)

    def _current_device_state(self) -> DeviceState:
        """Return the externally-managed or internal device state."""
        if self.get_device_state is None:
            return self._device_state
        try:
            return coerce_device_state(self.get_device_state())
        except Exception:
            return DeviceState.READY

    def _input_is_blocked(self) -> bool:
        """Return True when the button should ignore the current interaction."""
        if self._busy:
            return True
        return is_busy_device_state(self._current_device_state())

    def _run_managed_pipeline(self) -> bool:
        """Run the shared capture-analyze pipeline and save the latest result."""
        print("Button pressed")
        LOGGER.info("Managed GPIO pipeline started pin=%s mode=%s", self.pin, self.mode)
        try:
            self._set_managed_state(DeviceState.CAPTURING)
            captured_path, processed_path = build_capture_session_paths()
            result = run_capture_analyze(
                mode=self.mode,
                backend=self.backend,
                camera_index=self.camera_index,
                width=self.width,
                height=self.height,
                captured_path=str(captured_path),
                processed_path=str(processed_path),
                grayscale=self.grayscale,
                max_dimension=self.max_dimension,
                autofocus_mode=self.autofocus_mode,
                exposure=self.exposure,
                brightness=self.brightness,
                capture_delay_seconds=self.capture_delay_seconds,
                status_callback=self._print_pipeline_status,
            )
            print("Answer received")
            print(f"Camera backend used: {result.camera_backend_used}")
            if result.camera_resolution is not None:
                print(
                    f"Captured resolution: {result.camera_resolution[0]}x{result.camera_resolution[1]}"
                )
            print(f"Captured image: {result.captured_path}")
            print(f"Processed image: {result.processed_path}")
            for warning in result.warnings:
                print(f"Warning: {warning}")
            if result.answer:
                print("\nAI Answer:\n")
                print(result.answer)
            save_latest_result(result, output_path=self.result_path)
            self._set_managed_state(DeviceState.DONE)
            LOGGER.info("Managed GPIO pipeline succeeded pin=%s mode=%s", self.pin, self.mode)
        except (PipelineError, Exception) as exc:
            error_message = str(exc)
            print(f"Error: {error_message}")
            LOGGER.exception("Managed GPIO pipeline failed pin=%s mode=%s", self.pin, self.mode)
            failure_result = PipelineResult(
                captured_path=None,
                processed_path=None,
                answer=error_message,
                mode=self.mode,
                camera_backend_used=self.backend,
                camera_resolution=None,
                status="error",
            )
            save_latest_result(failure_result, output_path=self.result_path)
            self._set_managed_state(DeviceState.ERROR)
        return True

    def _run_managed_clear(self) -> bool:
        """Clear the saved result file and return the managed state to READY."""
        clear_latest_result_file(self.result_path, mode=self.mode)
        self._set_managed_state(DeviceState.READY)
        print("Result cleared")
        LOGGER.info("Managed GPIO result cleared pin=%s mode=%s", self.pin, self.mode)
        return True

    def _run_managed_back(self) -> bool:
        """Return the managed state to READY without clearing the saved result."""
        self._set_managed_state(DeviceState.READY)
        LOGGER.info("Managed GPIO back action succeeded pin=%s mode=%s", self.back_button_pin, self.mode)
        return True

    def _set_managed_mode(self, mode: str) -> bool:
        """Update the managed default mode from a physical mode-selection button."""
        self.mode = normalize_mode(mode)
        self._set_managed_state(DeviceState.MODE_SELECTED)
        LOGGER.info("Managed GPIO mode updated pin=%s mode=%s", self.pin, self.mode)
        return True

    def _set_managed_state(self, device_state: DeviceState | str) -> None:
        """Update internal state and LED feedback for standalone button mode."""
        self._device_state = coerce_device_state(device_state)
        if self.led_indicator is not None:
            self.led_indicator.set_state(self._device_state)

    def _print_pipeline_status(self, message: str) -> None:
        """Translate shared pipeline progress updates into terminal-friendly output."""
        status_messages = {
            "Capturing image...": "Capturing image",
            "Preprocessing image...": "Processing image",
            "Sending image to OpenAI Vision...": "Sending to AI",
        }
        if message == "Capturing image...":
            self._set_managed_state(DeviceState.CAPTURING)
        else:
            self._set_managed_state(DeviceState.PROCESSING)
        print(status_messages.get(message, message))


def _import_button_factory() -> ButtonFactory:
    """Import gpiozero.Button only when GPIO button support is requested."""
    try:
        from gpiozero import Button
    except ImportError as exc:
        raise GPIOButtonError(
            "gpiozero is not available. Install it with: pip install gpiozero"
        ) from exc
    except Exception as exc:
        raise GPIOButtonError(f"GPIO is not available on this system. {exc}") from exc
    return Button
