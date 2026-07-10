"""Persistent offline retry queue for deferred AI analysis jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
import shutil
import threading
from typing import Any, Callable, TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from pipeline.runner import PipelineResult

LOGGER = logging.getLogger(__name__)

AnalyzeRetryFunc = Callable[["OfflineRetryEntry"], "PipelineResult"]
RetrySuccessCallback = Callable[["OfflineRetryEntry", "PipelineResult"], None]
RetryFailureCallback = Callable[["OfflineRetryEntry", Exception, bool], None]


class OfflineRetryQueueError(Exception):
    """Base error raised for queue persistence or validation failures."""


class OfflineRetryQueueFullError(OfflineRetryQueueError):
    """Raised when the queue already contains the configured maximum entries."""


@dataclass(slots=True)
class OfflineRetryEntry:
    """Single deferred AI analysis request stored on disk."""

    id: str
    created_at: str
    updated_at: str
    selected_mode: str
    selected_mode_internal: str
    captured_path: str
    processed_path: str
    camera_backend_used: str
    camera_resolution: tuple[int, int] | None
    last_error: str
    attempt_count: int
    next_attempt_at: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "selected_mode": self.selected_mode,
            "selected_mode_internal": self.selected_mode_internal,
            "captured_path": self.captured_path,
            "processed_path": self.processed_path,
            "camera_backend_used": self.camera_backend_used,
            "camera_resolution": list(self.camera_resolution) if self.camera_resolution is not None else None,
            "last_error": self.last_error,
            "attempt_count": self.attempt_count,
            "next_attempt_at": self.next_attempt_at,
        }


class OfflineRetryQueue:
    """Durable FIFO queue that retries transient AI analysis failures in the background."""

    def __init__(
        self,
        *,
        queue_path: str | Path,
        storage_dir: str | Path,
        poll_interval_seconds: float = 30.0,
        max_entries: int = 24,
    ) -> None:
        self.queue_path = Path(queue_path)
        self.storage_dir = Path(storage_dir)
        self.poll_interval_seconds = max(5.0, float(poll_interval_seconds))
        self.max_entries = max(1, int(max_entries))
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._analyze_func: AnalyzeRetryFunc | None = None
        self._success_callback: RetrySuccessCallback | None = None
        self._failure_callback: RetryFailureCallback | None = None

    def start(
        self,
        *,
        analyze_func: AnalyzeRetryFunc,
        success_callback: RetrySuccessCallback,
        failure_callback: RetryFailureCallback | None = None,
    ) -> bool:
        """Start the background retry worker once."""
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return False
            self._analyze_func = analyze_func
            self._success_callback = success_callback
            self._failure_callback = failure_callback
            self._stop_event.clear()
            self._wake_event.set()
            self._worker = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name="offline-retry-worker",
            )
            self._worker.start()
        return True

    def close(self) -> None:
        """Stop the background retry worker."""
        self._stop_event.set()
        self._wake_event.set()
        worker = self._worker
        if worker is not None:
            worker.join(timeout=1.0)

    def list_entries(self) -> list[OfflineRetryEntry]:
        """Return the current persisted entries in FIFO order."""
        with self._lock:
            return self._load_entries_locked()

    def pending_count(self) -> int:
        """Return the number of queued entries still awaiting retry."""
        return len(self.list_entries())

    def snapshot(self) -> dict[str, Any]:
        """Return a small public summary of the queue state."""
        entries = self.list_entries()
        next_attempt_at = entries[0].next_attempt_at if entries else ""
        return {
            "pending_count": len(entries),
            "next_attempt_at": next_attempt_at,
        }

    def enqueue(
        self,
        *,
        selected_mode: str,
        selected_mode_internal: str,
        processed_path: str | Path,
        captured_path: str | Path | None = None,
        camera_backend_used: str | None = None,
        camera_resolution: tuple[int, int] | None = None,
        error_message: str = "",
    ) -> OfflineRetryEntry:
        """Persist a capture for later re-analysis when transient failures occur."""
        processed_file = Path(processed_path)
        if not processed_file.is_file():
            raise OfflineRetryQueueError(
                f"Cannot queue retry because processed image '{processed_file}' is missing."
            )

        captured_file = Path(captured_path) if captured_path else None
        if captured_file is not None and not captured_file.is_file():
            captured_file = None

        with self._lock:
            entries = self._load_entries_locked()
            if len(entries) >= self.max_entries:
                raise OfflineRetryQueueFullError(
                    f"Offline retry queue is full ({self.max_entries} pending item(s))."
                )

            entry_id = uuid4().hex
            entry_dir = self.storage_dir / entry_id
            entry_dir.mkdir(parents=True, exist_ok=False)

            queued_processed_path = entry_dir / f"processed{processed_file.suffix.lower() or '.jpg'}"
            shutil.copy2(processed_file, queued_processed_path)

            queued_captured_path = ""
            if captured_file is not None:
                copied_captured_path = entry_dir / f"captured{captured_file.suffix.lower() or '.jpg'}"
                shutil.copy2(captured_file, copied_captured_path)
                queued_captured_path = str(copied_captured_path)

            now = _now_iso()
            entry = OfflineRetryEntry(
                id=entry_id,
                created_at=now,
                updated_at=now,
                selected_mode=selected_mode,
                selected_mode_internal=selected_mode_internal,
                captured_path=queued_captured_path,
                processed_path=str(queued_processed_path),
                camera_backend_used=camera_backend_used or "",
                camera_resolution=camera_resolution,
                last_error=error_message.strip(),
                attempt_count=0,
                next_attempt_at=now,
            )
            entries.append(entry)
            self._write_entries_locked(entries)

        self._wake_event.set()
        LOGGER.warning(
            "Queued offline retry entry=%s ui_mode=%s internal_mode=%s",
            entry.id,
            selected_mode,
            selected_mode_internal,
        )
        return entry

    def process_once(
        self,
        *,
        analyze_func: AnalyzeRetryFunc,
        success_callback: RetrySuccessCallback,
        failure_callback: RetryFailureCallback | None = None,
    ) -> bool:
        """Process at most one ready entry and return True when work was attempted."""
        with self._lock:
            entries = self._load_entries_locked()
            entry = _find_ready_entry(entries)
            if entry is None:
                return False

        try:
            result = analyze_func(entry)
        except Exception as exc:
            retryable = bool(getattr(exc, "retryable", False))
            with self._lock:
                entries = self._load_entries_locked()
                current_entry = _find_entry_by_id(entries, entry.id)
                if current_entry is None:
                    return True

                if retryable:
                    current_entry.attempt_count += 1
                    current_entry.last_error = str(exc)
                    current_entry.updated_at = _now_iso()
                    current_entry.next_attempt_at = _future_iso(
                        self._retry_delay_seconds(current_entry.attempt_count)
                    )
                    self._write_entries_locked(entries)
                else:
                    self._remove_entry_files(current_entry)
                    entries = [candidate for candidate in entries if candidate.id != current_entry.id]
                    self._write_entries_locked(entries)

            if failure_callback is not None:
                failure_callback(entry, exc, retryable)
            return True

        with self._lock:
            entries = self._load_entries_locked()
            current_entry = _find_entry_by_id(entries, entry.id)
            if current_entry is not None:
                self._remove_entry_files(current_entry)
                entries = [candidate for candidate in entries if candidate.id != current_entry.id]
                self._write_entries_locked(entries)

        success_callback(entry, result)
        return True

    def _worker_loop(self) -> None:
        """Continuously process queued entries until shutdown."""
        while not self._stop_event.is_set():
            analyze_func = self._analyze_func
            success_callback = self._success_callback
            if analyze_func is None or success_callback is None:
                return

            try:
                did_work = self.process_once(
                    analyze_func=analyze_func,
                    success_callback=success_callback,
                    failure_callback=self._failure_callback,
                )
            except Exception:
                LOGGER.exception("Offline retry worker crashed while processing the queue")
                did_work = False

            if did_work:
                continue

            self._wake_event.wait(timeout=self.poll_interval_seconds)
            self._wake_event.clear()

    def _load_entries_locked(self) -> list[OfflineRetryEntry]:
        """Load and validate the persisted queue file."""
        if not self.queue_path.is_file():
            return []

        try:
            payload = json.loads(self.queue_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            LOGGER.exception("Offline retry queue file could not be read: %s", self.queue_path)
            return []

        if not isinstance(payload, list):
            LOGGER.warning("Offline retry queue file is not a list: %s", self.queue_path)
            return []

        entries: list[OfflineRetryEntry] = []
        for raw_entry in payload:
            entry = _coerce_entry(raw_entry)
            if entry is not None:
                entries.append(entry)
        return entries

    def _write_entries_locked(self, entries: list[OfflineRetryEntry]) -> None:
        """Write the full queue snapshot back to disk atomically."""
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        temp_path = self.queue_path.with_suffix(f"{self.queue_path.suffix}.tmp")
        payload = [entry.to_dict() for entry in entries]
        temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(self.queue_path)

    def _remove_entry_files(self, entry: OfflineRetryEntry) -> None:
        """Delete any copied images for the entry after processing completes."""
        entry_dir = self.storage_dir / entry.id
        shutil.rmtree(entry_dir, ignore_errors=True)

    def _retry_delay_seconds(self, attempt_count: int) -> float:
        """Return the next background retry delay with a small exponential backoff."""
        multiplier = min(8, 2 ** max(0, attempt_count - 1))
        return self.poll_interval_seconds * multiplier


def _coerce_entry(raw_entry: Any) -> OfflineRetryEntry | None:
    """Validate a queue payload entry loaded from disk."""
    if not isinstance(raw_entry, dict):
        return None

    entry_id = str(raw_entry.get("id", "")).strip()
    selected_mode = str(raw_entry.get("selected_mode", "")).strip()
    selected_mode_internal = str(raw_entry.get("selected_mode_internal", "")).strip()
    processed_path = str(raw_entry.get("processed_path", "")).strip()
    created_at = str(raw_entry.get("created_at", "")).strip() or _now_iso()
    updated_at = str(raw_entry.get("updated_at", "")).strip() or created_at
    next_attempt_at = str(raw_entry.get("next_attempt_at", "")).strip() or updated_at
    if not entry_id or not selected_mode_internal or not processed_path:
        return None

    resolution = raw_entry.get("camera_resolution")
    camera_resolution: tuple[int, int] | None = None
    if isinstance(resolution, (list, tuple)) and len(resolution) == 2:
        try:
            camera_resolution = (int(resolution[0]), int(resolution[1]))
        except (TypeError, ValueError):
            camera_resolution = None

    try:
        attempt_count = max(0, int(raw_entry.get("attempt_count", 0)))
    except (TypeError, ValueError):
        attempt_count = 0

    return OfflineRetryEntry(
        id=entry_id,
        created_at=created_at,
        updated_at=updated_at,
        selected_mode=selected_mode,
        selected_mode_internal=selected_mode_internal,
        captured_path=str(raw_entry.get("captured_path", "")).strip(),
        processed_path=processed_path,
        camera_backend_used=str(raw_entry.get("camera_backend_used", "")).strip(),
        camera_resolution=camera_resolution,
        last_error=str(raw_entry.get("last_error", "")).strip(),
        attempt_count=attempt_count,
        next_attempt_at=next_attempt_at,
    )


def _find_ready_entry(entries: list[OfflineRetryEntry]) -> OfflineRetryEntry | None:
    """Return the first queued entry whose retry time has arrived."""
    now = datetime.now()
    for entry in entries:
        try:
            next_attempt = datetime.fromisoformat(entry.next_attempt_at)
        except ValueError:
            next_attempt = now
        if next_attempt <= now:
            return entry
    return None


def _find_entry_by_id(entries: list[OfflineRetryEntry], entry_id: str) -> OfflineRetryEntry | None:
    """Return the entry with the matching identifier, if it still exists."""
    for entry in entries:
        if entry.id == entry_id:
            return entry
    return None


def _now_iso() -> str:
    """Return a second-precision ISO timestamp for queue metadata."""
    return datetime.now().replace(microsecond=0).isoformat()


def _future_iso(delay_seconds: float) -> str:
    """Return a future ISO timestamp offset by the given delay."""
    return (datetime.now() + timedelta(seconds=max(0.0, delay_seconds))).replace(
        microsecond=0
    ).isoformat()
