"""Unit tests for Phase 11 GPIO button behavior."""

from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import patch

from hardware.button import GPIOButtonTrigger
from hardware.status import DeviceState


class GPIOButtonTriggerTests(unittest.TestCase):
    """Verify short press, long press, busy-state, and recovery behavior."""

    def test_short_press_triggers_capture_once(self) -> None:
        called = threading.Event()
        calls: list[str] = []

        def trigger_action() -> bool:
            calls.append("capture")
            called.set()
            return True

        trigger = _build_trigger(
            trigger_action=trigger_action,
            clear_action=lambda: True,
            get_device_state=lambda: DeviceState.READY,
        )

        trigger._handle_release()

        self.assertTrue(called.wait(1))
        self.assertEqual(calls, ["capture"])

    def test_long_press_clears_once_and_suppresses_short_press(self) -> None:
        cleared = threading.Event()
        capture_calls: list[str] = []
        clear_calls: list[str] = []

        def clear_action() -> bool:
            clear_calls.append("clear")
            cleared.set()
            return True

        trigger = _build_trigger(
            trigger_action=lambda: capture_calls.append("capture") or True,
            clear_action=clear_action,
            get_device_state=lambda: DeviceState.DONE,
        )

        trigger._handle_hold()
        self.assertTrue(cleared.wait(1))
        trigger._handle_release()
        time.sleep(0.05)

        self.assertEqual(capture_calls, [])
        self.assertEqual(clear_calls, ["clear"])

    def test_duplicate_short_press_is_ignored_while_action_is_busy(self) -> None:
        started = threading.Event()
        release_gate = threading.Event()
        calls: list[str] = []

        def trigger_action() -> bool:
            calls.append("capture")
            started.set()
            release_gate.wait(1)
            return True

        trigger = _build_trigger(
            trigger_action=trigger_action,
            clear_action=lambda: True,
            get_device_state=lambda: DeviceState.READY,
        )

        trigger._handle_release()
        self.assertTrue(started.wait(1))
        trigger._handle_release()
        release_gate.set()
        time.sleep(0.05)

        self.assertEqual(calls, ["capture"])

    def test_input_is_ignored_during_processing_states(self) -> None:
        capture_calls: list[str] = []
        clear_calls: list[str] = []

        trigger = _build_trigger(
            trigger_action=lambda: capture_calls.append("capture") or True,
            clear_action=lambda: clear_calls.append("clear") or True,
            get_device_state=lambda: DeviceState.PROCESSING,
        )

        trigger._handle_release()
        trigger._handle_hold()
        time.sleep(0.05)

        self.assertEqual(capture_calls, [])
        self.assertEqual(clear_calls, [])

    def test_failure_releases_busy_guard_for_next_press(self) -> None:
        first_call = threading.Event()
        second_call = threading.Event()
        calls = {"count": 0}

        def trigger_action() -> bool:
            calls["count"] += 1
            if calls["count"] == 1:
                first_call.set()
                raise RuntimeError("boom")
            second_call.set()
            return True

        trigger = _build_trigger(
            trigger_action=trigger_action,
            clear_action=lambda: True,
            get_device_state=lambda: DeviceState.READY,
        )

        trigger._handle_release()
        self.assertTrue(first_call.wait(1))
        time.sleep(0.05)
        trigger._handle_release()

        self.assertTrue(second_call.wait(1))
        self.assertEqual(calls["count"], 2)


def _build_trigger(
    *,
    trigger_action,
    clear_action,
    get_device_state,
) -> GPIOButtonTrigger:
    """Create a trigger with patched device settings for deterministic tests."""
    with patch("hardware.button.load_device_settings") as mock_settings:
        mock_settings.return_value = _FakeSettings()
        return GPIOButtonTrigger(
            trigger_action=trigger_action,
            clear_action=clear_action,
            get_device_state=get_device_state,
        )


class _FakeSettings:
    """Minimal settings object for button tests."""

    def __init__(self) -> None:
        self.button = _FakeButtonSettings()
        self.camera = _FakeCameraSettings()
        self.ai = _FakeAISettings()


class _FakeButtonSettings:
    enabled = True
    pin = 17
    debounce_seconds = 0.15
    hold_seconds = 1.2


class _FakeCameraSettings:
    backend = "auto"
    index = 0
    resolution = type("Resolution", (), {"width": 4608, "height": 2592})()
    grayscale = False
    max_dimension = 1600
    autofocus_mode = "continuous"
    exposure = "auto"
    brightness = 0.0
    capture_delay_seconds = 1.0


class _FakeAISettings:
    default_mode = "read_text"
