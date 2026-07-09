"""GPIO button controller with short-press capture and long-press clear."""

from __future__ import annotations

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
from pipeline import PipelineError, PipelineResult, run_capture_analyze, save_latest_result

ButtonFactory = Callable[..., Any]


class GPIOButtonError(Exception):
    """Friendly error raised when GPIO button setup or runtime fails."""


class GPIOButtonTrigger:
    """GPIO button controller with debounce, hold detection, and busy guards."""

    def __init__(
        self,
        pin: int | None = None,
        debounce_seconds: float | None = None,
        hold_seconds: float | None = None,
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
        result_path: str = "data/latest_result.txt",
        trigger_action: Callable[[], bool] | None = None,
        clear_action: Callable[[], bool] | None = None,
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
        self.get_device_state = get_device_state
        self.led_indicator = led_indicator
        self.button_factory = button_factory
        self._lock = threading.Lock()
        self._busy = False
        self._hold_fired = False
        self._button = None
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
        except Exception as exc:
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

    def _handle_hold(self) -> None:
        """Trigger a clear action for a long press and suppress short release."""
        with self._lock:
            self._hold_fired = True

        if self._input_is_blocked():
            print("Device is busy. Ignoring button input.")
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
                return
            if is_busy_device_state(self._current_device_state()):
                print("Device is busy. Ignoring button input.")
                return
            self._busy = True

        worker = threading.Thread(
            target=self._run_trigger_action,
            daemon=True,
            name="gpio-button-trigger",
        )
        worker.start()

    def _run_trigger_action(self) -> None:
        """Run the configured short-press action behind a duplicate-trigger guard."""
        try:
            started = self.trigger_action()
            if not started and not self._managed_pipeline:
                print("Pipeline is already running. Ignoring button press.")
            elif started and not self._managed_pipeline:
                print("Button pressed")
        except Exception as exc:
            print(f"Error: {exc}")
        finally:
            with self._lock:
                self._busy = False

    def _run_clear_action(self) -> None:
        """Run the configured long-press clear action."""
        try:
            cleared = self.clear_action()
            if cleared and not self._managed_pipeline:
                print("Result cleared")
        except Exception as exc:
            print(f"Error: {exc}")

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
        try:
            self._set_managed_state(DeviceState.CAPTURING)
            result = run_capture_analyze(
                mode=self.mode,
                backend=self.backend,
                camera_index=self.camera_index,
                width=self.width,
                height=self.height,
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
        except (PipelineError, Exception) as exc:
            error_message = str(exc)
            print(f"Error: {error_message}")
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
