"""Shared text-only result history storage for the native VisionDesk app."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import threading
from pathlib import Path
from typing import Any, Callable

from system.storage import atomic_write_json, quarantine_file

try:
    from pipeline.runner import PipelineResult
except ImportError:  # pragma: no cover - import-safe typing fallback
    PipelineResult = Any  # type: ignore[assignment]


class ResultHistoryStore:
    """Load, validate, retain, and mutate recent text-only result history entries."""

    def __init__(
        self,
        *,
        history_path: str | Path,
        quarantine_dir: str | Path,
        retention_days: int,
        result_limit: int,
        resolve_mode_pair: Callable[[Any, Any], tuple[str, str]],
        mode_label_resolver: Callable[[str, str], str],
        timestamp_provider: Callable[[], str],
    ) -> None:
        self.history_path = Path(history_path)
        self.quarantine_dir = Path(quarantine_dir)
        self.retention_days = max(1, int(retention_days))
        self.result_limit = max(1, int(result_limit))
        self.resolve_mode_pair = resolve_mode_pair
        self.mode_label_resolver = mode_label_resolver
        self.timestamp_provider = timestamp_provider
        self._lock = threading.Lock()
        self._cache: list[dict[str, Any]] | None = None
        self._last_load_status = "empty"
        self._last_load_message = ""

    def load_entries(self) -> list[dict[str, Any]]:
        """Return the recent result history from memory or disk."""
        return list(self.load_snapshot()["entries"])

    def load_snapshot(self) -> dict[str, Any]:
        """Return entries plus a status describing empty, recovered, or error states."""
        with self._lock:
            if self._cache is not None:
                return self._build_snapshot(
                    self._cache,
                    status=self._last_load_status,
                    message=self._last_load_message,
                )

            if not self.history_path.is_file():
                self._cache = []
                self._last_load_status = "empty"
                self._last_load_message = ""
                return self._build_snapshot(self._cache, status="empty")

            try:
                raw_entries = json.loads(self.history_path.read_text(encoding="utf-8"))
            except OSError:
                self._cache = []
                self._last_load_status = "error"
                self._last_load_message = "Result history could not be read."
                return self._build_snapshot(
                    self._cache,
                    status=self._last_load_status,
                    message=self._last_load_message,
                )
            except json.JSONDecodeError:
                quarantine_file(
                    self.history_path,
                    quarantine_dir=self.quarantine_dir,
                    reason="invalid-history-json",
                )
                self._cache = []
                self._last_load_status = "recovered"
                self._last_load_message = "Corrupted result history was reset."
                return self._build_snapshot(
                    self._cache,
                    status=self._last_load_status,
                    message=self._last_load_message,
                )

            parsed_entries: list[dict[str, Any]] = []
            if not isinstance(raw_entries, list):
                quarantine_file(
                    self.history_path,
                    quarantine_dir=self.quarantine_dir,
                    reason="invalid-history-shape",
                )
                self._cache = []
                self._last_load_status = "recovered"
                self._last_load_message = "Corrupted result history was reset."
                return self._build_snapshot(
                    self._cache,
                    status=self._last_load_status,
                    message=self._last_load_message,
                )

            for raw_entry in raw_entries:
                entry = self.coerce_entry(raw_entry)
                if entry is not None:
                    parsed_entries.append(entry)

            self._cache = self.apply_retention(parsed_entries)
            self._last_load_status = "empty" if not self._cache else "ok"
            self._last_load_message = ""
            return self._build_snapshot(
                self._cache,
                status=self._last_load_status,
                message=self._last_load_message,
            )

    def write_entries(self, entries: list[dict[str, Any]]) -> None:
        """Persist recent result history and refresh the in-memory cache."""
        normalized_input: list[dict[str, Any]] = []
        for entry in entries[: self.result_limit]:
            coerced_entry = self.coerce_entry(entry)
            if coerced_entry is not None:
                normalized_input.append(coerced_entry)
        normalized_entries = self.apply_retention(normalized_input)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            self._cache = normalized_entries
            self._last_load_status = "empty" if not normalized_entries else "ok"
            self._last_load_message = ""
            atomic_write_json(
                self.history_path,
                normalized_entries,
                ensure_ascii=False,
                indent=2,
            )

    def append_result(
        self,
        result: PipelineResult,
        selected_mode: str,
        selected_mode_internal: str,
    ) -> dict[str, Any] | None:
        """Save a successful assistant response into recent-results history."""
        answer = (result.answer or "").strip()
        if not answer:
            return None

        ui_mode, internal_mode = self.resolve_mode_pair(selected_mode, selected_mode_internal)
        history_entries = self.load_entries()
        created_at = self.timestamp_provider()
        entry_id = str(int(datetime.now().timestamp() * 1000))
        history_entry = {
            "id": entry_id,
            "created_at": created_at,
            "selected_mode": ui_mode,
            "selected_mode_internal": internal_mode,
            "mode_label": self.mode_label_resolver(ui_mode, internal_mode),
            "status": result.status,
            "answer": answer,
            "summary": self.history_summary(answer),
            "camera_backend_used": result.camera_backend_used or "",
            "camera_resolution": list(result.camera_resolution) if result.camera_resolution else [],
            "model_used": result.model_used or "",
            "duration_seconds": result.duration_seconds,
            "retry_status": result.retry_status or "",
            "error_summary": result.error_summary or "",
        }
        history_entries.insert(0, history_entry)
        self.write_entries(history_entries)
        return history_entry

    def delete_entry(self, entry_id: str) -> bool:
        """Delete a single history entry and return True when one was removed."""
        normalized_entry_id = str(entry_id).strip()
        if not normalized_entry_id:
            return False
        existing_entries = self.load_entries()
        filtered_entries = [
            entry
            for entry in existing_entries
            if str(entry.get("id", "")).strip() != normalized_entry_id
        ]
        if len(filtered_entries) == len(existing_entries):
            return False
        self.write_entries(filtered_entries)
        return True

    def clear(self) -> None:
        """Remove every persisted history entry."""
        self.write_entries([])

    def invalidate_cache(self) -> None:
        """Forget the in-memory snapshot so the next load re-reads disk."""
        with self._lock:
            self._cache = None
            self._last_load_status = "empty"
            self._last_load_message = ""

    def get_entry(self, entry_id: str) -> dict[str, Any] | None:
        """Return a single saved result history entry by identifier."""
        for entry in self.load_entries():
            if entry.get("id") == entry_id:
                return entry
        return None

    def coerce_entry(self, raw_entry: Any) -> dict[str, Any] | None:
        """Validate the stored history payload shape."""
        if not isinstance(raw_entry, dict):
            return None

        entry_id = str(raw_entry.get("id", "")).strip()
        answer = str(raw_entry.get("answer", "")).strip()
        if not entry_id or not answer:
            return None

        selected_mode, selected_mode_internal = self.resolve_mode_pair(
            raw_entry.get("selected_mode", ""),
            raw_entry.get("selected_mode_internal", ""),
        )
        mode_label = str(raw_entry.get("mode_label", "")).strip() or self.mode_label_resolver(
            selected_mode,
            selected_mode_internal,
        )
        summary = str(raw_entry.get("summary", "")).strip() or self.history_summary(answer)

        raw_resolution = raw_entry.get("camera_resolution", [])
        camera_resolution: list[int] = []
        if (
            isinstance(raw_resolution, (list, tuple))
            and len(raw_resolution) == 2
            and all(isinstance(value, (int, float)) for value in raw_resolution)
        ):
            camera_resolution = [int(raw_resolution[0]), int(raw_resolution[1])]

        return {
            "id": entry_id,
            "created_at": str(raw_entry.get("created_at", "")),
            "selected_mode": selected_mode,
            "selected_mode_internal": selected_mode_internal,
            "mode_label": mode_label,
            "status": str(raw_entry.get("status", "success")).strip() or "success",
            "answer": answer,
            "summary": summary,
            "camera_backend_used": str(raw_entry.get("camera_backend_used", "")),
            "camera_resolution": camera_resolution,
            "model_used": str(raw_entry.get("model_used", "")).strip(),
            "duration_seconds": self.coerce_optional_float(raw_entry.get("duration_seconds")),
            "retry_status": str(raw_entry.get("retry_status", "")).strip(),
            "error_summary": str(raw_entry.get("error_summary", "")).strip(),
        }

    def decorate_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Add non-persisted fields used by UI renderers."""
        decorated_entry = entry.copy()
        decorated_entry["has_thumbnail"] = False
        decorated_entry["has_reanalyze_assets"] = False
        decorated_entry["thumbnail_data_url"] = ""
        return decorated_entry

    def decorate_entries(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Decorate a full list of persisted history entries for UI rendering."""
        return [self.decorate_entry(entry) for entry in entries]

    def history_entry_camera_resolution(self, entry: dict[str, Any]) -> tuple[int, int] | None:
        """Return the saved capture resolution for a history entry when available."""
        raw_resolution = entry.get("camera_resolution", [])
        if (
            isinstance(raw_resolution, (list, tuple))
            and len(raw_resolution) == 2
            and all(isinstance(value, (int, float)) for value in raw_resolution)
        ):
            return (int(raw_resolution[0]), int(raw_resolution[1]))
        return None

    def history_summary(self, answer: str, max_chars: int = 160) -> str:
        """Return a compact one-line summary for a result-history list entry."""
        cleaned = " ".join(answer.split())
        if len(cleaned) <= max_chars:
            return cleaned
        return cleaned[: max_chars - 3].rstrip() + "..."

    def apply_retention(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Trim history entries by age and configured item count."""
        retained: list[dict[str, Any]] = []
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        for entry in entries:
            created_at = self.parse_timestamp(str(entry.get("created_at", "")))
            if created_at is not None and created_at < cutoff:
                continue
            retained.append(entry)
            if len(retained) >= self.result_limit:
                break
        return retained

    @staticmethod
    def coerce_optional_float(value: Any) -> float | None:
        """Return a float value when the history payload contains one."""
        if value in {None, ""}:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def parse_timestamp(value: str) -> datetime | None:
        """Parse an ISO timestamp from persisted UI/history payloads."""
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _build_snapshot(
        entries: list[dict[str, Any]],
        *,
        status: str,
        message: str = "",
    ) -> dict[str, Any]:
        resolved_status = status
        if resolved_status == "ok" and not entries:
            resolved_status = "empty"
        return {
            "status": resolved_status,
            "message": str(message or ""),
            "entries": [entry.copy() for entry in entries],
        }
