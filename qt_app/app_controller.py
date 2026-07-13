"""Main Qt facade exposed to QML as the VisionDesk native app controller."""

from __future__ import annotations

import threading
from typing import Any

from PySide6.QtCore import QObject, Property, QCoreApplication, QDateTime, QTimer, Qt, Signal, Slot

from hardware import DeviceState, clear_latest_result_file
from qt_app.camera_controller import CameraController
from qt_app.gpio_controller import GPIOController
from qt_app.health_controller import HealthController
from qt_app.history_controller import HistoryController
from qt_app.image_provider import CachedImageStore
from qt_app.models import ApplicationStateModel, DictListModel, ResultStateModel
from qt_app.navigation_controller import NavigationController
from qt_app.pipeline_controller import PipelineController
from qt_app.runtime import VisionDeskRuntime
from qt_app.setup_controller import SetupController
from system.factory_reset import (
    CONFIGURATION_RESET,
    FULL_FACTORY_RESET,
    USER_DATA_RESET,
    perform_factory_reset,
)
from system.ui_catalog import MODE_SELECTED_DETAIL, READY_DETAIL, UI_MODE_OPTIONS
from system.ui_presenters import build_processing_view, build_result_detail_view, build_result_view


class AppController(QObject):
    """Single QML-facing facade for navigation, setup, camera, and results."""

    currentScreenChanged = Signal()
    applicationStateChanged = Signal()
    selectedModeChanged = Signal()
    selectedModeLabelChanged = Signal()
    displayStatusChanged = Signal()
    resultTitleChanged = Signal()
    resultStateChanged = Signal()
    resultPlainTextChanged = Signal()
    resultHtmlChanged = Signal()
    errorTitleChanged = Signal()
    errorDetailChanged = Signal()
    setupReadyToFinishChanged = Signal()
    viewStateChanged = Signal()
    deviceActionsChanged = Signal()
    factoryResetWorkerFinished = Signal()

    def __init__(
        self,
        runtime: VisionDeskRuntime,
        *,
        camera_store: CachedImageStore,
        result_store: CachedImageStore,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.runtime = runtime
        self._application_state_model = ApplicationStateModel(self)
        self._result_state_model = ResultStateModel(self)
        self._selected_mode_internal = ""
        self._processing_view: dict[str, str] = {
            "title": "Processing",
            "subtitle": "",
            "mode_label": "",
            "status_message": "",
            "status_tone": "active",
        }
        self._mode_cards_model = DictListModel(["id", "name", "description"], self)
        self._mode_cards_model.set_items(list(UI_MODE_OPTIONS))
        self._camera_store = camera_store
        self._result_store = result_store
        self._device_actions_busy = False
        self._device_actions_status = ""
        self._device_actions_tone = "neutral"
        self._factory_reset_result = None
        self._factory_reset_error = ""
        self.factoryResetWorkerFinished.connect(self._handle_factory_reset_worker_finished)

        self.camera_controller = CameraController(runtime, image_store=camera_store, parent=self)
        self.pipeline_controller = PipelineController(runtime, result_image_store=result_store, parent=self)
        self.setup_controller = SetupController(runtime, parent=self)
        self.history_controller = HistoryController(runtime, parent=self)
        self.health_controller = HealthController(
            runtime,
            camera_controller=self.camera_controller,
            ui_state_provider=self._ui_state_snapshot,
            busy_provider=self.isBackendBusy,
            parent=self,
        )
        self.gpio_controller = GPIOController(runtime, get_device_state=self.currentDeviceState, parent=self)

        self._wire_model_notifications()
        self._wire_controller_notifications()
        self._bootstrap_initial_state()

    @Property(QObject, constant=True)
    def modeCardsModel(self) -> DictListModel:
        return self._mode_cards_model

    @Property(QObject, constant=True)
    def progressStepsModel(self) -> DictListModel:
        return self.pipeline_controller.progressStepsModel

    @Property(QObject, constant=True)
    def healthMetricsModel(self) -> DictListModel:
        return self.health_controller.metricsModel

    @Property(QObject, constant=True)
    def cameraAnalysisModel(self) -> DictListModel:
        return self.health_controller.cameraAnalysisModel

    @Property(QObject, constant=True)
    def wifiNetworksModel(self) -> DictListModel:
        return self.setup_controller.wifiNetworksModel

    @Property(QObject, constant=True)
    def gpioRequirementsModel(self) -> DictListModel:
        return self.setup_controller.gpioRequirementsModel

    @Property(QObject, constant=True)
    def deviceChecksModel(self) -> DictListModel:
        return self.setup_controller.deviceChecksModel

    @Property(QObject, constant=True)
    def historyEntriesModel(self) -> DictListModel:
        return self.history_controller.historyEntriesModel

    @Property(QObject, constant=True)
    def applicationStateModel(self) -> ApplicationStateModel:
        return self._application_state_model

    @Property(QObject, constant=True)
    def resultStateModel(self) -> ResultStateModel:
        return self._result_state_model

    @Property(QObject, constant=True)
    def healthStateModel(self):
        return self.health_controller.stateModel

    @Property(str, notify=currentScreenChanged)
    def currentScreen(self) -> str:
        return self._application_state_model.currentScreen

    @Property(str, notify=applicationStateChanged)
    def applicationState(self) -> str:
        return self._application_state_model.applicationState

    @Property(str, notify=selectedModeChanged)
    def selectedMode(self) -> str:
        return self._application_state_model.selectedMode

    @Property(str, notify=selectedModeLabelChanged)
    def selectedModeLabel(self) -> str:
        return self._application_state_model.selectedModeLabel

    @Property(str, notify=displayStatusChanged)
    def displayStatus(self) -> str:
        return self._application_state_model.displayStatus

    @Property(str, notify=resultTitleChanged)
    def resultTitle(self) -> str:
        return self._result_state_model.resultTitle

    @Property(str, notify=resultStateChanged)
    def resultState(self) -> str:
        return self._result_state_model.resultState

    @Property(str, notify=resultPlainTextChanged)
    def resultPlainText(self) -> str:
        return self._result_state_model.resultPlainText

    @Property(str, notify=resultHtmlChanged)
    def resultHtml(self) -> str:
        return self._result_state_model.resultHtml

    @Property(str, notify=errorTitleChanged)
    def errorTitle(self) -> str:
        return self._application_state_model.errorTitle

    @Property(str, notify=errorDetailChanged)
    def errorDetail(self) -> str:
        return self._application_state_model.errorDetail

    @Property(bool, notify=setupReadyToFinishChanged)
    def setupReadyToFinish(self) -> bool:
        return self._application_state_model.setupReadyToFinish

    @Property(int, notify=viewStateChanged)
    def cameraPreviewRevision(self) -> int:
        return self.camera_controller.previewRevision

    @Property(bool, notify=viewStateChanged)
    def cameraPreviewAvailable(self) -> bool:
        return self.camera_controller.previewAvailable

    @Property(str, notify=viewStateChanged)
    def cameraPreviewState(self) -> str:
        return self.health_controller.stateModel.cameraPreviewState

    @Property(str, notify=viewStateChanged)
    def cameraPreviewTitle(self) -> str:
        return self.health_controller.stateModel.cameraPreviewTitle

    @Property(str, notify=viewStateChanged)
    def cameraPreviewMessage(self) -> str:
        return self.health_controller.stateModel.cameraPreviewMessage

    @Property(str, notify=viewStateChanged)
    def processingTitle(self) -> str:
        return self._processing_view.get("title", "Processing")

    @Property(str, notify=viewStateChanged)
    def processingSubtitle(self) -> str:
        return self._processing_view.get("subtitle", "")

    @Property(str, notify=viewStateChanged)
    def processingModeLabel(self) -> str:
        return self._processing_view.get("mode_label", "")

    @Property(str, notify=viewStateChanged)
    def processingStatusMessage(self) -> str:
        return self._processing_view.get("status_message", "")

    @Property(str, notify=viewStateChanged)
    def processingStatusTone(self) -> str:
        return self._processing_view.get("status_tone", "active")

    @Property(str, notify=viewStateChanged)
    def resultNote(self) -> str:
        return self._result_state_model.resultNote

    @Property(str, notify=viewStateChanged)
    def resultDetailHtml(self) -> str:
        return self._result_state_model.detailHtml

    @Property(bool, notify=viewStateChanged)
    def resultDetailVisible(self) -> bool:
        return self._result_state_model.detailVisible

    @Property(int, notify=viewStateChanged)
    def resultPreviewRevision(self) -> int:
        return self._result_state_model.previewRevision

    @Property(str, notify=viewStateChanged)
    def setupCurrentStep(self) -> str:
        return self.setup_controller.currentStep

    @Property(str, notify=viewStateChanged)
    def setupFinishMessage(self) -> str:
        return self.setup_controller.finishMessage

    @Property(str, notify=viewStateChanged)
    def setupWarningsText(self) -> str:
        return self.setup_controller.warningsText

    @Property(str, notify=viewStateChanged)
    def setupMaskedOpenAiKey(self) -> str:
        return self.setup_controller.maskedOpenAiKey

    @Property(str, notify=viewStateChanged)
    def setupMaskedApiKey(self) -> str:
        return self.setup_controller.maskedApiKey

    @Property(bool, notify=viewStateChanged)
    def setupHasApiKey(self) -> bool:
        return self.setup_controller.hasApiKey

    @Property(bool, notify=viewStateChanged)
    def setupApiKeyVerified(self) -> bool:
        return self.setup_controller.apiKeyVerified

    @Property(str, notify=viewStateChanged)
    def setupDeviceChecksStatus(self) -> str:
        return self.setup_controller.deviceChecksStatus

    @Property(str, notify=viewStateChanged)
    def setupDeviceChecksMessage(self) -> str:
        return self.setup_controller.deviceChecksMessage

    @Property(str, notify=viewStateChanged)
    def setupWifiMessage(self) -> str:
        return self.setup_controller.wifiMessage

    @Property(str, notify=viewStateChanged)
    def setupWifiScanStatus(self) -> str:
        return self.setup_controller.wifiScanStatus

    @Property(str, notify=viewStateChanged)
    def setupWifiStatus(self) -> str:
        return self.setup_controller.wifiStatus

    @Property(str, notify=viewStateChanged)
    def setupWifiSsid(self) -> str:
        return self.setup_controller.wifiSsid

    @Property(str, notify=viewStateChanged)
    def setupOpenAiMessage(self) -> str:
        return self.setup_controller.openAiMessage

    @Property(str, notify=viewStateChanged)
    def setupOpenAiStatus(self) -> str:
        return self.setup_controller.openAiStatus

    @Property(str, notify=viewStateChanged)
    def setupCameraMessage(self) -> str:
        return self.setup_controller.cameraMessage

    @Property(str, notify=viewStateChanged)
    def setupCameraStatus(self) -> str:
        return self.setup_controller.cameraStatus

    @Property(str, notify=viewStateChanged)
    def setupCameraAutofocusMode(self) -> str:
        return self.setup_controller.cameraAutofocusMode

    @Property(str, notify=viewStateChanged)
    def setupCameraResolutionLabel(self) -> str:
        return self.setup_controller.cameraResolutionLabel

    @Property(str, notify=viewStateChanged)
    def setupCameraPreviewFpsLabel(self) -> str:
        return self.setup_controller.cameraPreviewFpsLabel

    @Property(str, notify=viewStateChanged)
    def setupCameraExposureLabel(self) -> str:
        return self.setup_controller.cameraExposureLabel

    @Property(str, notify=viewStateChanged)
    def setupGpioMessage(self) -> str:
        return self.setup_controller.gpioMessage

    @Property(str, notify=viewStateChanged)
    def setupGpioStatus(self) -> str:
        return self.setup_controller.gpioStatus

    @Property(bool, notify=viewStateChanged)
    def setupGpioActive(self) -> bool:
        return self.setup_controller.gpioActive

    @Property(bool, notify=deviceActionsChanged)
    def deviceActionsBusy(self) -> bool:
        return self._device_actions_busy

    @Property(str, notify=deviceActionsChanged)
    def deviceActionsStatus(self) -> str:
        return self._device_actions_status

    @Property(str, notify=deviceActionsChanged)
    def deviceActionsTone(self) -> str:
        return self._device_actions_tone

    @Property(str, notify=viewStateChanged)
    def historyState(self) -> str:
        return self.history_controller.historyState

    @Property(str, notify=viewStateChanged)
    def historyMessage(self) -> str:
        return self.history_controller.historyMessage

    @Property(bool, notify=viewStateChanged)
    def hasSelectedHistoryItem(self) -> bool:
        return self.history_controller.hasSelectedHistoryItem

    @Property(str, notify=viewStateChanged)
    def selectedHistoryId(self) -> str:
        return self.history_controller.selectedHistoryId

    @Property(str, notify=viewStateChanged)
    def selectedHistoryCreatedAt(self) -> str:
        return self.history_controller.selectedHistoryCreatedAt

    @Property(str, notify=viewStateChanged)
    def selectedHistoryModeLabel(self) -> str:
        return self.history_controller.selectedHistoryModeLabel

    @Property(str, notify=viewStateChanged)
    def selectedHistoryStatus(self) -> str:
        return self.history_controller.selectedHistoryStatus

    @Property(str, notify=viewStateChanged)
    def selectedHistoryStatusLabel(self) -> str:
        return self.history_controller.selectedHistoryStatusLabel

    @Property(str, notify=viewStateChanged)
    def selectedHistoryModelUsed(self) -> str:
        return self.history_controller.selectedHistoryModelUsed

    @Property(str, notify=viewStateChanged)
    def selectedHistoryDurationLabel(self) -> str:
        return self.history_controller.selectedHistoryDurationLabel

    @Property(str, notify=viewStateChanged)
    def selectedHistoryRetryStatus(self) -> str:
        return self.history_controller.selectedHistoryRetryStatus

    @Property(str, notify=viewStateChanged)
    def selectedHistoryErrorSummary(self) -> str:
        return self.history_controller.selectedHistoryErrorSummary

    @Property(str, notify=viewStateChanged)
    def selectedHistoryTitle(self) -> str:
        return self.history_controller.selectedHistoryTitle

    @Property(str, notify=viewStateChanged)
    def selectedHistoryNote(self) -> str:
        return self.history_controller.selectedHistoryNote

    @Property(str, notify=viewStateChanged)
    def selectedHistoryResultHtml(self) -> str:
        return self.history_controller.selectedHistoryResultHtml

    @Property(str, notify=viewStateChanged)
    def selectedHistoryDetailHtml(self) -> str:
        return self.history_controller.selectedHistoryDetailHtml

    @Property(int, constant=True)
    def windowWidth(self) -> int:
        return self.runtime.screen_width

    @Property(int, constant=True)
    def windowHeight(self) -> int:
        return self.runtime.screen_height

    @Slot(str)
    def selectMode(self, mode: str) -> None:
        ui_mode, internal_mode = self.runtime.resolve_mode_pair(mode, None)
        if not ui_mode:
            return
        label = self._mode_label(ui_mode)
        self._selected_mode_internal = internal_mode
        self._application_state_model.update(
            selected_mode=ui_mode,
            selected_mode_label=label,
            display_status=MODE_SELECTED_DETAIL,
            updated_at=self.runtime.timestamp(),
        )
        self.openCamera()

    @Slot()
    def openCamera(self) -> None:
        if not self.selectedMode:
            return
        self._set_screen("camera", "CAMERA_PREPARING", MODE_SELECTED_DETAIL)
        self.camera_controller.setActive(True)
        QTimer.singleShot(120, self._mark_camera_ready)

    @Slot()
    def capture(self) -> None:
        if not self.selectedMode or self.pipeline_controller.busy:
            return
        started = self.pipeline_controller.start_capture(
            selected_mode=self.selectedMode,
            selected_mode_internal=self._selected_mode_internal,
        )
        if not started:
            return
        self._refresh_processing_view()
        self._set_screen("processing", "CAPTURING", self.processingStatusMessage or "Capturing image...")

    @Slot()
    def goBack(self) -> None:
        if self.pipeline_controller.busy:
            return
        if self.currentScreen == "setup" and not self.runtime.setup_is_complete():
            return
        if self.currentScreen in {"history", "history_detail"}:
            self.history_controller.goBack()
            return
        self.clearResult()

    @Slot()
    def retry(self) -> None:
        if self.currentScreen == "error" and self.selectedMode:
            self.capture()

    @Slot()
    def clearResult(self) -> None:
        self._reset_result_ui(
            reset_selected_mode=True,
            display_status=READY_DETAIL,
            application_state="READY",
            target_screen="home",
        )

    @Slot()
    def openHistory(self) -> None:
        if self.pipeline_controller.busy:
            return
        self.history_controller.openHistory()

    @Slot()
    def reloadHistory(self) -> None:
        self.history_controller.reloadHistory()

    @Slot(str)
    def openHistoryItem(self, entry_id: str) -> None:
        self.history_controller.openHistoryItem(entry_id)

    @Slot(str)
    def deleteHistoryItem(self, entry_id: str) -> None:
        self.history_controller.deleteHistoryItem(entry_id)

    @Slot()
    def clearHistory(self) -> None:
        self.history_controller.clearHistory()

    @Slot()
    def deleteAllData(self) -> None:
        if self.pipeline_controller.busy:
            return
        self.runFactoryReset(USER_DATA_RESET, False)

    @Slot()
    def runConfigurationReset(self) -> None:
        self.runFactoryReset(CONFIGURATION_RESET, False)

    @Slot(bool)
    def runFullFactoryReset(self, removeWifiProfile: bool = False) -> None:
        self.runFactoryReset(FULL_FACTORY_RESET, removeWifiProfile)

    @Slot(str, bool)
    def runFactoryReset(self, mode: str, removeWifiProfile: bool = False) -> None:
        if self.pipeline_controller.busy or self._device_actions_busy:
            return
        normalized_mode = str(mode or "").strip().lower()
        if normalized_mode not in {CONFIGURATION_RESET, USER_DATA_RESET, FULL_FACTORY_RESET}:
            self._set_device_actions_state(
                busy=False,
                status="Unsupported device reset action.",
                tone="error",
            )
            return

        self._factory_reset_result = None
        self._factory_reset_error = ""
        self._set_device_actions_state(
            busy=True,
            status=self._factory_reset_start_message(normalized_mode, bool(removeWifiProfile)),
            tone="active",
        )
        self.camera_controller.setActive(False)
        self.health_controller.stop()
        self.gpio_controller.stop()
        worker = threading.Thread(
            target=self._run_factory_reset_worker,
            args=(normalized_mode, bool(removeWifiProfile)),
            daemon=True,
            name=f"factory-reset-{normalized_mode}",
        )
        worker.start()

    @Slot()
    def scanWifi(self) -> None:
        self.setup_controller.scanWifi()

    @Slot()
    def runSetupDeviceChecks(self) -> None:
        self.setup_controller.runDeviceChecks()

    @Slot()
    def goToSetupNextStep(self) -> None:
        self.setup_controller.goToNextStep()

    @Slot()
    def goToSetupPreviousStep(self) -> None:
        self.setup_controller.goToPreviousStep()

    @Slot(str)
    def goToSetupStep(self, step: str) -> None:
        self.setup_controller.goToStep(step)

    @Slot(str, str, str)
    def connectWifi(self, selectedSsid: str, manualSsid: str, password: str) -> None:
        self.setup_controller.connectWifi(selectedSsid, manualSsid, password)

    @Slot(str)
    def verifyApiKey(self, apiKey: str) -> None:
        self.setup_controller.verifyApiKey(apiKey)

    @Slot()
    def clearApiKey(self) -> None:
        self.setup_controller.clearApiKey()

    @Slot()
    def runCameraTest(self) -> None:
        self.setup_controller.runCameraTest()

    @Slot()
    def startGpioTest(self) -> None:
        self.setup_controller.startGpioTest()

    @Slot()
    def stopGpioTest(self) -> None:
        self.setup_controller.stopGpioTest()

    @Slot()
    def finishSetup(self) -> None:
        self.setup_controller.finishSetup()

    def currentDeviceState(self) -> str:
        """Return the hardware-facing busy state for GPIO integration."""
        return self._ui_state_snapshot()["device_state"]

    def isBackendBusy(self) -> bool:
        """Return True when capture/pipeline or preview should block intrusive checks."""
        return self.pipeline_controller.busy or self.currentScreen in {"setup", "camera"}

    def shutdown(self) -> None:
        """Stop background controllers and release runtime resources."""
        self.gpio_controller.stop()
        self.setup_controller.close()
        self.camera_controller.close()
        self.pipeline_controller.close()
        self.health_controller.stop()
        self.runtime.shutdown()

    def _bootstrap_initial_state(self) -> None:
        if self.runtime.setup_is_complete():
            self._application_state_model.update(
                current_screen="home",
                application_state="READY",
                display_status=READY_DETAIL,
                updated_at=self.runtime.timestamp(),
            )
            self.health_controller.start()
            self.gpio_controller.start()
            self.runtime.ensure_offline_retry_started(
                analyze_func=self.pipeline_controller.analyze_offline_retry_entry,
                success_callback=self.pipeline_controller.record_offline_retry_success,
                failure_callback=self.pipeline_controller.record_offline_retry_failure,
            )
            return
        self._application_state_model.update(
            current_screen="setup",
            application_state="SETUP_REQUIRED",
            display_status="Finish device setup before using VisionDesk.",
            setup_ready_to_finish=self.setup_controller.readyToFinish,
            updated_at=self.runtime.timestamp(),
        )
        self.camera_controller.setActive(True)
        self.health_controller.start()

    def _wire_model_notifications(self) -> None:
        self._application_state_model.currentScreenChanged.connect(self.currentScreenChanged)
        self._application_state_model.applicationStateChanged.connect(self.applicationStateChanged)
        self._application_state_model.selectedModeChanged.connect(self.selectedModeChanged)
        self._application_state_model.selectedModeLabelChanged.connect(self.selectedModeLabelChanged)
        self._application_state_model.displayStatusChanged.connect(self.displayStatusChanged)
        self._application_state_model.errorTitleChanged.connect(self.errorTitleChanged)
        self._application_state_model.errorDetailChanged.connect(self.errorDetailChanged)
        self._application_state_model.setupReadyToFinishChanged.connect(self.setupReadyToFinishChanged)
        self._result_state_model.resultTitleChanged.connect(self.resultTitleChanged)
        self._result_state_model.resultStateChanged.connect(self.resultStateChanged)
        self._result_state_model.resultPlainTextChanged.connect(self.resultPlainTextChanged)
        self._result_state_model.resultHtmlChanged.connect(self.resultHtmlChanged)

    def _wire_controller_notifications(self) -> None:
        self.pipeline_controller.progressChanged.connect(self._handle_pipeline_progress_changed)
        self.pipeline_controller.payloadReady.connect(self._handle_pipeline_payload)
        self.camera_controller.previewRevisionChanged.connect(self.viewStateChanged)
        self.camera_controller.previewAvailableChanged.connect(self._refresh_health_summary)
        self.camera_controller.previewErrorChanged.connect(self._refresh_health_summary)
        self.health_controller.summaryChanged.connect(self.viewStateChanged)
        self.history_controller.stateChanged.connect(self.viewStateChanged)
        self.history_controller.screenRequested.connect(self._handle_history_screen_requested)
        self.history_controller.deleteAllDataCompleted.connect(self._handle_delete_all_data_completed)
        self.setup_controller.stateChanged.connect(self._handle_setup_state_changed)
        self.setup_controller.setupCompleted.connect(self._handle_setup_completed)
        self.gpio_controller.modeSelected.connect(self.selectMode)
        self.gpio_controller.captureRequested.connect(self.capture)
        self.gpio_controller.backRequested.connect(self.goBack)
        self.gpio_controller.clearRequested.connect(self.clearResult)

    def _handle_pipeline_progress_changed(self) -> None:
        state = self.pipeline_controller.progressState
        status_map = {
            "CAPTURING": "CAPTURING",
            "PREPROCESSING": "PREPROCESSING",
            "ANALYZING": "ANALYZING",
        }
        self._refresh_processing_view()
        self._application_state_model.update(
            application_state=status_map.get(state, self.applicationState),
            display_status=self.processingStatusMessage,
            updated_at=self.runtime.timestamp(),
        )
        self.viewStateChanged.emit()
        self._refresh_health_summary()

    def _handle_pipeline_payload(self, payload: dict[str, Any]) -> None:
        kind = payload.get("kind")
        if kind == "success":
            result = payload["result"]
            self._present_result(
                status="Answer Ready",
                answer_text=result.answer or "",
                error_text="",
                history_entry=payload.get("history_entry"),
                application_state="DONE",
            )
            return
        if kind == "queued":
            result = payload["result"]
            self._present_result(
                status="Queued for retry",
                answer_text=result.answer or "",
                error_text=payload.get("technical_error", ""),
                history_entry=payload.get("history_entry"),
                application_state="RETRY_QUEUED",
            )
            return
        self._application_state_model.update(
            error_title=payload.get("friendly_error", "Analysis failed"),
            error_detail=payload.get("technical_error", ""),
            display_status="Try again when ready",
            updated_at=self.runtime.timestamp(),
        )
        self._set_screen("error", "ERROR", "Try again when ready")
        self.viewStateChanged.emit()
        self._refresh_health_summary()

    def _handle_setup_state_changed(self) -> None:
        self._application_state_model.update(
            setup_ready_to_finish=self.setup_controller.readyToFinish,
            updated_at=self.runtime.timestamp(),
        )
        self.viewStateChanged.emit()
        self._refresh_health_summary()

    def _handle_setup_completed(self, completion_timestamp: str) -> None:
        del completion_timestamp
        self.gpio_controller.restart_if_needed()
        QCoreApplication.quit()

    def _handle_history_screen_requested(self, screen: str) -> None:
        if screen == "history_detail":
            self._set_screen("history_detail", "HISTORY_DETAIL", "Viewing saved result")
            self.viewStateChanged.emit()
            self._refresh_health_summary()
            return
        if screen == "history":
            self._set_screen("history", "HISTORY", "Recent saved results")
            self.viewStateChanged.emit()
            self._refresh_health_summary()
            return
        if screen == "home":
            self._reset_result_ui(
                reset_selected_mode=True,
                display_status=READY_DETAIL,
                application_state="READY",
                target_screen="home",
                write_latest_result_placeholder=False,
            )

    def _handle_delete_all_data_completed(self, message: str) -> None:
        self._reset_result_ui(
            reset_selected_mode=True,
            display_status=message,
            application_state="READY",
            target_screen="home",
            write_latest_result_placeholder=False,
        )

    def _handle_factory_reset_worker_finished(self) -> None:
        summary = self._factory_reset_result
        error_message = self._factory_reset_error
        self._factory_reset_result = None
        self._factory_reset_error = ""

        if error_message:
            self._set_device_actions_state(
                busy=False,
                status=error_message,
                tone="error",
            )
            self.health_controller.start()
            self.gpio_controller.restart_if_needed()
            self._refresh_health_summary()
            return

        if summary is None:
            self._set_device_actions_state(
                busy=False,
                status="Device action finished without a result.",
                tone="error",
            )
            self.health_controller.start()
            self.gpio_controller.restart_if_needed()
            self._refresh_health_summary()
            return

        if summary.mode == USER_DATA_RESET:
            self.runtime.result_history_store.invalidate_cache()
            self.history_controller._clear_selected_entry()
            self.history_controller.historyEntriesModel.clear()
            self.history_controller._entry_lookup = {}
            self.history_controller._set_history_state("empty", "No saved results yet.")
            self._set_device_actions_state(
                busy=False,
                status="All local data deleted. Device is ready for a new capture.",
                tone="success",
            )
            self.health_controller.start()
            self.gpio_controller.restart_if_needed()
            self._handle_delete_all_data_completed(self.deviceActionsStatus)
            return

        self.runtime.mark_setup_incomplete()
        self.runtime.request_restart()
        self._set_device_actions_state(
            busy=False,
            status="Reset complete. Restarting VisionDesk into Setup Wizard...",
            tone="success",
        )
        QCoreApplication.quit()

    def _mark_camera_ready(self) -> None:
        if self.currentScreen == "camera":
            self._application_state_model.update(
                application_state="CAMERA_READY",
                display_status="Live preview ready. Capture when ready.",
                updated_at=self.runtime.timestamp(),
        )
        self.viewStateChanged.emit()
        self._refresh_health_summary()

    def _run_factory_reset_worker(self, mode: str, remove_wifi_profile: bool) -> None:
        try:
            self._factory_reset_result = perform_factory_reset(
                mode=mode,
                paths=self.runtime.paths.to_visiondesk_paths(),
                settings=self.runtime.settings,
                remove_wifi_profile=remove_wifi_profile,
            )
        except Exception as exc:  # pragma: no cover - defensive logging path
            self._factory_reset_error = str(exc)
        self.factoryResetWorkerFinished.emit()

    def _set_device_actions_state(self, *, busy: bool, status: str, tone: str) -> None:
        changed = (
            busy != self._device_actions_busy
            or status != self._device_actions_status
            or tone != self._device_actions_tone
        )
        self._device_actions_busy = busy
        self._device_actions_status = str(status or "")
        self._device_actions_tone = str(tone or "neutral")
        if changed:
            self.deviceActionsChanged.emit()

    @staticmethod
    def _factory_reset_start_message(mode: str, remove_wifi_profile: bool) -> str:
        if mode == CONFIGURATION_RESET:
            return "Resetting configuration and returning to Setup Wizard..."
        if mode == FULL_FACTORY_RESET:
            if remove_wifi_profile:
                return "Running full factory reset and removing the saved Wi-Fi profile..."
            return "Running full factory reset..."
        return "Clearing saved history, retry queue, and private media..."

    def _refresh_processing_view(self) -> None:
        self._processing_view = build_processing_view(
            self.selectedMode,
            selected_mode_label=self.selectedModeLabel,
            progress_state=self.pipeline_controller.progressState,
            detail=self.pipeline_controller.progressMessage,
            error=self.errorTitle,
            default_capture_mode=self.runtime.default_capture_mode,
        )

    def _present_result(
        self,
        *,
        status: str,
        answer_text: str,
        error_text: str,
        history_entry: dict[str, Any] | None,
        application_state: str,
    ) -> None:
        result_view = build_result_view(
            self.selectedMode,
            selected_mode_label=self.selectedModeLabel,
            status=status,
            answer_text=answer_text,
            error_text=error_text,
            default_capture_mode=self.runtime.default_capture_mode,
        )
        detail_view = build_result_detail_view(
            selected_mode=self.selectedMode,
            answer_text=answer_text,
            result_state=result_view["state"],
            detail_text=self.pipeline_controller.progressMessage,
            error_text=error_text,
            latest_result_path=self.runtime.paths.latest_result_path,
            history_entry=history_entry,
            history_entry_camera_resolution=self.runtime.result_history_store.history_entry_camera_resolution,
        )
        self._result_state_model.update(
            result_title=result_view["title"],
            result_state=result_view["state"],
            result_plain_text=result_view["body_text"],
            result_html=str(result_view["body_html"]),
            result_note=result_view["note"],
            detail_html=str(detail_view["body_html"]),
            detail_visible=bool(detail_view["has_content"]),
            preview_revision=self._result_store.revision,
        )
        self._application_state_model.update(
            error_title="",
            error_detail=error_text,
            display_status=status,
            updated_at=self.runtime.timestamp(),
        )
        self._set_screen("result", application_state, status)
        self.viewStateChanged.emit()
        self._refresh_health_summary()

    def _set_screen(self, screen: str, application_state: str, display_status: str) -> None:
        resolved_screen = NavigationController.resolve_render_screen(screen, self.selectedMode)
        self._application_state_model.update(
            current_screen=resolved_screen,
            application_state=application_state,
            display_status=display_status,
            updated_at=self.runtime.timestamp(),
        )
        self.camera_controller.setActive(resolved_screen in {"setup", "camera"})

    def _reset_result_ui(
        self,
        *,
        reset_selected_mode: bool,
        display_status: str,
        application_state: str,
        target_screen: str,
        write_latest_result_placeholder: bool = True,
    ) -> None:
        if write_latest_result_placeholder:
            clear_latest_result_file(
                self.runtime.paths.latest_result_path,
                mode=self._selected_mode_internal or self.selectedMode,
            )
        self._result_store.clear()
        self._result_state_model.update(
            result_title="Result",
            result_state="NO_RESULT",
            result_plain_text="",
            result_html="",
            result_note="",
            detail_html="",
            detail_visible=False,
            preview_revision=self._result_store.revision,
        )
        update_payload: dict[str, Any] = {
            "error_title": "",
            "error_detail": "",
            "display_status": display_status,
            "updated_at": self.runtime.timestamp(),
        }
        if reset_selected_mode:
            update_payload["selected_mode"] = ""
            update_payload["selected_mode_label"] = ""
            self._selected_mode_internal = ""
        self._application_state_model.update(**update_payload)
        self._set_screen(target_screen, application_state, display_status)
        self.viewStateChanged.emit()
        self._refresh_health_summary()

    def _refresh_health_summary(self) -> None:
        self.health_controller.refresh()

    def _mode_label(self, mode: str) -> str:
        for option in UI_MODE_OPTIONS:
            if str(option.get("id")) == mode:
                return str(option.get("name", ""))
        return mode.replace("_", " ").title()

    def _ui_state_snapshot(self) -> dict[str, Any]:
        current_screen = self._application_state_model.currentScreen or "home"
        selected_mode = self._application_state_model.selectedMode
        state_map = {
            "STARTING": DeviceState.READY.value,
            "SETUP_REQUIRED": DeviceState.READY.value,
            "READY": DeviceState.READY.value,
            "MODE_SELECTED": DeviceState.MODE_SELECTED.value,
            "CAMERA_PREPARING": DeviceState.MODE_SELECTED.value,
            "CAMERA_READY": DeviceState.MODE_SELECTED.value,
            "CAPTURING": DeviceState.CAPTURING.value,
            "PREPROCESSING": DeviceState.PROCESSING.value,
            "ANALYZING": DeviceState.PROCESSING.value,
            "RETRY_QUEUED": DeviceState.DONE.value,
            "DONE": DeviceState.DONE.value,
            "ERROR": DeviceState.ERROR.value,
        }
        return {
            "screen": current_screen,
            "device_state": state_map.get(self._application_state_model.applicationState, DeviceState.READY.value),
            "selected_mode": selected_mode,
            "selected_mode_internal": self._selected_mode_internal,
            "updated_at": self._application_state_model.updatedAt
            or QDateTime.currentDateTime().toString(Qt.ISODate),
        }
