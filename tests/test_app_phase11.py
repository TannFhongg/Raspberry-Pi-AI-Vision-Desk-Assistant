"""App-level tests for the Raspberry Pi hardware-first screen flow."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

os.environ.setdefault("ENABLE_GPIO_BUTTON", "0")
os.environ.setdefault("ENABLE_GPIO_LED", "0")
os.environ.setdefault("OFFLINE_RETRY_ENABLED", "0")
os.environ.setdefault("RELIABILITY_HEALTH_MONITOR_ENABLED", "0")

import app as app_module

from hardware.status import DeviceState


class Phase11AppIntegrationTests(unittest.TestCase):
    """Verify the shared app state behavior used by hardware-first control."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="phase11-app-test-"))
        self.ui_state_path = self.temp_dir / "ui_state.json"
        self.health_status_path = self.temp_dir / "health_status.json"
        self.latest_result_path = self.temp_dir / "latest_result.txt"
        self.result_history_path = self.temp_dir / "result_history.json"
        self.result_history_asset_dir = self.temp_dir / "history_assets"
        self.preview_path = self.temp_dir / "captured.jpg"
        self.processed_path = self.temp_dir / "processed.jpg"
        self.led_indicator = _FakeLEDIndicator()
        self.live_preview = _FakeLivePreview()
        self.offline_retry_queue = _FakeOfflineRetryQueue()
        self.path_patcher = patch.object(app_module, "UI_STATE_PATH", self.ui_state_path)
        self.health_path_patcher = patch.object(app_module, "HEALTH_STATUS_PATH", self.health_status_path)
        self.result_patcher = patch.object(app_module, "LATEST_RESULT_PATH", self.latest_result_path)
        self.history_patcher = patch.object(app_module, "RESULT_HISTORY_PATH", self.result_history_path)
        self.history_asset_patcher = patch.object(
            app_module,
            "RESULT_HISTORY_ASSET_DIR",
            self.result_history_asset_dir,
        )
        self.preview_patcher = patch.object(app_module, "CAPTURED_IMAGE_PATH", self.preview_path)
        self.processed_patcher = patch.object(app_module, "PROCESSED_IMAGE_PATH", self.processed_path)
        self.led_patcher = patch.object(app_module, "LED_INDICATOR", self.led_indicator)
        self.live_preview_patcher = patch.object(app_module, "LIVE_PREVIEW", self.live_preview)
        self.thumbnail_cache_patcher = patch.object(app_module, "RESULT_HISTORY_THUMBNAIL_CACHE", {})
        self.offline_retry_patcher = patch.object(
            app_module,
            "OFFLINE_RETRY_QUEUE",
            self.offline_retry_queue,
        )
        self.path_patcher.start()
        self.health_path_patcher.start()
        self.result_patcher.start()
        self.history_patcher.start()
        self.history_asset_patcher.start()
        self.preview_patcher.start()
        self.processed_patcher.start()
        self.led_patcher.start()
        self.live_preview_patcher.start()
        self.thumbnail_cache_patcher.start()
        self.offline_retry_patcher.start()
        app_module.app.config["TESTING"] = True
        app_module.RUNNING = False
        app_module.GPIO_TRIGGER = None
        app_module.HEALTH_MONITOR = None
        app_module.RESULT_HISTORY_CACHE = None
        app_module._reset_ui_state(clear_saved_result=False)

    def tearDown(self) -> None:
        self.path_patcher.stop()
        self.health_path_patcher.stop()
        self.result_patcher.stop()
        self.history_patcher.stop()
        self.history_asset_patcher.stop()
        self.preview_patcher.stop()
        self.processed_patcher.stop()
        self.led_patcher.stop()
        self.live_preview_patcher.stop()
        self.thumbnail_cache_patcher.stop()
        self.offline_retry_patcher.stop()

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

    def test_back_route_returns_to_mode_selection_without_clearing_saved_result(self) -> None:
        client = app_module.app.test_client()
        self.latest_result_path.write_text("Old result\n", encoding="utf-8")
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="read_text",
            selected_mode_internal="document_reader",
            answer="Persistent answer",
            current_step=3,
        )

        response = client.post("/back")

        self.assertEqual(response.status_code, 302)
        state = app_module._load_ui_state()
        self.assertEqual(state["device_state"], "READY")
        self.assertEqual(state["screen"], "home")
        self.assertEqual(state["selected_mode"], "")
        self.assertEqual(state["selected_mode_internal"], "")
        self.assertEqual(self.latest_result_path.read_text(encoding="utf-8"), "Old result\n")

    def test_back_request_is_ignored_while_capture_job_is_running(self) -> None:
        app_module._set_selected_mode("solve_problem")
        app_module.RUNNING = True

        changed = app_module._return_to_mode_selection()

        self.assertFalse(changed)
        state = app_module._load_ui_state()
        self.assertEqual(state["device_state"], "MODE_SELECTED")
        self.assertEqual(state["selected_mode"], "solve_problem")
        self.assertEqual(state["selected_mode_internal"], "math_solver")

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
        self.assertNotIn(b"Answer:", response.data)
        self.assertNotIn(b"Button 5", response.data)
        state = app_module._load_ui_state()
        self.assertEqual(state["device_state"], "DONE")
        self.assertEqual(state["screen"], "result")
        self.assertEqual(state["answer"], "Line one")
        self.assertEqual(state["selected_mode"], "solve_problem")
        self.assertEqual(state["selected_mode_internal"], "math_solver")

    def test_back_route_clears_result_history_anchor_for_gpio_exit(self) -> None:
        client = app_module.app.test_client()
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="solve_problem",
            selected_mode_internal="math_solver",
            history_entry_id="entry-1",
            answer="Done",
            current_step=3,
        )

        response = client.post("/back")

        self.assertEqual(response.status_code, 302)
        state = app_module._load_ui_state()
        self.assertEqual(state["history_entry_id"], "")

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
        self.assertIn(b"Capture", response.data)
        self.assertIn(b"Press button to select the mode.", response.data)
        self.assertNotIn(b"Button 1", response.data)
        self.assertNotIn(b"Button 5", response.data)
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
        self.assertEqual(self.live_preview.pause_calls, 1)
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

        self.assertEqual(self.live_preview.resume_calls, 1)
        state = app_module._load_ui_state()
        self.assertEqual(state["device_state"], "ERROR")
        self.assertEqual(state["screen"], "error")
        self.assertEqual(state["selected_mode"], "read_text")
        self.assertEqual(state["selected_mode_internal"], "document_reader")
        self.assertEqual(state["error"], "Invalid image")
        self.assertIn("Invalid image file", state["error_detail"])

    def test_retryable_openai_failure_is_saved_to_offline_queue(self) -> None:
        self.preview_path.write_bytes(b"captured")
        self.processed_path.write_bytes(b"processed")
        retryable_error = app_module.PipelineError(
            "Could not connect to OpenAI after 3 attempts. Check your internet connection and try again.",
            retryable=True,
            captured_path=self.preview_path,
            processed_path=self.processed_path,
            mode="document_reader",
            camera_backend_used="picamera2",
            camera_resolution=(1920, 1080),
        )

        with patch("app.run_capture_analyze", side_effect=retryable_error):
            app_module._run_capture_job("read_text", "document_reader")

        self.assertEqual(self.live_preview.resume_calls, 1)
        self.assertEqual(len(self.offline_retry_queue.entries), 1)
        state = app_module._load_ui_state()
        self.assertEqual(state["device_state"], "DONE")
        self.assertEqual(state["screen"], "result")
        self.assertEqual(state["status"], "Queued for retry")
        self.assertIn("Saved for automatic retry.", state["answer"])
        latest_result = self.latest_result_path.read_text(encoding="utf-8")
        self.assertIn("Status: queued", latest_result)
        self.assertIn("Message: Saved for automatic retry.", latest_result)
        self.assertEqual(app_module._load_result_history(), [])

    def test_live_preview_image_is_rendered_from_the_live_route(self) -> None:
        client = app_module.app.test_client()
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="analyze_image",
            selected_mode_internal="general_vision",
            answer="Preview test",
            current_step=3,
        )

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Live Camera Feed", response.data)
        self.assertIn(b"/camera/live-stream.mjpg", response.data)
        self.assertNotIn(b"data-live-preview-url", response.data)
        self.assertNotIn(b"&frame=", response.data)

    def test_live_preview_route_returns_current_frame_bytes(self) -> None:
        client = app_module.app.test_client()

        response = client.get("/camera/live-frame.jpg")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/jpeg")
        self.assertEqual(response.data, self.live_preview.frame_bytes)

    def test_live_preview_stream_route_returns_mjpeg_chunk(self) -> None:
        client = app_module.app.test_client()

        response = client.get("/camera/live-stream.mjpg")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "multipart/x-mixed-replace")
        self.assertIn("boundary=frame", response.content_type)
        first_chunk = b"".join(response.response)
        self.assertIn(b"--frame", first_chunk)
        self.assertIn(b"Content-Type: image/jpeg", first_chunk)
        self.assertIn(self.live_preview.frame_bytes, first_chunk)

    def test_ui_state_api_returns_public_state_json(self) -> None:
        client = app_module.app.test_client()
        app_module._write_device_state(
            DeviceState.PROCESSING,
            selected_mode="read_text",
            selected_mode_internal="document_reader",
            detail="Processing...",
            current_step=1,
        )

        response = client.get("/api/ui-state")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        assert payload is not None
        self.assertEqual(payload["screen"], "processing")
        self.assertEqual(payload["selected_mode"], "read_text")
        self.assertEqual(payload["selected_mode_label"], "Read Text")
        self.assertEqual(payload["display_status"], "Processing...")
        self.assertEqual(payload["current_step"], 1)
        self.assertEqual(payload["progress_steps"][1]["state"], "active")

    def test_health_api_prefers_latest_monitor_snapshot(self) -> None:
        client = app_module.app.test_client()
        app_module.HEALTH_MONITOR = _FakeHealthMonitor(
            latest_snapshot={
                "overall_status": "healthy",
                "updated_at": "2026-07-10T21:35:09",
                "cpu": {"status": "pass", "temperature_c": 46.3, "message": "CPU temperature is 46.3 C."},
                "memory": {"status": "pass", "used_percent": 12.5, "message": "Memory usage is 12.5%."},
                "network": {"status": "pass", "message": "Internet connection check succeeded."},
                "camera": {"status": "pass", "message": "Camera capture succeeded.", "last_probe_at": "2026-07-10T21:35:09"},
            }
        )

        response = client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        assert payload is not None
        self.assertEqual(payload["overall"]["label"], "System OK")
        self.assertEqual(payload["cpu"]["label"], "CPU 46.3C")
        self.assertEqual(payload["memory"]["label"], "RAM 12.5%")
        self.assertEqual(payload["network"]["label"], "NET OK")
        self.assertEqual(payload["camera"]["label"], "CAM OK")

    def test_successful_capture_is_added_to_recent_results_history(self) -> None:
        result = app_module.PipelineResult(
            captured_path=self.preview_path,
            processed_path=self.processed_path,
            answer="First line\nSecond line",
            mode="document_reader",
            camera_backend_used="picamera2",
            camera_resolution=(1920, 1080),
            status="success",
        )

        with patch("app.run_capture_analyze", return_value=result):
            app_module._run_capture_job("read_text", "document_reader")

        history_entries = app_module._load_result_history()
        self.assertEqual(len(history_entries), 1)
        self.assertEqual(history_entries[0]["mode_label"], "Read Text")
        self.assertEqual(history_entries[0]["camera_resolution"], [1920, 1080])
        self.assertIn("First line", history_entries[0]["summary"])

    def test_history_screen_renders_saved_entries(self) -> None:
        client = app_module.app.test_client()
        app_module._write_result_history(
            [
                {
                    "id": "entry-1",
                    "created_at": "2026-07-10T22:00:00",
                    "selected_mode": "read_text",
                    "selected_mode_internal": "document_reader",
                    "mode_label": "Read Text",
                    "answer": "Saved answer body",
                    "summary": "Saved answer summary",
                    "camera_backend_used": "picamera2",
                    "camera_resolution": [1920, 1080],
                }
            ]
        )

        response = client.get("/history")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Recent Results", response.data)
        self.assertIn(b"Saved answer summary", response.data)
        self.assertIn(b"/history/entry-1", response.data)

    def test_history_screen_renders_thumbnail_gallery_when_assets_exist(self) -> None:
        client = app_module.app.test_client()
        source_image_path = self.temp_dir / "history-source.jpg"
        processed_image_path = self.temp_dir / "history-processed.jpg"
        _create_valid_image_file(source_image_path)
        _create_valid_image_file(processed_image_path)
        app_module._write_result_history(
            [
                {
                    "id": "entry-1",
                    "created_at": "2026-07-10T22:00:00",
                    "selected_mode": "read_text",
                    "selected_mode_internal": "document_reader",
                    "mode_label": "Read Text",
                    "answer": "Saved answer body",
                    "summary": "Saved answer summary",
                    "camera_backend_used": "picamera2",
                    "camera_resolution": [1920, 1080],
                    "source_image_path": str(source_image_path),
                    "processed_image_path": str(processed_image_path),
                }
            ]
        )

        response = client.get("/history")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"history-card-thumb-image", response.data)
        self.assertIn(b"data:image/jpeg;base64,", response.data)

    def test_history_detail_screen_renders_saved_answer(self) -> None:
        client = app_module.app.test_client()
        app_module._write_result_history(
            [
                {
                    "id": "entry-1",
                    "created_at": "2026-07-10T22:00:00",
                    "selected_mode": "solve_problem",
                    "selected_mode_internal": "math_solver",
                    "mode_label": "Solve Problem",
                    "answer": "Saved answer body",
                    "summary": "Saved answer summary",
                    "camera_backend_used": "opencv",
                    "camera_resolution": [1280, 720],
                }
            ]
        )

        response = client.get("/history/entry-1")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Solve Problem", response.data)
        self.assertIn(b"Saved answer body", response.data)
        self.assertIn(b"1280x720", response.data)

    def test_result_screen_offers_instant_reanalyze_buttons(self) -> None:
        client = app_module.app.test_client()
        _create_valid_image_file(self.preview_path)
        _create_valid_image_file(self.processed_path)
        result = app_module.PipelineResult(
            captured_path=self.preview_path,
            processed_path=self.processed_path,
            answer="Solved",
            mode="math_solver",
            camera_backend_used="opencv",
            camera_resolution=(640, 480),
            status="success",
        )

        with patch("app.run_capture_analyze", return_value=result):
            app_module._run_capture_job("solve_problem", "math_solver")

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Analyze Same Image As", response.data)
        self.assertIn(b'action="/reanalyze"', response.data)
        self.assertIn(b"Read Text", response.data)

    def test_result_screen_shows_gpio_reanalyze_hint_when_listener_is_active(self) -> None:
        client = app_module.app.test_client()
        _create_valid_image_file(self.preview_path)
        _create_valid_image_file(self.processed_path)
        result = app_module.PipelineResult(
            captured_path=self.preview_path,
            processed_path=self.processed_path,
            answer="Solved",
            mode="math_solver",
            camera_backend_used="opencv",
            camera_resolution=(640, 480),
            status="success",
        )

        with patch("app.run_capture_analyze", return_value=result):
            app_module._run_capture_job("solve_problem", "math_solver")

        app_module.GPIO_TRIGGER = object()

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"GPIO: press a mode button to re-analyze this same image", response.data)

    def test_reanalyze_job_reuses_saved_image_without_new_capture(self) -> None:
        source_image_path = self.temp_dir / "history-source.jpg"
        processed_image_path = self.temp_dir / "history-processed.jpg"
        _create_valid_image_file(source_image_path)
        _create_valid_image_file(processed_image_path)
        app_module._write_result_history(
            [
                {
                    "id": "entry-1",
                    "created_at": "2026-07-10T22:00:00",
                    "selected_mode": "read_text",
                    "selected_mode_internal": "document_reader",
                    "mode_label": "Read Text",
                    "answer": "Saved answer body",
                    "summary": "Saved answer summary",
                    "camera_backend_used": "picamera2",
                    "camera_resolution": [1920, 1080],
                    "source_image_path": str(source_image_path),
                    "processed_image_path": str(processed_image_path),
                }
            ]
        )
        analyze_result = app_module.PipelineResult(
            captured_path=source_image_path,
            processed_path=processed_image_path,
            answer="Reanalyzed answer",
            mode="math_solver",
            camera_backend_used=None,
            camera_resolution=None,
            status="success",
        )

        with patch("app.run_analyze", return_value=analyze_result) as run_analyze_mock:
            app_module._run_reanalyze_job("entry-1", "solve_problem", "math_solver")

        self.assertEqual(self.live_preview.pause_calls, 0)
        self.assertEqual(self.live_preview.resume_calls, 0)
        run_analyze_mock.assert_called_once()
        self.assertEqual(run_analyze_mock.call_args.kwargs["captured_path"], str(source_image_path))
        self.assertEqual(run_analyze_mock.call_args.kwargs["processed_path"], str(processed_image_path))
        state = app_module._load_ui_state()
        self.assertEqual(state["device_state"], "DONE")
        self.assertEqual(state["answer"], "Reanalyzed answer")
        history_entries = app_module._load_result_history()
        self.assertEqual(len(history_entries), 2)
        self.assertEqual(history_entries[0]["selected_mode_internal"], "math_solver")

    def test_physical_mode_button_reanalyzes_current_result_image(self) -> None:
        source_image_path = self.temp_dir / "history-source.jpg"
        processed_image_path = self.temp_dir / "history-processed.jpg"
        _create_valid_image_file(source_image_path)
        _create_valid_image_file(processed_image_path)
        app_module._write_result_history(
            [
                {
                    "id": "entry-1",
                    "created_at": "2026-07-10T22:00:00",
                    "selected_mode": "solve_problem",
                    "selected_mode_internal": "math_solver",
                    "mode_label": "Solve Problem",
                    "answer": "Saved answer body",
                    "summary": "Saved answer summary",
                    "camera_backend_used": "opencv",
                    "camera_resolution": [1280, 720],
                    "source_image_path": str(source_image_path),
                    "processed_image_path": str(processed_image_path),
                }
            ]
        )
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="solve_problem",
            selected_mode_internal="math_solver",
            history_entry_id="entry-1",
            answer="Saved answer body",
            current_step=3,
        )

        with patch("app._start_reanalyze_job", return_value=True) as reanalyze_mock:
            changed = app_module._select_mode_from_hardware("read_text")

        self.assertTrue(changed)
        reanalyze_mock.assert_called_once_with("entry-1", "read_text")

    def test_run_capture_job_success_resumes_live_preview(self) -> None:
        result = app_module.PipelineResult(
            captured_path=self.preview_path,
            processed_path=self.processed_path,
            answer="Solved",
            mode="math_solver",
            camera_backend_used="opencv",
            camera_resolution=(640, 480),
            status="success",
        )

        with patch("app.run_capture_analyze", return_value=result):
            app_module._run_capture_job("solve_problem", "math_solver")

        self.assertEqual(self.live_preview.resume_calls, 1)
        state = app_module._load_ui_state()
        self.assertEqual(state["device_state"], "DONE")
        self.assertEqual(state["answer"], "Solved")

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

    def __init__(self, latest_snapshot=None) -> None:
        self.started = False
        self.latest_snapshot = latest_snapshot

    def start(self) -> bool:
        self.started = True
        return True


