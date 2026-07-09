"""Unit tests for the optional GPIO LED indicator."""

from __future__ import annotations

import unittest

from hardware.led import LEDIndicator
from hardware.status import DeviceState


class FakeLED:
    """Small fake gpiozero LED for behavior tests."""

    def __init__(self, pin: int, active_high: bool = True) -> None:
        self.pin = pin
        self.active_high = active_high
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def on(self) -> None:
        self.calls.append(("on", (), {}))

    def blink(self, *args: object, **kwargs: object) -> None:
        self.calls.append(("blink", args, kwargs))

    def close(self) -> None:
        self.calls.append(("close", (), {}))


class LEDIndicatorTests(unittest.TestCase):
    """Verify state-to-pattern mapping and no-op fallback behavior."""

    def test_ready_and_done_use_solid_on(self) -> None:
        indicator = LEDIndicator(
            pin=27,
            enabled=True,
            active_high=True,
            led_factory=FakeLED,
        )

        indicator.set_state(DeviceState.READY)
        indicator.set_state(DeviceState.DONE)

        self.assertEqual(indicator._device.calls[0][0], "on")
        self.assertEqual(indicator._device.calls[1][0], "on")

    def test_capture_processing_and_error_use_expected_blink_patterns(self) -> None:
        indicator = LEDIndicator(
            pin=27,
            enabled=True,
            active_high=True,
            led_factory=FakeLED,
        )

        indicator.set_state(DeviceState.CAPTURING)
        indicator.set_state(DeviceState.PROCESSING)
        indicator.set_state(DeviceState.ERROR)

        self.assertEqual(
            indicator._device.calls,
            [
                ("blink", (), {"on_time": 0.4, "off_time": 0.4, "background": True}),
                ("blink", (), {"on_time": 0.2, "off_time": 0.2, "background": True}),
                ("blink", (), {"on_time": 0.1, "off_time": 0.1, "background": True}),
            ],
        )

    def test_create_falls_back_to_disabled_noop_when_led_unavailable(self) -> None:
        def failing_factory(*args: object, **kwargs: object) -> object:
            raise RuntimeError("no gpio")

        indicator = LEDIndicator.create(
            pin=27,
            enabled=True,
            active_high=True,
            led_factory=failing_factory,
        )

        self.assertFalse(indicator.available)
        self.assertIn("Could not initialize GPIO LED", indicator.disabled_reason or "")
        indicator.set_state(DeviceState.ERROR)
