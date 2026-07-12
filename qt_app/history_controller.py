"""History workflow controller for the native Qt frontend."""

from __future__ import annotations

import logging
import threading
from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot

from qt_app.models import DictListModel
from qt_app.runtime import VisionDeskRuntime
from system.ui_presenters import (
    build_result_detail_view,
    build_result_view,
    format_result_duration,
)

LOGGER = logging.getLogger(__name__)


class HistoryController(QObject):
    """Load, present, and mutate saved text-only result history for QML."""

    stateChanged = Signal()
    screenRequested = Signal(str)
    deleteAllDataCompleted = Signal(str)
    workerFinished = Signal(object)

    def __init__(self, runtime: VisionDeskRuntime, parent=None) -> None:
        super().__init__(parent)
        self.runtime = runtime
        self._history_entries_model = DictListModel(
            [
                "id",
                "created_at",
                "mode_label",
                "summary",
                "status",
                "model_used",
                "duration_seconds",
                "retry_status",
                "error_summary",
            ],
            self,
        )
        self._history_state = "loading"
        self._history_message = "Loading recent results..."
        self._selected_entry: dict[str, Any] | None = None
        self._selected_title = ""
        self._selected_note = ""
        self._selected_result_html = ""
        self._selected_detail_html = ""
        self._entry_lookup: dict[str, dict[str, Any]] = {}
        self._worker_running = False
        self.workerFinished.connect(self._handle_worker_finished)

    @Property(QObject, constant=True)
    def historyEntriesModel(self) -> DictListModel:
        return self._history_entries_model

    @Property(str, notify=stateChanged)
    def historyState(self) -> str:
        return self._history_state

    @Property(str, notify=stateChanged)
    def historyMessage(self) -> str:
        return self._history_message

    @Property(bool, notify=stateChanged)
    def hasSelectedHistoryItem(self) -> bool:
        return self._selected_entry is not None

    @Property(str, notify=stateChanged)
    def selectedHistoryId(self) -> str:
        return str((self._selected_entry or {}).get("id", ""))

    @Property(str, notify=stateChanged)
    def selectedHistoryCreatedAt(self) -> str:
        return str((self._selected_entry or {}).get("created_at", ""))

    @Property(str, notify=stateChanged)
    def selectedHistoryModeLabel(self) -> str:
        return str((self._selected_entry or {}).get("mode_label", ""))

    @Property(str, notify=stateChanged)
    def selectedHistoryStatus(self) -> str:
        return str((self._selected_entry or {}).get("status", ""))

    @Property(str, notify=stateChanged)
    def selectedHistoryStatusLabel(self) -> str:
        return self._humanize_text((self._selected_entry or {}).get("status", ""))

    @Property(str, notify=stateChanged)
    def selectedHistoryModelUsed(self) -> str:
        return str((self._selected_entry or {}).get("model_used", ""))

    @Property(str, notify=stateChanged)
    def selectedHistoryDurationLabel(self) -> str:
        return format_result_duration((self._selected_entry or {}).get("duration_seconds"))

    @Property(str, notify=stateChanged)
    def selectedHistoryRetryStatus(self) -> str:
        return self._humanize_text((self._selected_entry or {}).get("retry_status", ""))

    @Property(str, notify=stateChanged)
    def selectedHistoryErrorSummary(self) -> str:
        return str((self._selected_entry or {}).get("error_summary", ""))

    @Property(str, notify=stateChanged)
    def selectedHistoryTitle(self) -> str:
        return self._selected_title

    @Property(str, notify=stateChanged)
    def selectedHistoryNote(self) -> str:
        return self._selected_note

    @Property(str, notify=stateChanged)
    def selectedHistoryResultHtml(self) -> str:
        return self._selected_result_html

    @Property(str, notify=stateChanged)
    def selectedHistoryDetailHtml(self) -> str:
        return self._selected_detail_html

    @Slot()
    def reloadHistory(self) -> None:
        self._set_history_state("loading", "Loading recent results...")
        self._run_in_thread(self._load_snapshot_worker, "history-reload")

    @Slot()
    def openHistory(self) -> None:
        self._clear_selected_entry()
        self.screenRequested.emit("history")
        self.reloadHistory()

    @Slot(str)
    def openHistoryItem(self, entry_id: str) -> None:
        entry = self._entry_lookup.get(str(entry_id).strip())
        if entry is None:
            self.reloadHistory()
            return
        self._select_entry(entry)
        self.screenRequested.emit("history_detail")

    @Slot(str)
    def deleteHistoryItem(self, entry_id: str) -> None:
        normalized_entry_id = str(entry_id).strip()
        if not normalized_entry_id:
            return
        self._set_history_state("loading", "Deleting saved result...")
        self._run_in_thread(
            lambda: self._delete_history_item_worker(normalized_entry_id),
            "history-delete-item",
        )

    @Slot()
    def clearHistory(self) -> None:
        self._set_history_state("loading", "Clearing recent results...")
        self._run_in_thread(self._clear_history_worker, "history-clear")

    @Slot()
    def deleteAllData(self) -> None:
        self._set_history_state("loading", "Deleting local data...")
        self._run_in_thread(self._delete_all_data_worker, "history-delete-all")

    @Slot()
    def goBack(self) -> None:
        if self._selected_entry is not None:
            self._clear_selected_entry()
            self.screenRequested.emit("history")
            return
        self.screenRequested.emit("home")

    def _run_in_thread(self, target, name: str) -> None:
        if self._worker_running:
            return
        self._worker_running = True
        worker = threading.Thread(target=self._wrap_worker(target), daemon=True, name=name)
        worker.start()

    def _wrap_worker(self, target):
        def _worker() -> None:
            try:
                target()
            except Exception as exc:  # pragma: no cover - defensive logging path
                LOGGER.exception("History worker failed")
                self.workerFinished.emit(
                    {
                        "kind": "error",
                        "state": "error",
                        "message": f"History operation failed: {exc}",
                    }
                )

        return _worker

    def _load_snapshot_worker(self) -> None:
        self.runtime.result_history_store.invalidate_cache()
        snapshot = self.runtime.result_history_store.load_snapshot()
        self.workerFinished.emit({"kind": "snapshot", "snapshot": snapshot})

    def _delete_history_item_worker(self, entry_id: str) -> None:
        deleted = self.runtime.result_history_store.delete_entry(entry_id)
        snapshot = self.runtime.result_history_store.load_snapshot()
        self.workerFinished.emit(
            {
                "kind": "delete_item",
                "entry_id": entry_id,
                "deleted": deleted,
                "snapshot": snapshot,
            }
        )

    def _clear_history_worker(self) -> None:
        self.runtime.result_history_store.clear()
        snapshot = self.runtime.result_history_store.load_snapshot()
        self.workerFinished.emit({"kind": "clear_history", "snapshot": snapshot})

    def _delete_all_data_worker(self) -> None:
        self.runtime.delete_all_user_data()
        self.workerFinished.emit(
            {
                "kind": "delete_all_data",
                "message": "All local data deleted. Device is ready for a new capture.",
            }
        )

    def _handle_worker_finished(self, payload: dict[str, Any]) -> None:
        self._worker_running = False
        kind = str(payload.get("kind", "")).strip()
        if kind == "snapshot":
            self._apply_snapshot(payload.get("snapshot", {}))
            return
        if kind == "delete_item":
            snapshot = payload.get("snapshot", {})
            self._apply_snapshot(snapshot)
            if str(payload.get("entry_id", "")) == self.selectedHistoryId:
                self._clear_selected_entry()
                self.screenRequested.emit("history")
            return
        if kind == "clear_history":
            self._clear_selected_entry()
            self._apply_snapshot(payload.get("snapshot", {}))
            self.screenRequested.emit("history")
            return
        if kind == "delete_all_data":
            self._clear_selected_entry()
            self._history_entries_model.clear()
            self._entry_lookup = {}
            self._set_history_state("empty", "No saved results yet.")
            self.deleteAllDataCompleted.emit(
                str(payload.get("message", "All local data deleted. Device is ready."))
            )
            return
        self._set_history_state(
            str(payload.get("state", "error")).strip() or "error",
            str(payload.get("message", "History is unavailable right now.")).strip(),
        )

    def _apply_snapshot(self, snapshot: dict[str, Any]) -> None:
        raw_entries = snapshot.get("entries", [])
        entries = raw_entries if isinstance(raw_entries, list) else []
        safe_entries = [self._safe_list_item(entry) for entry in entries]
        self._history_entries_model.set_items(safe_entries)
        self._entry_lookup = {
            str(entry.get("id", "")).strip(): entry.copy()
            for entry in entries
            if str(entry.get("id", "")).strip()
        }
        snapshot_status = str(snapshot.get("status", "ok")).strip().lower() or "ok"
        snapshot_message = str(snapshot.get("message", "")).strip()
        state = snapshot_status
        message = snapshot_message
        if snapshot_status == "ok":
            state = "ready"
            message = snapshot_message or ""
        elif snapshot_status == "empty":
            state = "empty"
            message = snapshot_message or "No saved results yet."
        elif snapshot_status == "recovered":
            state = "recovered"
            message = snapshot_message or "Corrupted result history was reset."
        elif snapshot_status == "error":
            state = "error"
            message = snapshot_message or "Result history could not be loaded."
        self._set_history_state(state, message)
        if self._selected_entry is not None:
            refreshed_entry = self._entry_lookup.get(self.selectedHistoryId)
            if refreshed_entry is None:
                self._clear_selected_entry()
            else:
                self._select_entry(refreshed_entry)

    def _safe_list_item(self, entry: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(entry.get("id", "")).strip(),
            "created_at": str(entry.get("created_at", "")).strip(),
            "mode_label": str(entry.get("mode_label", "")).strip(),
            "summary": str(entry.get("summary", "")).strip(),
            "status": str(entry.get("status", "")).strip(),
            "model_used": str(entry.get("model_used", "")).strip(),
            "duration_seconds": entry.get("duration_seconds"),
            "retry_status": str(entry.get("retry_status", "")).strip(),
            "error_summary": str(entry.get("error_summary", "")).strip(),
        }

    def _select_entry(self, entry: dict[str, Any]) -> None:
        self._selected_entry = entry.copy()
        selected_mode = str(entry.get("selected_mode", "")).strip()
        mode_label = str(entry.get("mode_label", "")).strip()
        error_text = str(entry.get("error_summary", "")).strip()
        result_view = build_result_view(
            selected_mode,
            selected_mode_label=mode_label,
            status=str(entry.get("status", "")),
            answer_text=str(entry.get("answer", "")),
            error_text=error_text,
            default_capture_mode=self.runtime.default_capture_mode,
        )
        detail_view = build_result_detail_view(
            selected_mode=selected_mode,
            answer_text=str(entry.get("answer", "")),
            result_state=str(result_view.get("state", "")),
            detail_text="",
            error_text=error_text,
            latest_result_path=None,
            history_entry=entry,
            history_entry_camera_resolution=self.runtime.result_history_store.history_entry_camera_resolution,
        )
        self._selected_title = str(result_view.get("title", "Result"))
        self._selected_note = str(result_view.get("note", ""))
        self._selected_result_html = str(result_view.get("body_html", ""))
        self._selected_detail_html = str(detail_view.get("body_html", ""))
        self.stateChanged.emit()

    def _clear_selected_entry(self) -> None:
        if self._selected_entry is None and not any(
            (
                self._selected_title,
                self._selected_note,
                self._selected_result_html,
                self._selected_detail_html,
            )
        ):
            return
        self._selected_entry = None
        self._selected_title = ""
        self._selected_note = ""
        self._selected_result_html = ""
        self._selected_detail_html = ""
        self.stateChanged.emit()

    def _set_history_state(self, state: str, message: str) -> None:
        next_state = str(state or "ready").strip().lower() or "ready"
        next_message = str(message or "")
        if next_state == self._history_state and next_message == self._history_message:
            return
        self._history_state = next_state
        self._history_message = next_message
        self.stateChanged.emit()

    @staticmethod
    def _humanize_text(value: Any) -> str:
        return str(value or "").strip().replace("_", " ").title()
