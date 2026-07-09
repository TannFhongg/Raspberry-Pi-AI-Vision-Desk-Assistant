"""GPIO button listener for triggering the full AI Vision pipeline."""

from __future__ import annotations

import threading
import time
from typing import Callable

from config import load_device_settings
from pipeline import PipelineError, PipelineResult, run_capture_analyze, save_latest_result


class GPIOButtonError(Exception):
    """Friendly error raised when GPIO button setup or runtime fails."""


class GPIOButtonTrigger:
    """Stateful GPIO button trigger that prevents overlapping pipeline runs."""

    def __init__(
        self,
        pin: int | None = None,
        debounce_seconds: float = 0.2,
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
    ) -> None:
        settings = load_device_settings()
        camera_settings = settings.camera
        self.pin = settings.button.pin if pin is None else pin
        self.debounce_seconds = debounce_seconds
        self.mode = settings.ai.default_mode if mode is None else mode
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
        self.trigger_action = trigger_action
        self._lock = threading.Lock()
        self._busy = False
        self._button = None

    def start(self) -> None:
        """Initialize gpiozero and begin listening for button presses."""
        try:
            from gpiozero import Button
        except ImportError as exc:
            raise GPIOButtonError(
                "gpiozero is not available. Install it with: pip install gpiozero"
            ) from exc
        except Exception as exc:
            raise GPIOButtonError(f"GPIO is not available on this system. {exc}") from exc

        try:
            self._button = Button(
                self.pin,
                pull_up=True,
                bounce_time=self.debounce_seconds,
            )
            self._button.when_pressed = self._handle_press
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

    def _handle_press(self) -> None:
        """Trigger a background pipeline run when the button is pressed."""
        if self.trigger_action is not None:
            self._handle_custom_trigger()
            return

        with self._lock:
            if self._busy:
                print("Pipeline is already running. Ignoring button press.")
                return
            self._busy = True

        worker = threading.Thread(target=self._run_pipeline, daemon=True)
        worker.start()

    def _handle_custom_trigger(self) -> None:
        """Run an externally-managed capture action from the same button press."""
        try:
            started = self.trigger_action()
        except Exception as exc:
            print(f"Error: {exc}")
            return

        if started:
            print("Button pressed")
        else:
            print("Pipeline is already running. Ignoring button press.")

    def _run_pipeline(self) -> None:
        """Run the shared capture-analyze pipeline and save the latest result."""
        try:
            print("Button pressed")
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
        finally:
            with self._lock:
                self._busy = False

    def _print_pipeline_status(self, message: str) -> None:
        """Translate shared pipeline progress updates into GPIO-friendly terminal output."""
        status_messages = {
            "Capturing image...": "Capturing image",
            "Preprocessing image...": "Processing image",
            "Sending image to OpenAI Vision...": "Sending to AI",
        }
        print(status_messages.get(message, message))
