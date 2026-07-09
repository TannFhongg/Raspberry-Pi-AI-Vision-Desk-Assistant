"""App-level tests for the Phase 11 hardware state flow."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ENABLE_GPIO_BUTTON", "0")
os.environ.setdefault("ENABLE_GPIO_LED", "0")

import app as app_module

from hardware.status import DeviceState


class Phase11AppIntegrationTests(unittest.TestCase):
    """Verify the shared app state behavior used by hardware-only control."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="phase11-app-test-"))
        self.ui_state_path = self.temp_dir / "ui_state.json"
        self.latest_result_path = self.temp_dir / "latest_result.txt"
        self.led_indicator = _FakeLEDIndicator()
        self.path_patcher = patch.object(app_module, "UI_STATE_PATH", self.ui_state_path)
        self.result_patcher = patch.object(app_module, "LATEST_RESULT_PATH", self.latest_result_path)
        self.led_patcher = patch.object(app_module, "LED_INDICATOR", self.led_indicator)
        self.path_patcher.start()
        self.result_patcher.start()
        self.led_patcher.start()
        app_module.app.config["TESTING"] = True
        app_module.RUNNING = False
        app_module.GPIO_TRIGGER = None
        app_module._reset_ui_state(clear_saved_result=False)

    def tearDown(self) -> None:
        self.path_patcher.stop()
        self.result_patcher.stop()
        self.led_patcher.stop()

    def test_home_result_and_error_screens_refresh_when_gpio_listener_is_active(self) -> None:
        client = app_module.app.test_client()
        app_module.GPIO_TRIGGER = object()

        cases = (
            (DeviceState.READY, {"detail": "Tap Capture or press the button"}, b"window.location.reload()"),
            (DeviceState.DONE, {"answer": "Answer stays visible"}, b"window.location.reload()"),
            (
                DeviceState.ERROR,
                {"error": "Camera not found", "error_detail": "Camera backend failed"},
                b"window.location.reload()",
            ),
        )

        for state, extra, expected in cases:
            with self.subTest(state=state):
                app_module._write_device_state(
                    state,
                    selected_mode="read_text",
                    detail=extra.get("detail"),
                    answer=extra.get("answer", ""),
                    error=extra.get("error", ""),
                    error_detail=extra.get("error_detail", ""),
                )
                response = client.get("/")
                self.assertEqual(response.status_code, 200)
                self.assertIn(expected, response.data)

    def test_clear_route_resets_ui_state_and_clears_saved_result(self) -> None:
        client = app_module.app.test_client()
        self.latest_result_path.write_text("Old result\n", encoding="utf-8")
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="read_text",
            answer="Persistent answer",
            current_step=4,
        )

        response = client.post("/clear")

        self.assertEqual(response.status_code, 302)
        state = app_module._load_ui_state()
        self.assertEqual(state["device_state"], "READY")
        self.assertEqual(state["screen"], "home")
        self.assertEqual(state["answer"], "")
        self.assertEqual(state["error"], "")

        latest_result = self.latest_result_path.read_text(encoding="utf-8")
        self.assertIn("Status: cleared", latest_result)
        self.assertIn("Message: No result available", latest_result)

    def test_done_answer_stays_visible_after_render(self) -> None:
        client = app_module.app.test_client()
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="solve_problem",
            answer="Line one",
            current_step=4,
        )

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Line one", response.data)
        state = app_module._load_ui_state()
        self.assertEqual(state["device_state"], "DONE")
        self.assertEqual(state["screen"], "result")
        self.assertEqual(state["answer"], "Line one")


class _FakeLEDIndicator:
    """No-op LED used to isolate app state tests from GPIO behavior."""

    def __init__(self) -> None:
        self.states: list[DeviceState | str] = []

    def set_state(self, device_state: DeviceState | str) -> None:
        self.states.append(device_state)
