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

    def test_live_preview_routes_keep_no_store_cache_headers(self) -> None:
        client = app_module.app.test_client()

        frame_response = client.get("/camera/live-frame.jpg")
        stream_response = client.get("/camera/live-stream.mjpg")

        self.assertEqual(frame_response.status_code, 200)
        self.assertEqual(frame_response.headers["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")
        self.assertEqual(stream_response.status_code, 200)
        self.assertIn("boundary=frame", stream_response.content_type)
        self.assertEqual(stream_response.headers["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")

    def test_linux_live_frame_route_uses_direct_preview_capture(self) -> None:
        client = app_module.app.test_client()

        with patch("app.sys.platform", "linux"), patch("app.capture_preview_jpeg", return_value=b"linux-frame"):
            response = client.get("/camera/live-frame.jpg")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"linux-frame")

    def test_linux_template_context_prefers_live_frame_preview_refresh(self) -> None:
        with patch("app.sys.platform", "linux"):
            with app_module.app.test_request_context("/"):
                context = app_module._build_template_context()

        self.assertIn("/camera/live-frame.jpg", context["live_preview_url"])
        self.assertIn("/camera/live-frame.jpg", context["live_preview_base_url"])
        self.assertGreaterEqual(context["live_preview_refresh_ms"], 1500)

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
        state = app_module._load_ui_state()
        self.assertEqual(state["screen"], "result")
        history_entries = app_module._load_result_history()
        self.assertEqual(len(history_entries), 1)
        self.assertEqual(history_entries[0]["model_used"], "gpt-5.4-mini")
        self.assertNotIn("source_image_path", history_entries[0])
        self.assertNotIn("processed_image_path", history_entries[0])

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
        self.assertEqual(self.queue.pending_count(), 1)
        entry = self.queue.list_entries()[0]
        self.assertTrue(self.queue.resolve_processed_path(entry).is_file())
        self.assertEqual(app_module._load_result_history(), [])

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


class _FakeLEDIndicator:
    """Small LED double for app tests that only records the latest state."""

    disabled_reason = ""

    def __init__(self) -> None:
        self.states: list[str] = []

    def set_state(self, device_state) -> None:
        self.states.append(str(device_state))
