"""Application-level QObject state exposed to the Qt Quick shell."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Property, Signal


class ApplicationStateModel(QObject):
    """Singleton-style QObject holding the active workflow/navigation state."""

    currentScreenChanged = Signal()
    applicationStateChanged = Signal()
    selectedModeChanged = Signal()
    selectedModeLabelChanged = Signal()
    displayStatusChanged = Signal()
    errorTitleChanged = Signal()
    errorDetailChanged = Signal()
    errorMessageChanged = Signal()
    errorCodeChanged = Signal()
    canRetryChanged = Signal()
    setupReadyToFinishChanged = Signal()
    updatedAtChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_screen = "home"
        self._application_state = "STARTING"
        self._selected_mode = ""
        self._selected_mode_label = ""
        self._display_status = ""
        self._error_title = ""
        self._error_detail = ""
        self._error_message = ""
        self._error_code = ""
        self._can_retry = False
        self._setup_ready_to_finish = False
        self._updated_at = ""

    def update(self, **changes: Any) -> None:
        """Apply a partial state update and emit only changed signals."""
        for key, value in changes.items():
            if key == "current_screen" and value != self._current_screen:
                self._current_screen = str(value)
                self.currentScreenChanged.emit()
            elif key == "application_state" and value != self._application_state:
                self._application_state = str(value)
                self.applicationStateChanged.emit()
            elif key == "selected_mode" and value != self._selected_mode:
                self._selected_mode = str(value)
                self.selectedModeChanged.emit()
            elif key == "selected_mode_label" and value != self._selected_mode_label:
                self._selected_mode_label = str(value)
                self.selectedModeLabelChanged.emit()
            elif key == "display_status" and value != self._display_status:
                self._display_status = str(value)
                self.displayStatusChanged.emit()
            elif key == "error_title" and value != self._error_title:
                self._error_title = str(value)
                self.errorTitleChanged.emit()
            elif key == "error_detail" and value != self._error_detail:
                self._error_detail = str(value)
                self.errorDetailChanged.emit()
            elif key == "error_message" and value != self._error_message:
                self._error_message = str(value)
                self.errorMessageChanged.emit()
            elif key == "error_code" and value != self._error_code:
                self._error_code = str(value)
                self.errorCodeChanged.emit()
            elif key == "can_retry" and bool(value) != self._can_retry:
                self._can_retry = bool(value)
                self.canRetryChanged.emit()
            elif key == "setup_ready_to_finish" and bool(value) != self._setup_ready_to_finish:
                self._setup_ready_to_finish = bool(value)
                self.setupReadyToFinishChanged.emit()
            elif key == "updated_at" and value != self._updated_at:
                self._updated_at = str(value)
                self.updatedAtChanged.emit()

    @Property(str, notify=currentScreenChanged)
    def currentScreen(self) -> str:
        return self._current_screen

    @Property(str, notify=applicationStateChanged)
    def applicationState(self) -> str:
        return self._application_state

    @Property(str, notify=selectedModeChanged)
    def selectedMode(self) -> str:
        return self._selected_mode

    @Property(str, notify=selectedModeLabelChanged)
    def selectedModeLabel(self) -> str:
        return self._selected_mode_label

    @Property(str, notify=displayStatusChanged)
    def displayStatus(self) -> str:
        return self._display_status

    @Property(str, notify=errorTitleChanged)
    def errorTitle(self) -> str:
        return self._error_title

    @Property(str, notify=errorDetailChanged)
    def errorDetail(self) -> str:
        return self._error_detail

    @Property(str, notify=errorMessageChanged)
    def errorMessage(self) -> str:
        return self._error_message

    @Property(str, notify=errorCodeChanged)
    def errorCode(self) -> str:
        return self._error_code

    @Property(bool, notify=canRetryChanged)
    def canRetry(self) -> bool:
        return self._can_retry

    @Property(bool, notify=setupReadyToFinishChanged)
    def setupReadyToFinish(self) -> bool:
        return self._setup_ready_to_finish

    @Property(str, notify=updatedAtChanged)
    def updatedAt(self) -> str:
        return self._updated_at
