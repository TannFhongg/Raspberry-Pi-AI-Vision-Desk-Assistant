"""Unit tests for the durable offline retry queue."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipeline.runner import PipelineError, PipelineResult
from system.offline_retry import OfflineRetryQueue


class OfflineRetryQueueTests(unittest.TestCase):
    """Verify deferred AI retries persist to disk and recover safely."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="offline-retry-test-"))
        self.queue = OfflineRetryQueue(
            queue_path=self.temp_dir / "queue.json",
            storage_dir=self.temp_dir / "entries",
            poll_interval_seconds=10.0,
            max_entries=4,
        )
        self.captured_path = self.temp_dir / "captured.jpg"
        self.processed_path = self.temp_dir / "processed.jpg"
        self.captured_path.write_bytes(b"captured")
        self.processed_path.write_bytes(b"processed")

    def test_enqueue_persists_copied_files_and_process_once_succeeds(self) -> None:
        entry = self.queue.enqueue(
            selected_mode="read_text",
            selected_mode_internal="document_reader",
            captured_path=self.captured_path,
            processed_path=self.processed_path,
            camera_backend_used="picamera2",
            camera_resolution=(1920, 1080),
            error_message="network down",
        )

        self.assertEqual(self.queue.pending_count(), 1)
        self.assertTrue(Path(entry.processed_path).is_file())
        self.assertTrue(Path(entry.captured_path).is_file())

        callback_results: list[PipelineResult] = []

        processed = self.queue.process_once(
            analyze_func=lambda queued_entry: PipelineResult(
                captured_path=Path(queued_entry.captured_path),
                processed_path=Path(queued_entry.processed_path),
                answer="Recovered answer",
                mode=queued_entry.selected_mode_internal,
                camera_backend_used=queued_entry.camera_backend_used,
                camera_resolution=queued_entry.camera_resolution,
                status="success",
            ),
            success_callback=lambda _entry, result: callback_results.append(result),
        )

        self.assertTrue(processed)
        self.assertEqual(self.queue.pending_count(), 0)
        self.assertEqual(len(callback_results), 1)
        self.assertEqual(callback_results[0].answer, "Recovered answer")
        self.assertFalse((self.temp_dir / "entries" / entry.id).exists())

    def test_process_once_reschedules_retryable_failures(self) -> None:
        entry = self.queue.enqueue(
            selected_mode="read_text",
            selected_mode_internal="document_reader",
            processed_path=self.processed_path,
            error_message="network down",
        )
        failure_events: list[tuple[str, bool]] = []

        processed = self.queue.process_once(
            analyze_func=lambda _queued_entry: _raise_pipeline_error(
                PipelineError("network still down", retryable=True)
            ),
            success_callback=lambda _entry, _result: None,
            failure_callback=lambda failed_entry, _error, retryable: failure_events.append(
                (failed_entry.id, retryable)
            ),
        )

        self.assertTrue(processed)
        self.assertEqual(failure_events, [(entry.id, True)])
        queued_entries = self.queue.list_entries()
        self.assertEqual(len(queued_entries), 1)
        self.assertEqual(queued_entries[0].attempt_count, 1)
        self.assertEqual(queued_entries[0].last_error, "network still down")
        self.assertNotEqual(queued_entries[0].next_attempt_at, queued_entries[0].created_at)

    def test_process_once_drops_nonretryable_failures(self) -> None:
        entry = self.queue.enqueue(
            selected_mode="read_text",
            selected_mode_internal="document_reader",
            processed_path=self.processed_path,
            error_message="network down",
        )
        failure_events: list[tuple[str, bool]] = []

        processed = self.queue.process_once(
            analyze_func=lambda _queued_entry: _raise_pipeline_error(
                PipelineError("invalid image file", retryable=False)
            ),
            success_callback=lambda _entry, _result: None,
            failure_callback=lambda failed_entry, _error, retryable: failure_events.append(
                (failed_entry.id, retryable)
            ),
        )

        self.assertTrue(processed)
        self.assertEqual(failure_events, [(entry.id, False)])
        self.assertEqual(self.queue.pending_count(), 0)
        self.assertFalse((self.temp_dir / "entries" / entry.id).exists())


def _raise_pipeline_error(error: PipelineError):
    """Raise the provided pipeline error inside a lambda-friendly helper."""
    raise error


if __name__ == "__main__":
    unittest.main()
