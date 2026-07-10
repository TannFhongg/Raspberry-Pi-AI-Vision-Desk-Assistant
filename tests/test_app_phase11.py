"""App-level tests for the Raspberry Pi hardware-first screen flow."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ENABLE_GPIO_BUTTON", "0")
os.environ.setdefault("ENABLE_GPIO_LED", "0")
os.environ.setdefault("RELIABILITY_HEALTH_MONITOR_ENABLED", "0")

import app as app_module

from hardware.status import DeviceState


class Phase11AppIntegrationTests(unittest.TestCase):
    """Verify the shared app state behavior used by hardware-first control."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="phase11-app-test-"))
        self.ui_state_path = self.temp_dir / "ui_state.json"
        self.latest_result_path = self.temp_dir / "latest_result.txt"
        self.preview_path = self.temp_dir / "captured.jpg"
        self.processed_path = self.temp_dir / "processed.jpg"
        self.led_indicator = _FakeLEDIndicator()
        self.path_patcher = patch.object(app_module, "UI_STATE_PATH", self.ui_state_path)
        self.result_patcher = patch.object(app_module, "LATEST_RESULT_PATH", self.latest_result_path)
        self.preview_patcher = patch.object(app_module, "CAPTURED_IMAGE_PATH", self.preview_path)
        self.processed_patcher = patch.object(app_module, "PROCESSED_IMAGE_PATH", self.processed_path)
        self.led_patcher = patch.object(app_module, "LED_INDICATOR", self.led_indicator)
        self.path_patcher.start()
        self.result_patcher.start()
        self.preview_patcher.start()
        self.processed_patcher.start()
        self.led_patcher.start()
        app_module.app.config["TESTING"] = True
        app_module.RUNNING = False
        app_module.GPIO_TRIGGER = None
        app_module.HEALTH_MONITOR = None
        app_module._reset_ui_state(clear_saved_result=False)

    def tearDown(self) -> None:
        self.path_patcher.stop()
        self.result_patcher.stop()
        self.preview_patcher.stop()
        self.processed_patcher.stop()
        self.led_patcher.stop()

    def test_home_result_and_error_screens_refresh_when_gpio_listener_is_active(self) -> None:
        client = app_module.app.test_client()
        app_module.GPIO_TRIGGER = object()

        cases = (
            (DeviceState.READY, {"detail": "Press button to select the mode."}, b"window.location.reload()"),
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
                    selected_mode_internal="document_reader",
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
            selected_mode_internal="document_reader",
            answer="Persistent answer",
            current_step=3,
        )

        response = client.post("/clear")

        self.assertEqual(response.status_code, 302)
        state = app_module._load_ui_state()
        self.assertEqual(state["device_state"], "READY")
        self.assertEqual(state["screen"], "home")
        self.assertEqual(state["selected_mode"], "")
        self.assertEqual(state["selected_mode_internal"], "")
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
            selected_mode_internal="math_solver",
            answer="Line one",
            current_step=3,
        )

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Line one", response.data)
        self.assertIn(b"Solve Problem", response.data)
        state = app_module._load_ui_state()
        self.assertEqual(state["device_state"], "DONE")
        self.assertEqual(state["screen"], "result")
        self.assertEqual(state["answer"], "Line one")
        self.assertEqual(state["selected_mode"], "solve_problem")
        self.assertEqual(state["selected_mode_internal"], "math_solver")

    def test_home_screen_shows_the_new_raspberry_pi_mode_buttons(self) -> None:
        client = app_module.app.test_client()

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Ready ...", response.data)
        self.assertIn(b"Read Text", response.data)
        self.assertIn(b"Summarize Document", response.data)
        self.assertIn(b"Analyze Image", response.data)
        self.assertIn(b"Professional Assistant", response.data)
        self.assertIn(b"Solve Problem", response.data)
        self.assertIn(b"Button Main", response.data)
        self.assertIn(b"Capture", response.data)
        self.assertIn(b"Press button to select the mode.", response.data)
        self.assertNotIn(b"Document Reader", response.data)

    def test_home_screen_uses_landscape_shell_dimensions(self) -> None:
        client = app_module.app.test_client()

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"orientation-landscape", response.data)
        self.assertIn(b"--screen-width: 480px;", response.data)
        self.assertIn(b"--screen-height: 320px;", response.data)
        self.assertIn(b'action="/mode/select"', response.data)
        self.assertIn(b'action="/analyze"', response.data)

    def test_legacy_mode_selection_is_saved_with_ui_and_internal_modes(self) -> None:
        client = app_module.app.test_client()

        response = client.post("/mode/select", data={"mode": "solve_problem"})

        self.assertEqual(response.status_code, 302)
        state = app_module._load_ui_state()
        self.assertEqual(state["device_state"], "MODE_SELECTED")
        self.assertEqual(state["selected_mode"], "solve_problem")
        self.assertEqual(state["selected_mode_internal"], "math_solver")

    def test_professional_assistant_maps_to_general_vision_pipeline(self) -> None:
        client = app_module.app.test_client()

        response = client.post("/mode/select", data={"mode": "professional_assistant"})

        self.assertEqual(response.status_code, 302)
        state = app_module._load_ui_state()
        self.assertEqual(state["selected_mode"], "professional_assistant")
        self.assertEqual(state["selected_mode_internal"], "general_vision")

    def test_capture_without_selected_mode_defaults_to_solve_problem(self) -> None:
        app_module._reset_ui_state(clear_saved_result=False, clear_selected_mode=True)

        with patch("app.threading.Thread", _FakeThread):
            started = app_module._start_capture_job()

        self.assertTrue(started)
        state = app_module._load_ui_state()
        self.assertEqual(state["device_state"], "CAPTURING")
        self.assertEqual(state["selected_mode"], "solve_problem")
        self.assertEqual(state["selected_mode_internal"], "math_solver")
        app_module.RUNNING = False

    def test_legacy_saved_mode_renders_with_new_label(self) -> None:
        client = app_module.app.test_client()
        self.ui_state_path.write_text(
            (
                "{\n"
                '  "screen": "home",\n'
                '  "device_state": "READY",\n'
                '  "selected_mode": "document_reader",\n'
                '  "status": "Ready",\n'
                '  "detail": "Press button to select the mode.",\n'
                '  "answer": "",\n'
                '  "error": "",\n'
                '  "error_detail": "",\n'
                '  "current_step": -1,\n'
                '  "updated_at": "2026-07-09T22:00:00"\n'
                "}\n"
            ),
            encoding="utf-8",
        )

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Read Text", response.data)
        state = app_module._load_ui_state()
        self.assertEqual(state["selected_mode"], "read_text")
        self.assertEqual(state["selected_mode_internal"], "document_reader")

    def test_humanize_error_maps_reliability_failures(self) -> None:
        cases = {
            "Picamera2 could not capture an image.": "Camera disconnected",
            "Could not connect to OpenAI after 3 attempts. Check your internet connection and try again.": "Network unavailable",
            "The OpenAI request timed out after 3 attempts. Please try again.": "OpenAI request timed out",
            "Invalid image file 'static/processed.jpg'. Please capture a new image and try again.": "Invalid image",
        }

        for raw_error, expected in cases.items():
            with self.subTest(raw_error=raw_error):
                self.assertEqual(app_module._humanize_error(raw_error), expected)

    def test_run_capture_job_failure_updates_error_screen(self) -> None:
        with patch("app.run_capture_analyze", side_effect=app_module.PipelineError("Invalid image file")):
            app_module._run_capture_job("read_text", "document_reader")

        state = app_module._load_ui_state()
        self.assertEqual(state["device_state"], "ERROR")
        self.assertEqual(state["screen"], "error")
        self.assertEqual(state["selected_mode"], "read_text")
        self.assertEqual(state["selected_mode_internal"], "document_reader")
        self.assertEqual(state["error"], "Invalid image")
        self.assertIn("Invalid image file", state["error_detail"])

    def test_preview_image_is_rendered_when_capture_file_exists(self) -> None:
        client = app_module.app.test_client()
        self.preview_path.write_bytes(b"fake image bytes")
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="analyze_image",
            selected_mode_internal="general_vision",
            answer="Preview test",
            current_step=3,
        )

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/static/captured.jpg?v=", response.data)

    def test_back_route_returns_to_ready_screen_without_selected_mode(self) -> None:
        client = app_module.app.test_client()
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="solve_problem",
            selected_mode_internal="math_solver",
            answer="Done",
            current_step=3,
        )

        response = client.post("/back")

        self.assertEqual(response.status_code, 302)
        state = app_module._load_ui_state()
        self.assertEqual(state["device_state"], "READY")
        self.assertEqual(state["selected_mode"], "")
        self.assertEqual(state["selected_mode_internal"], "")

    def test_bootstrap_ui_state_resets_result_screen_to_ready(self) -> None:
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="solve_problem",
            selected_mode_internal="math_solver",
            answer="Done",
            current_step=3,
        )

        app_module._bootstrap_ui_state()

        state = app_module._load_ui_state()
        self.assertEqual(state["device_state"], "READY")
        self.assertEqual(state["screen"], "home")
        self.assertEqual(state["selected_mode"], "")
        self.assertEqual(state["selected_mode_internal"], "")

    def test_health_monitor_can_be_started_from_app(self) -> None:
        fake_monitor = _FakeHealthMonitor()

        with patch.object(app_module.SETTINGS.reliability, "health_monitor_enabled", True), patch(
            "app.HealthMonitor",
            return_value=fake_monitor,
        ):
            app_module._ensure_health_monitor_started()

        self.assertIs(app_module.HEALTH_MONITOR, fake_monitor)
        self.assertTrue(fake_monitor.started)


class _FakeLEDIndicator:
    """No-op LED used to isolate app state tests from GPIO behavior."""

    def __init__(self) -> None:
        self.states: list[DeviceState | str] = []

    def set_state(self, device_state: DeviceState | str) -> None:
        self.states.append(device_state)


class _FakeHealthMonitor:
    """Small monitor double used to validate startup wiring."""

    def __init__(self) -> None:
        self.started = False

    def start(self) -> bool:
        self.started = True
        return True


class _FakeThread:
    """Minimal thread double used to validate job startup state without background work."""

    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    def start(self) -> None:
        return None
