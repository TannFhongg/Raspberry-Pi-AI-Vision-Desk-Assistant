"""Result-state QObject exposed to the Qt Quick result screen."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Property, Signal


class ResultStateModel(QObject):
    """Singleton-style QObject holding the active answer/result payload."""

    resultTitleChanged = Signal()
    resultStateChanged = Signal()
    resultPlainTextChanged = Signal()
    resultHtmlChanged = Signal()
    resultNoteChanged = Signal()
    detailHtmlChanged = Signal()
    detailVisibleChanged = Signal()
    previewRevisionChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._result_title = "Result"
        self._result_state = "NO_RESULT"
        self._result_plain_text = ""
        self._result_html = ""
        self._result_note = ""
        self._detail_html = ""
        self._detail_visible = False
        self._preview_revision = 0

    def update(self, **changes: Any) -> None:
        """Apply a partial result update and emit changed signals."""
        for key, value in changes.items():
            if key == "result_title" and value != self._result_title:
                self._result_title = str(value)
                self.resultTitleChanged.emit()
            elif key == "result_state" and value != self._result_state:
                self._result_state = str(value)
                self.resultStateChanged.emit()
            elif key == "result_plain_text" and value != self._result_plain_text:
                self._result_plain_text = str(value)
                self.resultPlainTextChanged.emit()
            elif key == "result_html" and value != self._result_html:
                self._result_html = str(value)
                self.resultHtmlChanged.emit()
            elif key == "result_note" and value != self._result_note:
                self._result_note = str(value)
                self.resultNoteChanged.emit()
            elif key == "detail_html" and value != self._detail_html:
                self._detail_html = str(value)
                self.detailHtmlChanged.emit()
            elif key == "detail_visible" and bool(value) != self._detail_visible:
                self._detail_visible = bool(value)
                self.detailVisibleChanged.emit()
            elif key == "preview_revision" and int(value) != self._preview_revision:
                self._preview_revision = int(value)
                self.previewRevisionChanged.emit()

    @Property(str, notify=resultTitleChanged)
    def resultTitle(self) -> str:
        return self._result_title

    @Property(str, notify=resultStateChanged)
    def resultState(self) -> str:
        return self._result_state

    @Property(str, notify=resultPlainTextChanged)
    def resultPlainText(self) -> str:
        return self._result_plain_text

    @Property(str, notify=resultHtmlChanged)
    def resultHtml(self) -> str:
        return self._result_html

    @Property(str, notify=resultNoteChanged)
    def resultNote(self) -> str:
        return self._result_note

    @Property(str, notify=detailHtmlChanged)
    def detailHtml(self) -> str:
        return self._detail_html

    @Property(bool, notify=detailVisibleChanged)
    def detailVisible(self) -> bool:
        return self._detail_visible

    @Property(int, notify=previewRevisionChanged)
    def previewRevision(self) -> int:
        return self._preview_revision

