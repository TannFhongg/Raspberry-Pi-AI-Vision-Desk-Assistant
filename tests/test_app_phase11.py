"""App-level tests for the privacy-first kiosk flow."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ENABLE_GPIO_BUTTON", "0")
os.environ.setdefault("ENABLE_GPIO_LED", "0")
os.environ.setdefault("OFFLINE_RETRY_ENABLED", "0")
os.environ.setdefault("RELIABILITY_HEALTH_MONITOR_ENABLED", "0")

import app as app_module

from hardware.status import DeviceState
from pipeline.runner import PipelineError, PipelineResult
from system.offline_retry import OfflineRetryQueue


class PrivacyFirstAppTests(unittest.TestCase):
    """Verify the commercial-hardening runtime behavior in Flask."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="privacy-app-test-"))
        self.private_dir = self.temp_dir / "private"
        self.current_dir = self.private_dir / "current"
        self.retry_dir = self.private_dir / "retry"
        self.quarantine_dir = self.private_dir / "quarantine"
        self.ui_state_path = self.temp_dir / "ui_state.json"
        self.health_status_path = self.temp_dir / "health_status.json"
        self.latest_result_path = self.temp_dir / "latest_result.txt"
        self.result_history_path = self.temp_dir / "result_history.json"
        self.preview_dir = self.temp_dir / "ui-previews"
        self.latest_result_preview_path = self.preview_dir / "latest-result.jpg"
        self.retry_queue_path = self.private_dir / "retry_queue.json"
        self.captured_path = self.current_dir / "captured.jpg"
        self.processed_path = self.current_dir / "processed.jpg"

        self.live_preview = _FakeLivePreview()
        self.led_indicator = _FakeLEDIndicator()
        self.queue = OfflineRetryQueue(
            queue_path=self.retry_queue_path,
            storage_dir=self.retry_dir,
            poll_interval_seconds=1.0,
            max_entries=10,
            max_attempts=3,
            initial_delay_seconds=1.0,
            max_delay_seconds=60.0,
            retention_hours=24.0,
            min_free_bytes=1,
            max_storage_bytes=10 * 1024 * 1024,
            quarantine_dir=self.quarantine_dir,
        )

        self.patchers = [
            patch.object(app_module, "UI_STATE_PATH", self.ui_state_path),
            patch.object(app_module, "HEALTH_STATUS_PATH", self.health_status_path),
            patch.object(app_module, "LATEST_RESULT_PATH", self.latest_result_path),
            patch.object(app_module, "RESULT_HISTORY_PATH", self.result_history_path),
            patch.object(app_module, "UI_PREVIEW_DIR", self.preview_dir),
            patch.object(app_module, "LATEST_RESULT_PREVIEW_PATH", self.latest_result_preview_path),
            patch.object(app_module, "PRIVATE_DATA_PATH", self.private_dir),
            patch.object(app_module, "PRIVATE_CURRENT_PATH", self.current_dir),
            patch.object(app_module, "PRIVATE_RETRY_PATH", self.retry_dir),
            patch.object(app_module, "PRIVATE_QUARANTINE_PATH", self.quarantine_dir),
            patch.object(app_module, "CAPTURED_IMAGE_PATH", self.captured_path),
            patch.object(app_module, "PROCESSED_IMAGE_PATH", self.processed_path),
            patch.object(app_module, "OFFLINE_RETRY_QUEUE_PATH", self.retry_queue_path),
            patch.object(app_module, "OFFLINE_RETRY_STORAGE_PATH", self.retry_dir),
            patch.object(app_module, "LIVE_PREVIEW", self.live_preview),
            patch.object(app_module, "LED_INDICATOR", self.led_indicator),
            patch.object(app_module, "OFFLINE_RETRY_QUEUE", self.queue),
            patch.object(app_module, "PROCESSING_TRANSITION_SECONDS", 0.0),
        ]
        for patcher in self.patchers:
            patcher.start()

        app_module.app.config["TESTING"] = True
        app_module.RUNNING = False
        app_module.GPIO_TRIGGER = None
        app_module.HEALTH_MONITOR = None
        app_module.RESULT_HISTORY_CACHE = None
        self.current_dir.mkdir(parents=True, exist_ok=True)
        self.retry_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        app_module._reset_ui_state(clear_saved_result=False)

    def tearDown(self) -> None:
        self.queue.close()
        for patcher in reversed(self.patchers):
            patcher.stop()

    def test_ui_state_api_returns_public_state_json(self) -> None:
        client = app_module.app.test_client()
        app_module._write_device_state(
            DeviceState.PROCESSING,
            selected_mode="read_text",
            selected_mode_internal="document_reader",
            detail="Preprocessing image...",
            current_step=1,
            progress_state="PREPROCESSING",
        )

        response = client.get("/api/ui-state")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        assert payload is not None
        self.assertEqual(payload["screen"], "processing")
        self.assertEqual(payload["selected_mode"], "read_text")
        self.assertEqual(payload["selected_mode_label"], "Read Text")
        self.assertEqual(payload["progress_state"], "PREPROCESSING")
        self.assertEqual(payload["processing_title"], "Reading Text")
        self.assertEqual(payload["progress_steps"][0]["state"], "complete")
        self.assertEqual(payload["progress_steps"][1]["state"], "active")

    def test_ui_state_api_reports_camera_screen_when_mode_selected(self) -> None:
        client = app_module.app.test_client()
        app_module._set_selected_mode("read_text")

        response = client.get("/api/ui-state")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        assert payload is not None
        self.assertEqual(payload["screen"], "camera")
        self.assertEqual(payload["selected_mode"], "read_text")

    def test_index_renders_camera_screen_for_selected_mode(self) -> None:
        client = app_module.app.test_client()
        app_module._set_selected_mode("professional_assistant")

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"CURRENT MODE", response.data)
        self.assertIn(b"PROFESSIONAL ASSISTANT", response.data)
        self.assertIn(b"CAMERA ANALYSIS", response.data)

    def test_camera_route_renders_camera_screen(self) -> None:
        client = app_module.app.test_client()
        app_module._set_selected_mode("read_text")

        response = client.get("/camera")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"CAPTURE", response.data)
        self.assertIn(b"BACK", response.data)
        self.assertIn(b"/camera/live-stream.mjpg", response.data)

    def test_processing_route_renders_mode_specific_processing_screen(self) -> None:
        client = app_module.app.test_client()
        app_module._write_device_state(
            DeviceState.PROCESSING,
            selected_mode="summarize_document",
            selected_mode_internal="document_reader",
            detail="Preprocessing image...",
            current_step=1,
            progress_state="PREPROCESSING",
        )

        response = client.get("/processing")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Summarizing Document", response.data)
        self.assertIn(b"Analyzing structure and text", response.data)
        self.assertIn(b"CURRENT MODE", response.data)
        self.assertIn(b"SUMMARIZE DOCUMENT", response.data)
        self.assertIn(b"Image captured", response.data)
        self.assertIn(b"Processing", response.data)
        self.assertIn(b"Result", response.data)
        self.assertIn(b"LIVE STATUS", response.data)

    def test_ui_state_api_exposes_retry_queued_progress_mapping(self) -> None:
        client = app_module.app.test_client()
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="read_text",
            selected_mode_internal="document_reader",
            detail="Saved for retry",
            answer="Saved for automatic retry.",
            current_step=1,
            status="Queued for retry",
            progress_state="RETRY_QUEUED",
            progress_error_step=1,
        )

        response = client.get("/api/ui-state")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        assert payload is not None
        self.assertEqual(payload["progress_state"], "RETRY_QUEUED")
        self.assertEqual(payload["processing_status_message"], "Saved for retry")
        self.assertEqual(payload["progress_steps"][1]["state"], "error")

    def test_result_route_renders_result_screen(self) -> None:
        client = app_module.app.test_client()
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="summarize_document",
            selected_mode_internal="document_reader",
            answer="Point one\nPoint two",
            status="Answer Ready",
        )

        response = client.get("/result")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Captured", response.data)
        self.assertIn(b"SUMMARIZE DOCUMENT", response.data)
        self.assertIn(b"Key Takeaways", response.data)
        self.assertIn(b"BACK", response.data)
        self.assertNotIn(b"Capture Again", response.data)

    def test_result_route_renders_current_mode_pill(self) -> None:
        client = app_module.app.test_client()
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="professional_assistant",
            selected_mode_internal="general_vision",
            answer="Recommendations here",
            status="Answer Ready",
        )

        response = client.get("/result")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"PROFESSIONAL ASSISTANT", response.data)

    def test_result_route_renders_image_preview_from_private_route(self) -> None:
        client = app_module.app.test_client()
        self.processed_path.write_bytes(b"processed-preview")
        app_module._sync_latest_result_preview(self.processed_path)
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="analyze_image",
            selected_mode_internal="general_vision",
            answer="Image analysis ready",
            status="Answer Ready",
        )

        response = client.get("/result")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/result-preview/latest.jpg", response.data)
        self.assertIn(b"Captured image", response.data)

    def test_result_route_formats_ai_answer_markup(self) -> None:
        client = app_module.app.test_client()
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="solve_problem",
            selected_mode_internal="math_solver",
            answer="# Summary\n**Important**\n1. First step\n2. Second step\n- Extra note",
            status="Answer Ready",
        )

        response = client.get("/result")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<h3>Summary</h3>", response.data)
        self.assertIn(b"<strong>Important</strong>", response.data)
        self.assertIn(b"<ol>", response.data)
        self.assertIn(b"<ul>", response.data)

    def test_result_screen_uses_independent_scroll_container_for_long_answers(self) -> None:
        client = app_module.app.test_client()
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="read_text",
            selected_mode_internal="document_reader",
            answer=("Long answer line\n" * 60).strip(),
            status="Answer Ready",
        )

        response = client.get("/result")
        css = Path("static/style.css").read_text(encoding="utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"result-answer-scroll", response.data)
        self.assertIn(".result-answer-scroll", css)
        self.assertIn("overflow-y: auto;", css)

    def test_result_route_shows_empty_answer_state(self) -> None:
        client = app_module.app.test_client()
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="read_text",
            selected_mode_internal="document_reader",
            answer="",
            status="Answer Ready",
        )

        response = client.get("/result")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No answer received", response.data)
        self.assertIn(b"No answer was received for this capture.", response.data)

    def test_result_route_shows_error_state(self) -> None:
        client = app_module.app.test_client()
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="analyze_image",
            selected_mode_internal="general_vision",
            answer="The assistant saved this capture for a retry.",
            status="Queued for retry",
        )

        response = client.get("/result")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Retry queued", response.data)
        self.assertIn(b"Waiting for retry.", response.data)

    def test_live_preview_routes_keep_no_store_cache_headers(self) -> None:
        client = app_module.app.test_client()

        frame_response = client.get("/camera/live-frame.jpg")
        stream_response = client.get("/camera/live-stream.mjpg")

        self.assertEqual(frame_response.status_code, 200)
        self.assertEqual(frame_response.headers["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")
        self.assertEqual(stream_response.status_code, 200)
        self.assertIn("boundary=frame", stream_response.content_type)
        self.assertEqual(stream_response.headers["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")

    def test_live_frame_route_uses_live_preview_service(self) -> None:
        client = app_module.app.test_client()

        self.live_preview.frame_bytes = b"linux-frame"
        response = client.get("/camera/live-frame.jpg")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"linux-frame")

    def test_result_preview_route_returns_latest_preview_with_no_store_headers(self) -> None:
        client = app_module.app.test_client()
        self.processed_path.write_bytes(b"processed-preview")
        app_module._sync_latest_result_preview(self.processed_path)

        response = client.get("/result-preview/latest.jpg")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"processed-preview")
        self.assertEqual(response.headers["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")

    def test_template_context_prefers_live_stream_without_polling(self) -> None:
        with app_module.app.test_request_context("/"):
            context = app_module._build_template_context()

        self.assertIn("/camera/live-stream.mjpg", context["live_preview_url"])
        self.assertIn("/camera/live-stream.mjpg", context["live_preview_base_url"])
        self.assertEqual(context["live_preview_refresh_ms"], 0)
        self.assertIn("camera_analysis", context)
        self.assertIn("camera_preview", context)

    def test_health_summary_marks_camera_ok_when_preview_has_recent_frame(self) -> None:
        self.live_preview.recent_frame = True
        self.health_status_path.write_text(
            json.dumps(
                {
                    "updated_at": "2026-07-11T10:10:00",
                    "overall_status": "unknown",
                    "cpu": {
                        "status": "pass",
                        "temperature_c": 50.7,
                        "message": "CPU temperature is 50.7 C.",
                    },
                    "memory": {
                        "status": "pass",
                        "used_percent": 11.5,
                        "message": "Memory usage is 11.5%.",
                    },
                    "network": {
                        "status": "pass",
                        "message": "Internet connection check succeeded.",
                    },
                    "camera": {
                        "status": "unknown",
                        "message": "Camera probe has not run yet.",
                    },
                }
            ),
            encoding="utf-8",
        )

        summary = app_module._build_health_summary()

        self.assertEqual(summary["camera"]["status"], "pass")
        self.assertEqual(summary["camera"]["label"], "CAM OK")
        self.assertEqual(summary["overall"]["status"], "pass")
        self.assertEqual(summary["overall"]["label"], "System OK")

    def test_health_summary_uses_warning_state_for_high_cpu_or_memory(self) -> None:
        self.health_status_path.write_text(
            json.dumps(
                {
                    "updated_at": "2026-07-11T10:10:00",
                    "overall_status": "unknown",
                    "cpu": {
                        "status": "pass",
                        "temperature_c": 73.4,
                        "message": "CPU temperature is 73.4 C.",
                    },
                    "memory": {
                        "status": "pass",
                        "used_percent": 82.1,
                        "message": "Memory usage is 82.1%.",
                    },
                    "network": {
                        "status": "pass",
                        "message": "Internet connection check succeeded.",
                    },
                    "camera": {
                        "status": "pass",
                        "message": "Camera probe succeeded.",
                    },
                }
            ),
            encoding="utf-8",
        )

        summary = app_module._build_health_summary()

        self.assertEqual(summary["cpu"]["status"], "warning")
        self.assertEqual(summary["memory"]["status"], "warning")
        self.assertEqual(summary["overall"]["status"], "warning")
        self.assertEqual(summary["overall"]["label"], "System Watch")

    def test_successful_capture_cleans_private_working_media_and_persists_text_history(self) -> None:
        self.captured_path.write_bytes(b"captured")
        self.processed_path.write_bytes(b"processed")
        successful_result = PipelineResult(
            captured_path=self.captured_path,
            processed_path=self.processed_path,
            answer="First line\nSecond line",
            mode="document_reader",
            camera_backend_used="opencv",
            camera_resolution=(1920, 1080),
            status="success",
            model_used="gpt-5.4-mini",
            duration_seconds=1.234,
        )

        with patch("app.run_capture_analyze", return_value=successful_result):
            app_module._run_capture_job("read_text", "document_reader")

        self.assertEqual(self.live_preview.resume_calls, 1)
        self.assertFalse(self.captured_path.exists())
        self.assertFalse(self.processed_path.exists())
        self.assertTrue(self.latest_result_preview_path.is_file())
        state = app_module._load_ui_state()
        self.assertEqual(state["screen"], "result")
        self.assertEqual(state["progress_state"], "DONE")
        history_entries = app_module._load_result_history()
        self.assertEqual(len(history_entries), 1)
        self.assertEqual(history_entries[0]["model_used"], "gpt-5.4-mini")
        self.assertNotIn("source_image_path", history_entries[0])
        self.assertNotIn("processed_image_path", history_entries[0])

    def test_capture_job_uses_unique_private_working_paths(self) -> None:
        successful_result = PipelineResult(
            captured_path=None,
            processed_path=None,
            answer="Fresh answer",
            mode="document_reader",
            camera_backend_used="opencv",
            camera_resolution=(1920, 1080),
            status="success",
        )

        with patch("app.run_capture_analyze", return_value=successful_result) as run_capture_analyze:
            app_module._run_capture_job("read_text", "document_reader")

        called_kwargs = run_capture_analyze.call_args.kwargs
        captured_path = Path(called_kwargs["captured_path"])
        processed_path = Path(called_kwargs["processed_path"])
        self.assertEqual(captured_path.parent, self.current_dir)
        self.assertEqual(processed_path.parent, self.current_dir)
        self.assertTrue(captured_path.name.startswith("captured-"))
        self.assertTrue(processed_path.name.startswith("processed-"))
        self.assertNotEqual(captured_path.name, "captured.jpg")
        self.assertNotEqual(processed_path.name, "processed.jpg")

    def test_retryable_failure_queues_processed_media_and_cleans_working_files(self) -> None:
        self.captured_path.write_bytes(b"captured")
        self.processed_path.write_bytes(b"processed")
        retryable_error = PipelineError(
            "Could not connect to OpenAI after 3 attempts. Check your internet connection and try again.",
            retryable=True,
            captured_path=self.captured_path,
            processed_path=self.processed_path,
            mode="document_reader",
            camera_backend_used="opencv",
            camera_resolution=(1920, 1080),
        )

        with patch("app.run_capture_analyze", side_effect=retryable_error):
            app_module._run_capture_job("read_text", "document_reader")

        self.assertEqual(self.live_preview.resume_calls, 1)
        self.assertFalse(self.captured_path.exists())
        self.assertFalse(self.processed_path.exists())
        state = app_module._load_ui_state()
        self.assertEqual(state["status"], "Queued for retry")
        self.assertEqual(state["progress_state"], "RETRY_QUEUED")
        self.assertEqual(state["progress_error_step"], 1)
        self.assertEqual(self.queue.pending_count(), 1)
        entry = self.queue.list_entries()[0]
        self.assertTrue(self.queue.resolve_processed_path(entry).is_file())
        self.assertEqual(app_module._load_result_history(), [])

    def test_permanent_pipeline_failure_records_processing_error_metadata(self) -> None:
        failure = PipelineError("OpenAI request timed out after 30 seconds", retryable=False)

        def fail_during_analyze(*args, **kwargs):
            app_module._update_processing_state(
                "read_text",
                "document_reader",
                "Sending image to OpenAI Vision...",
            )
            raise failure

        with patch("app.run_capture_analyze", side_effect=fail_during_analyze):
            app_module._run_capture_job("read_text", "document_reader")

        state = app_module._load_ui_state()
        self.assertEqual(state["screen"], "error")
        self.assertEqual(state["progress_state"], "ERROR")
        self.assertEqual(state["progress_error_step"], 1)
        self.assertEqual(state["error"], "OpenAI request timed out")

    def test_delete_all_data_route_clears_history_queue_and_private_runtime_files(self) -> None:
        client = app_module.app.test_client()
        self.captured_path.write_bytes(b"captured")
        self.processed_path.write_bytes(b"processed")
        app_module._write_result_history(
            [
                {
                    "id": "entry-1",
                    "created_at": "2026-07-11T10:00:00",
                    "selected_mode": "read_text",
                    "selected_mode_internal": "document_reader",
                    "mode_label": "Read Text",
                    "status": "success",
                    "answer": "Saved answer",
                    "summary": "Saved answer",
                    "camera_backend_used": "opencv",
                    "camera_resolution": [1920, 1080],
                    "model_used": "gpt-5.4-mini",
                    "duration_seconds": 1.1,
                    "retry_status": "",
                    "error_summary": "",
                }
            ]
        )
        queued_entry = self.queue.enqueue(
            selected_mode="read_text",
            selected_mode_internal="document_reader",
            processed_path=self.processed_path,
            error_message="network down",
        )
        self.latest_result_preview_path.parent.mkdir(parents=True, exist_ok=True)
        self.latest_result_preview_path.write_bytes(b"preview")
        self.assertTrue(self.queue.resolve_processed_path(queued_entry).is_file())
        quarantine_file = self.quarantine_dir / "broken.json"
        quarantine_file.write_text("broken", encoding="utf-8")

        response = client.post(
            "/data/delete-all",
            data={"confirm": "delete-all", "confirm_stage": "final"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.queue.pending_count(), 0)
        self.assertFalse(self.result_history_path.exists())
        self.assertFalse(self.captured_path.exists())
        self.assertFalse(self.processed_path.exists())
        self.assertFalse(self.latest_result_preview_path.exists())
        self.assertFalse(self.quarantine_dir.exists())
        state = app_module._load_ui_state()
        self.assertIn("All local data deleted", state["detail"])

    def test_history_screen_renders_text_only_recent_results(self) -> None:
        client = app_module.app.test_client()
        app_module._write_result_history(
            [
                {
                    "id": "entry-1",
                    "created_at": "2026-07-11T10:00:00",
                    "selected_mode": "read_text",
                    "selected_mode_internal": "document_reader",
                    "mode_label": "Read Text",
                    "status": "success",
                    "answer": "Saved answer",
                    "summary": "Saved answer",
                    "camera_backend_used": "opencv",
                    "camera_resolution": [1920, 1080],
                    "model_used": "gpt-5.4-mini",
                    "duration_seconds": 1.1,
                    "retry_status": "",
                    "error_summary": "",
                }
            ]
        )

        response = client.get("/history")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Saved answer", response.data)
        self.assertNotIn(b"history-card-thumb-image", response.data)
        self.assertNotIn(b"Analyze Same Image As", response.data)

    def test_reanalyze_route_reports_text_only_policy_error(self) -> None:
        client = app_module.app.test_client()
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="read_text",
            selected_mode_internal="document_reader",
            answer="Ready",
            current_step=3,
        )

        response = client.post("/reanalyze", data={"entry_id": "entry-1", "mode": "solve_problem"})

        self.assertEqual(response.status_code, 302)
        state = app_module._load_ui_state()
        self.assertEqual(state["screen"], "error")
        self.assertIn("text-only retention", state["error_detail"])

    def test_capture_route_starts_background_job(self) -> None:
        client = app_module.app.test_client()
        app_module._set_selected_mode("read_text")

        with patch("app._start_capture_job", return_value=True) as start_capture_job:
            response = client.post("/capture")

        self.assertEqual(response.status_code, 302)
        start_capture_job.assert_called_once_with()
        self.assertTrue(response.location.endswith("/processing"))

    def test_back_route_returns_to_home_screen(self) -> None:
        client = app_module.app.test_client()
        app_module._set_selected_mode("read_text")

        response = client.post("/back")

        self.assertEqual(response.status_code, 302)
        state = app_module._load_ui_state()
        self.assertEqual(state["screen"], "home")
        self.assertEqual(state["selected_mode"], "")
        self.assertEqual(state["selected_mode_internal"], "")

    def test_back_route_returns_home_screen_from_result_state(self) -> None:
        client = app_module.app.test_client()
        app_module._write_device_state(
            DeviceState.DONE,
            selected_mode="read_text",
            selected_mode_internal="document_reader",
            answer="Answer ready",
            status="Answer Ready",
        )

        response = client.post("/back")

        self.assertEqual(response.status_code, 302)
        state = app_module._load_ui_state()
        self.assertEqual(state["screen"], "home")

    def test_back_route_is_ignored_while_processing(self) -> None:
        client = app_module.app.test_client()
        app_module._write_device_state(
            DeviceState.PROCESSING,
            selected_mode="read_text",
            selected_mode_internal="document_reader",
            detail="Sending to AI...",
            current_step=1,
            progress_state="ANALYZING",
        )

        response = client.post("/back")

        self.assertEqual(response.status_code, 302)
        state = app_module._load_ui_state()
        self.assertEqual(state["screen"], "processing")
        self.assertEqual(state["selected_mode"], "read_text")

    def test_capture_route_blocks_repeated_requests_while_processing(self) -> None:
        client = app_module.app.test_client()
        app_module._set_selected_mode("read_text")
        _DeferredThread.started_threads = []

        with patch("app.threading.Thread", _DeferredThread):
            first_response = client.post("/capture")
            second_response = client.post("/capture")

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        self.assertEqual(len(_DeferredThread.started_threads), 1)
        state = app_module._load_ui_state()
        self.assertEqual(state["device_state"], "CAPTURING")
        self.assertEqual(state["current_step"], 0)
        app_module.RUNNING = False

    def test_purge_runtime_artifacts_cleans_orphan_media_and_old_history(self) -> None:
        old_entry = {
            "id": "entry-old",
            "created_at": "2000-01-01T00:00:00",
            "selected_mode": "read_text",
            "selected_mode_internal": "document_reader",
            "mode_label": "Read Text",
            "status": "success",
            "answer": "Old answer",
            "summary": "Old answer",
            "camera_backend_used": "opencv",
            "camera_resolution": [1920, 1080],
            "model_used": "gpt-5.4-mini",
            "duration_seconds": 1.1,
            "retry_status": "",
            "error_summary": "",
        }
        self.result_history_path.write_text(json.dumps([old_entry]), encoding="utf-8")
        self.captured_path.write_bytes(b"captured")
        self.processed_path.write_bytes(b"processed")

        app_module.RESULT_HISTORY_CACHE = None
        app_module._purge_runtime_artifacts(delete_all=False)

        self.assertFalse(self.captured_path.exists())
        self.assertFalse(self.processed_path.exists())
        self.assertEqual(app_module._load_result_history(), [])

    def test_app_defaults_to_local_only_host(self) -> None:
        self.assertEqual(app_module.APP_HOST, "127.0.0.1")
        self.assertFalse(app_module.FLASK_DEBUG)

    def test_health_monitor_busy_treats_active_preview_as_busy(self) -> None:
        self.live_preview.active = True

        self.assertTrue(app_module._health_monitor_busy())


class _FakeLivePreview:
    """Small live-preview double used by the Flask screen tests."""

    def __init__(self) -> None:
        self.frame_bytes = b"jpeg-data"
        self.resume_calls = 0
        self.active = False
        self.recent_frame = False
        self.error_message = ""

    def get_jpeg_frame(self, timeout_seconds: float = 1.0) -> bytes:
        return self.frame_bytes

    def iter_mjpeg_stream(self, boundary: str = "frame", timeout_seconds: float = 1.0):
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + self.frame_bytes + b"\r\n"

    def pause(self, timeout_seconds: float = 2.0) -> bool:
        return True

    def resume(self) -> None:
        self.resume_calls += 1

    def is_camera_active(self) -> bool:
        return self.active

    def has_recent_frame(self, max_age_seconds: float = 10.0) -> bool:
        return self.recent_frame

    def latest_error_message(self) -> str:
        return self.error_message


class _FakeLEDIndicator:
    """Small LED double for app tests that only records the latest state."""

    disabled_reason = ""

    def __init__(self) -> None:
        self.states: list[str] = []

    def set_state(self, device_state) -> None:
        self.states.append(str(device_state))


class _DeferredThread:
    """Thread double that records launches without running the target."""

    started_threads: list["_DeferredThread"] = []

    def __init__(self, target=None, args=(), kwargs=None, daemon=None, name=None) -> None:
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        self.daemon = daemon
        self.name = name

    def start(self) -> None:
        self.started = True
        type(self).started_threads.append(self)
