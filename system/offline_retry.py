"""Persistent offline retry queue for deferred AI analysis jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import logging
from pathlib import Path
import random
import shutil
import threading
from typing import Any, Callable, TYPE_CHECKING
from uuid import uuid4

from system.storage import atomic_write_json, quarantine_file, safe_rmtree

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
    expires_at: str
    selected_mode: str
    selected_mode_internal: str
    processed_filename: str
    camera_backend_used: str
    camera_resolution: tuple[int, int] | None
    last_error: str
    last_error_category: str
    attempt_count: int
    next_attempt_at: str
    status: str
    checksum: str
    processing_started_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "selected_mode": self.selected_mode,
            "selected_mode_internal": self.selected_mode_internal,
            "processed_filename": self.processed_filename,
            "camera_backend_used": self.camera_backend_used,
            "camera_resolution": list(self.camera_resolution) if self.camera_resolution is not None else None,
            "last_error": self.last_error,
            "last_error_category": self.last_error_category,
            "attempt_count": self.attempt_count,
            "next_attempt_at": self.next_attempt_at,
            "status": self.status,
            "checksum": self.checksum,
            "processing_started_at": self.processing_started_at,
        }


class OfflineRetryQueue:
    """Durable FIFO queue that retries transient AI analysis failures in the background."""

    def __init__(
        self,
        *,
        queue_path: str | Path,
        storage_dir: str | Path,
        poll_interval_seconds: float = 5.0,
        max_entries: int = 10,
        max_attempts: int = 3,
        initial_delay_seconds: float = 30.0,
        max_delay_seconds: float = 900.0,
        retention_hours: float = 24.0,
        min_free_bytes: int = 128 * 1024 * 1024,
        max_storage_bytes: int = 512 * 1024 * 1024,
        quarantine_dir: str | Path | None = None,
    ) -> None:
        self.queue_path = Path(queue_path)
        self.storage_dir = Path(storage_dir)
        self.poll_interval_seconds = max(1.0, float(poll_interval_seconds))
        self.max_entries = max(1, int(max_entries))
        self.max_attempts = max(1, int(max_attempts))
        self.initial_delay_seconds = max(1.0, float(initial_delay_seconds))
        self.max_delay_seconds = max(self.initial_delay_seconds, float(max_delay_seconds))
        self.retention_hours = max(0.1, float(retention_hours))
        self.min_free_bytes = max(1, int(min_free_bytes))
        self.max_storage_bytes = max(1, int(max_storage_bytes))
        self.quarantine_dir = (
            Path(quarantine_dir)
            if quarantine_dir is not None
            else self.storage_dir.parent / "quarantine"
        )
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

    def close(self, *, timeout: float = 5.0) -> bool:
        """Stop the background retry worker and report whether it exited."""
        self._stop_event.set()
        self._wake_event.set()
        worker = self._worker
        if worker is not None:
            worker.join(timeout=max(0.0, timeout))
            return not worker.is_alive()
        return True

    def list_entries(self) -> list[OfflineRetryEntry]:
        """Return the current persisted entries in FIFO order."""
        with self._lock:
            entries = self._load_entries_locked()
            self._recover_processing_entries_locked(entries)
            return [entry for entry in entries]

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
            "storage_bytes": self._storage_usage_bytes(),
        }

    def clear(self) -> None:
        """Delete all queue metadata and retained retry media."""
        with self._lock:
            atomic_write_json(self.queue_path, [], ensure_ascii=True, indent=2)
            safe_rmtree(self.storage_dir)

    def prune(self) -> dict[str, int]:
        """Remove expired entries and orphaned files from private retry storage."""
        removed_entries = 0
        removed_orphans = 0

        with self._lock:
            entries = self._load_entries_locked()
            kept_entries: list[OfflineRetryEntry] = []
            now = datetime.now()
            for entry in entries:
                expires_at = _parse_iso(entry.expires_at) or now
                processed_path = self.resolve_processed_path(entry)
                if expires_at <= now or not processed_path.is_file():
                    self._remove_entry_files(entry)
                    removed_entries += 1
                    continue
                kept_entries.append(entry)

            self._write_entries_locked(kept_entries)
            known_ids = {entry.id for entry in kept_entries}
            if self.storage_dir.is_dir():
                for child in self.storage_dir.iterdir():
                    if child.is_dir() and child.name not in known_ids:
                        safe_rmtree(child)
                        removed_orphans += 1

        return {
            "removed_entries": removed_entries,
            "removed_orphans": removed_orphans,
        }

    def enqueue(
        self,
        *,
        selected_mode: str,
        selected_mode_internal: str,
        processed_path: str | Path,
        camera_backend_used: str | None = None,
        camera_resolution: tuple[int, int] | None = None,
        error_message: str = "",
        error_category: str = "",
    ) -> OfflineRetryEntry:
        """Persist a processed image for later re-analysis when transient failures occur."""
        processed_file = Path(processed_path)
        if not processed_file.is_file():
            raise OfflineRetryQueueError(
                f"Cannot queue retry because processed image '{processed_file}' is missing."
            )

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        source_size = processed_file.stat().st_size
        if self._storage_usage_bytes() + source_size > self.max_storage_bytes:
            raise OfflineRetryQueueFullError(
                "Offline retry storage is full. Delete queued jobs or wait for retries to finish."
            )
        if shutil.disk_usage(self.storage_dir).free < self.min_free_bytes:
            raise OfflineRetryQueueError(
                "Offline retry storage is below the safe free-space threshold."
            )

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
            checksum = _sha256_file(queued_processed_path)
            now = _now_iso()
            entry = OfflineRetryEntry(
                id=entry_id,
                created_at=now,
                updated_at=now,
                expires_at=_future_iso(self.retention_hours * 3600.0),
                selected_mode=selected_mode,
                selected_mode_internal=selected_mode_internal,
                processed_filename=f"{entry_id}/{queued_processed_path.name}",
                camera_backend_used=camera_backend_used or "",
                camera_resolution=camera_resolution,
                last_error=error_message.strip(),
                last_error_category=(error_category or _categorize_error_message(error_message)).strip(),
                attempt_count=0,
                next_attempt_at=_future_iso(self.initial_delay_seconds),
                status="pending",
                checksum=checksum,
                processing_started_at="",
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
            self._recover_processing_entries_locked(entries)
            entry = _find_ready_entry(entries)
            if entry is None:
                return False
            current_entry = _find_entry_by_id(entries, entry.id)
            if current_entry is None:
                return False
            current_entry.status = "processing"
            current_entry.processing_started_at = _now_iso()
            current_entry.updated_at = current_entry.processing_started_at
            self._write_entries_locked(entries)

        try:
            result = analyze_func(entry)
        except Exception as exc:
            retryable = bool(getattr(exc, "retryable", False))
            should_keep = False
            with self._lock:
                entries = self._load_entries_locked()
                current_entry = _find_entry_by_id(entries, entry.id)
                if current_entry is None:
                    return True

                current_entry.attempt_count += 1
                current_entry.last_error = str(exc)
                current_entry.last_error_category = _categorize_error_message(str(exc))
                current_entry.updated_at = _now_iso()
                current_entry.processing_started_at = ""

                if retryable and current_entry.attempt_count < self.max_attempts:
                    current_entry.status = "pending"
                    current_entry.next_attempt_at = _future_iso(
                        self._retry_delay_seconds(current_entry.attempt_count)
                    )
                    self._write_entries_locked(entries)
                    should_keep = True
                else:
                    self._remove_entry_files(current_entry)
                    entries = [candidate for candidate in entries if candidate.id != current_entry.id]
                    self._write_entries_locked(entries)

            if failure_callback is not None:
                failure_callback(entry, exc, retryable and should_keep)
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

    def resolve_processed_path(self, entry: OfflineRetryEntry) -> Path:
        """Return the private absolute processed-image path for an entry."""
        return self.storage_dir / entry.processed_filename

    def _worker_loop(self) -> None:
        """Continuously process queued entries until shutdown."""
        while not self._stop_event.is_set():
            analyze_func = self._analyze_func
            success_callback = self._success_callback
            if analyze_func is None or success_callback is None:
                return

            try:
                self.prune()
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
            quarantine_file(
                self.queue_path,
                quarantine_dir=self.quarantine_dir,
                reason="invalid-queue-json",
            )
            return []

        if not isinstance(payload, list):
            LOGGER.warning("Offline retry queue file is not a list: %s", self.queue_path)
            quarantine_file(
                self.queue_path,
                quarantine_dir=self.quarantine_dir,
                reason="invalid-queue-shape",
            )
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
        payload = [entry.to_dict() for entry in entries]
        atomic_write_json(self.queue_path, payload, ensure_ascii=True, indent=2)

    def _recover_processing_entries_locked(self, entries: list[OfflineRetryEntry]) -> None:
        """Requeue jobs that were left mid-flight by a reboot or crash."""
        changed = False
        for entry in entries:
            if entry.status != "processing":
                continue
            entry.status = "pending"
            entry.processing_started_at = ""
            entry.updated_at = _now_iso()
            entry.next_attempt_at = _future_iso(self.initial_delay_seconds)
            changed = True
        if changed:
            self._write_entries_locked(entries)

    def _remove_entry_files(self, entry: OfflineRetryEntry) -> None:
        """Delete any copied images for the entry after processing completes."""
        safe_rmtree(self.storage_dir / entry.id)

    def _retry_delay_seconds(self, attempt_count: int) -> float:
        """Return the next background retry delay with capped exponential backoff and jitter."""
        base_delay = min(
            self.max_delay_seconds,
            self.initial_delay_seconds * (2 ** max(0, attempt_count - 1)),
        )
        return min(self.max_delay_seconds, base_delay * random.uniform(0.75, 1.25))

    def _storage_usage_bytes(self) -> int:
        """Return the total bytes currently retained in private retry storage."""
        if not self.storage_dir.is_dir():
            return 0
        total_bytes = 0
        for path in self.storage_dir.rglob("*"):
            if path.is_file():
                total_bytes += path.stat().st_size
        return total_bytes


def _coerce_entry(raw_entry: Any) -> OfflineRetryEntry | None:
    """Validate a queue payload entry loaded from disk."""
    if not isinstance(raw_entry, dict):
        return None

    entry_id = str(raw_entry.get("id", "")).strip()
    selected_mode = str(raw_entry.get("selected_mode", "")).strip()
    selected_mode_internal = str(raw_entry.get("selected_mode_internal", "")).strip()
    processed_filename = str(raw_entry.get("processed_filename", "")).strip()
    if not entry_id or not selected_mode_internal or not processed_filename:
        return None
    if Path(processed_filename).is_absolute():
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

    created_at = str(raw_entry.get("created_at", "")).strip() or _now_iso()
    updated_at = str(raw_entry.get("updated_at", "")).strip() or created_at
    expires_at = str(raw_entry.get("expires_at", "")).strip() or _future_iso(24 * 3600.0)
    next_attempt_at = str(raw_entry.get("next_attempt_at", "")).strip() or updated_at
    status = str(raw_entry.get("status", "pending")).strip().lower() or "pending"
    if status not in {"pending", "processing"}:
        status = "pending"

    return OfflineRetryEntry(
        id=entry_id,
        created_at=created_at,
        updated_at=updated_at,
        expires_at=expires_at,
        selected_mode=selected_mode,
        selected_mode_internal=selected_mode_internal,
        processed_filename=processed_filename,
        camera_backend_used=str(raw_entry.get("camera_backend_used", "")).strip(),
        camera_resolution=camera_resolution,
        last_error=str(raw_entry.get("last_error", "")).strip(),
        last_error_category=str(raw_entry.get("last_error_category", "")).strip(),
        attempt_count=attempt_count,
        next_attempt_at=next_attempt_at,
        status=status,
        checksum=str(raw_entry.get("checksum", "")).strip(),
        processing_started_at=str(raw_entry.get("processing_started_at", "")).strip(),
    )


def _find_ready_entry(entries: list[OfflineRetryEntry]) -> OfflineRetryEntry | None:
    """Return the first queued entry whose retry time has arrived."""
    now = datetime.now()
    for entry in entries:
        if entry.status != "pending":
            continue
        expires_at = _parse_iso(entry.expires_at)
        if expires_at is not None and expires_at <= now:
            continue
        next_attempt = _parse_iso(entry.next_attempt_at) or now
        if next_attempt <= now:
            return entry
    return None


def _find_entry_by_id(entries: list[OfflineRetryEntry], entry_id: str) -> OfflineRetryEntry | None:
    """Return the entry with the matching identifier, if it still exists."""
    for entry in entries:
        if entry.id == entry_id:
            return entry
    return None


def _parse_iso(value: str) -> datetime | None:
    """Parse an ISO timestamp into a datetime when possible."""
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _categorize_error_message(message: str) -> str:
    """Collapse a retry error string into a small category label."""
    normalized = message.strip().lower()
    if "rate limit" in normalized or "quota" in normalized:
        return "rate_limit"
    if "timed out" in normalized or "timeout" in normalized:
        return "timeout"
    if "connect" in normalized or "network" in normalized:
        return "network"
    if "status 5" in normalized or "server error" in normalized:
        return "server_error"
    return "unknown"


def _sha256_file(path: Path) -> str:
    """Return the sha256 checksum of a private retry media file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now_iso() -> str:
    """Return a millisecond-precision ISO timestamp for queue metadata."""
    return datetime.now().isoformat(timespec="milliseconds")


def _future_iso(delay_seconds: float) -> str:
    """Return a future ISO timestamp offset by the given delay."""
    return (
        datetime.now() + timedelta(seconds=max(0.0, delay_seconds))
    ).isoformat(timespec="milliseconds")
