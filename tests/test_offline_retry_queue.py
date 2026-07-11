"""Unit tests for the durable offline retry queue."""

from __future__ import annotations

import json
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
            poll_interval_seconds=1.0,
            max_entries=4,
            max_attempts=3,
            initial_delay_seconds=1.0,
            max_delay_seconds=60.0,
            retention_hours=24.0,
            min_free_bytes=1,
            max_storage_bytes=10 * 1024 * 1024,
            quarantine_dir=self.temp_dir / "quarantine",
        )
        self.processed_path = self.temp_dir / "processed.jpg"
        self.processed_path.write_bytes(b"processed")

    def test_enqueue_persists_private_processed_file_and_process_once_succeeds(self) -> None:
        entry = self.queue.enqueue(
            selected_mode="read_text",
            selected_mode_internal="document_reader",
            processed_path=self.processed_path,
            camera_backend_used="opencv",
            camera_resolution=(1920, 1080),
            error_message="network down",
        )

        self.assertEqual(self.queue.pending_count(), 1)
        self.assertFalse(Path(entry.processed_filename).is_absolute())
        self.assertTrue(self.queue.resolve_processed_path(entry).is_file())

        callback_results: list[PipelineResult] = []
        _mark_entry_ready(self.queue.queue_path, entry.id)

        processed = self.queue.process_once(
            analyze_func=lambda queued_entry: PipelineResult(
                captured_path=None,
                processed_path=self.queue.resolve_processed_path(queued_entry),
                answer="Recovered answer",
                mode=queued_entry.selected_mode_internal,
                camera_backend_used=queued_entry.camera_backend_used,
                camera_resolution=queued_entry.camera_resolution,
                status="success",
                retry_status="retry_successful",
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
        _mark_entry_ready(self.queue.queue_path, entry.id)

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
        self.assertEqual(queued_entries[0].status, "pending")
        self.assertNotEqual(queued_entries[0].next_attempt_at, queued_entries[0].created_at)

    def test_process_once_drops_nonretryable_failures(self) -> None:
        entry = self.queue.enqueue(
            selected_mode="read_text",
            selected_mode_internal="document_reader",
            processed_path=self.processed_path,
            error_message="network down",
        )
        failure_events: list[tuple[str, bool]] = []
        _mark_entry_ready(self.queue.queue_path, entry.id)

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


def _mark_entry_ready(queue_path: Path, entry_id: str) -> None:
    """Force a queued retry entry to become immediately runnable."""
    payload = json.loads(queue_path.read_text(encoding="utf-8"))
    for entry in payload:
        if entry.get("id") == entry_id:
            entry["next_attempt_at"] = "2000-01-01T00:00:00"
    queue_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def _raise_pipeline_error(error: PipelineError):
    """Raise the provided pipeline error inside a lambda-friendly helper."""
    raise error


if __name__ == "__main__":
    unittest.main()