class _FakeLivePreview:
    """Small live-preview double used by the Flask screen tests."""

    def __init__(self) -> None:
        self.pause_calls = 0
        self.resume_calls = 0
        self.frame_bytes = b"fake-live-jpeg"

    def get_jpeg_frame(self, timeout_seconds: float = 1.0) -> bytes:
        del timeout_seconds
        return self.frame_bytes

    def iter_mjpeg_stream(self, boundary: str = "frame", timeout_seconds: float = 1.0):
        del timeout_seconds
        yield (
            b"--"
            + boundary.encode("ascii")
            + b"\r\n"
            + b"Content-Type: image/jpeg\r\n"
            + b"Content-Length: "
            + str(len(self.frame_bytes)).encode("ascii")
            + b"\r\n\r\n"
            + self.frame_bytes
            + b"\r\n"
        )

    def pause(self) -> None:
        self.pause_calls += 1

    def resume(self) -> None:
        self.resume_calls += 1


class _FakeOfflineRetryQueue:
    """Small queue double that records queued retry entries without background work."""

    def __init__(self) -> None:
        self.entries: list[object] = []

    def enqueue(self, **kwargs):
        entry = type("QueuedEntry", (), {})()
        entry.id = f"queued-{len(self.entries) + 1}"
        entry.selected_mode = kwargs["selected_mode"]
        entry.selected_mode_internal = kwargs["selected_mode_internal"]
        entry.captured_path = str(kwargs.get("captured_path") or "")
        entry.processed_path = str(kwargs["processed_path"])
        entry.camera_backend_used = kwargs.get("camera_backend_used") or ""
        entry.camera_resolution = kwargs.get("camera_resolution")
        self.entries.append(entry)
        return entry

    def pending_count(self) -> int:
        return len(self.entries)


class _FakeThread:
    """Minimal thread double used to validate job startup state without background work."""

    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    def start(self) -> None:
        return None


def _create_valid_image_file(path: Path) -> None:
    """Create a small valid JPEG image for thumbnail and history tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with Image.new("RGB", (48, 36), color=(210, 210, 210)) as image:
        image.save(path)
