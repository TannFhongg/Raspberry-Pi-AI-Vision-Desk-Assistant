"""GPIO bridge that routes hardware events into Qt queued signals."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from hardware import GPIOButtonError, GPIOButtonTrigger
from qt_app.runtime import VisionDeskRuntime

LOGGER = logging.getLogger(__name__)


class GPIOController(QObject):
    """Route shared GPIO button callbacks into Qt signals only."""

    captureRequested = Signal()
    backRequested = Signal()
    clearRequested = Signal()
    modeSelected = Signal(str)

    def __init__(self, runtime: VisionDeskRuntime, *, get_device_state, parent=None) -> None:
        super().__init__(parent)
        self.runtime = runtime
        self.get_device_state = get_device_state
        self._trigger: GPIOButtonTrigger | None = None

    def start(self) -> None:
        """Start hardware button listeners when setup and settings allow it."""
        if (
            self.runtime.mock_hardware
            or not self.runtime.settings.button.enabled
            or not self.runtime.setup_is_complete()
            or self._trigger is not None
        ):
            return
        mode_buttons = {
            "read_text": self.runtime.settings.button.mode_button_1_pin,
            "summarize_document": self.runtime.settings.button.mode_button_2_pin,
            "analyze_image": self.runtime.settings.button.mode_button_3_pin,
            "professional_assistant": self.runtime.settings.button.mode_button_4_pin,
            "solve_problem": self.runtime.settings.button.mode_button_5_pin,
        }
        configured_mode_buttons = {
            mode: pin
            for mode, pin in mode_buttons.items()
            if pin is not None
        }
        try:
            self._trigger = GPIOButtonTrigger(
                pin=self.runtime.settings.button.pin,
                debounce_seconds=self.runtime.settings.button.debounce_seconds,
                hold_seconds=self.runtime.settings.button.hold_seconds,
                back_button_pin=self.runtime.settings.button.back_button_pin,
                mode_buttons=configured_mode_buttons,
                mode_action=self._emit_mode_selected,
                trigger_action=self._emit_capture_requested,
                back_action=self._emit_back_requested,
                clear_action=self._emit_clear_requested,
                get_device_state=self.get_device_state,
                led_indicator=self.runtime.led_indicator,
            )
            self._trigger.start()
        except GPIOButtonError as exc:
            self._trigger = None
            LOGGER.warning("GPIO button listener disabled: %s", exc)

    def stop(self) -> None:
        """Stop the GPIO listener if it was started."""
        trigger = self._trigger
        self._trigger = None
        if trigger is not None:
            trigger.close()

    def restart_if_needed(self) -> None:
        """Restart the hardware listener after setup completes."""
        self.stop()
        self.start()

    def _emit_mode_selected(self, mode: str) -> bool:
        self.modeSelected.emit(mode)
        return True

    def _emit_capture_requested(self) -> bool:
        self.captureRequested.emit()
        return True

    def _emit_back_requested(self) -> bool:
        self.backRequested.emit()
        return True

    def _emit_clear_requested(self) -> bool:
        self.clearRequested.emit()
        return True

