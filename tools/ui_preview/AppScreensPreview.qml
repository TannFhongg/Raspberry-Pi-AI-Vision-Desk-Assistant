import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../../qt_app/qml/theme"
import "../../qt_app/qml/components"
import "../../qt_app/qml/screens"

Rectangle {
    id: window
    width: 1200
    height: 800
    color: appTheme.pageBackground

    property string requestedScreen: "home"
    property url outputPath: ""

    function capturePreview() {
        if (!String(window.outputPath || "").length) {
            return
        }
        window.grabToImage(function(result) {
            result.saveToFile(window.outputPath)
            Qt.quit()
        })
    }

    Theme {
        id: appTheme
    }

    QtObject {
        id: mockController

        property string currentScreen: window.requestedScreen
        property string selectedMode: "read_text"
        property string selectedModeLabel: "Read Text"
        property string applicationState: "ANALYZING"
        property string globalStatusText: "Ready"
        property string globalStatusTone: "success"
        property bool deviceActionsBusy: false
        property string deviceActionsStatus: ""
        property string deviceActionsTone: "active"
        property bool cameraPreviewAvailable: false
        property int cameraPreviewRevision: 0
        property string cameraPreviewTitle: "Camera is preparing"
        property string cameraPreviewMessage: "The live preview will appear here as soon as the camera is ready."
        property string processingTitle: "Analyzing Image"
        property string processingSubtitle: "Understanding the captured image"
        property string processingModeLabel: "Read Text"
        property string processingStatusMessage: "Sending the prepared image to AI analysis..."
        property string processingStatusTone: "active"
        property int resultPreviewRevision: 0
        property string resultState: "DONE"
        property string resultTitle: "Extracted Text"
        property string resultNote: "Analysis completed on this device."
        property string resultHtml: "<h3>VisionDesk result</h3><p>The captured page is clear and ready to read. This preview demonstrates readable result content inside the shared scroll card.</p><ul><li>High contrast text detected</li><li>Capture quality is good</li><li>Ready for the next task</li></ul>"
        property bool resultDetailVisible: true
        property string resultDetailHtml: "<p>Camera quality: good.</p><p>Lighting: balanced.</p>"
        property string errorTitle: "The image could not be analyzed"
        property string errorDetail: "VisionDesk could not complete this request. Check the connection and try the capture again."
        property string historyState: "ready"
        property string historyMessage: "Saved results will appear here after a successful capture."
        property bool hasSelectedHistoryItem: true
        property string selectedHistoryModeLabel: "Read Text"
        property string selectedHistoryCreatedAt: "Today, 10:42"
        property string selectedHistoryStatusLabel: "Complete"
        property string selectedHistoryStatus: "done"
        property string selectedHistoryModelUsed: "gpt-4.1-mini"
        property string selectedHistoryDurationLabel: "2.1s"
        property string selectedHistoryRetryStatus: ""
        property string selectedHistoryErrorSummary: ""
        property string selectedHistoryTitle: "Extracted Text"
        property string selectedHistoryNote: "Saved locally on this device."
        property string selectedHistoryResultHtml: "<h3>Document overview</h3><p>VisionDesk extracted the visible text and prepared a clear answer for the user.</p><ul><li>Heading recognized</li><li>Paragraph structure retained</li><li>Ready to review</li></ul>"
        property string selectedHistoryDetailHtml: "<p>Source: local capture.</p><p>Saved for later review.</p>"
        property string selectedHistoryId: "preview-result"

        property var deviceHealthModel: ListModel {
            ListElement { key: "overall"; section: "Overview"; title: "Overall device status"; value: "Ready"; message: "All shared checks are currently healthy."; tone: "success" }
            ListElement { key: "cpu"; section: "Performance"; title: "CPU temperature"; value: "49 °C"; message: "Within the configured range."; tone: "success" }
            ListElement { key: "memory"; section: "Performance"; title: "Memory usage"; value: "38% used"; message: "Memory is available."; tone: "success" }
            ListElement { key: "storage"; section: "Performance"; title: "Storage usage"; value: "31% used"; message: "Enough private storage is available."; tone: "success" }
            ListElement { key: "wifi"; section: "Connection"; title: "Wi-Fi connection"; value: "Connected"; message: "NetworkManager reports a connection."; tone: "success" }
            ListElement { key: "camera"; section: "Camera"; title: "Camera availability"; value: "Connected"; message: "Mock camera preview is active."; tone: "success" }
            ListElement { key: "focus"; section: "Camera controls"; title: "Autofocus"; value: "Available"; message: "Available for this camera."; tone: "success" }
            ListElement { key: "version"; section: "Service"; title: "Application version"; value: "1.0.0"; message: "The native VisionDesk service is running."; tone: "success" }
        }

        property var captureReview: QtObject {
            id: previewReview
            property string state: "reviewing"
            property string captureProfile: "document"
            property string captureProfileLabel: "Document"
            property int sourceRevision: 1
            property bool hasCapturedImage: true
            property real cropX: 0.12
            property real cropY: 0.10
            property real cropWidth: 0.76
            property real cropHeight: 0.80
            property bool perspectiveAvailable: true
            property bool perspectiveActive: false
            property var perspectivePoints: [{"x": 0.18, "y": 0.16}, {"x": 0.83, "y": 0.13}, {"x": 0.86, "y": 0.84}, {"x": 0.15, "y": 0.87}]
            property bool autofocusSupported: false
            property bool exposureSupported: false
            property string autofocusSupportMessage: "Not supported by this camera"
            property string exposureSupportMessage: "Not supported by this camera"
            property real previewZoomX: 0.12
            property real previewZoomY: 0.12
            property real previewZoomWidth: 0.76
            property real previewZoomHeight: 0.76
            property bool previewZoomActive: true
            property bool canSubmit: true
            property var captureProfilesModel: ListModel {
                ListElement { id: "document"; label: "Document"; description: "Page alignment" }
                ListElement { id: "computer_screen"; label: "Computer Screen"; description: "Screen safe area" }
                ListElement { id: "diagram"; label: "Diagram"; description: "Diagram guide" }
            }
            property var cameraCapabilitiesModel: ListModel {}
            function setCaptureProfile(profile) { captureProfile = profile }
            function zoomPreviewIn() { previewZoomActive = true }
            function zoomPreviewOut() { previewZoomActive = true }
            function resetPreviewZoom() { previewZoomActive = false }
            function setPreviewZoomRegion(x, y, width, height) { previewZoomX = x; previewZoomY = y; previewZoomWidth = width; previewZoomHeight = height }
            function setCropNormalized(x, y, width, height) { cropX = x; cropY = y; cropWidth = width; cropHeight = height }
            function resetCrop() { cropX = 0; cropY = 0; cropWidth = 1; cropHeight = 1 }
            function acceptPerspective() { perspectiveActive = true }
            function rejectPerspective() { perspectiveActive = false }
        }

        property var healthMetricsModel: ListModel {
            ListElement { label: "SYS"; value: "Ready"; state: "healthy"; message: "System services available." }
            ListElement { label: "CPU"; value: "49 C"; state: "healthy"; message: "Thermals are within range." }
            ListElement { label: "RAM"; value: "38%"; state: "healthy"; message: "Memory is available." }
            ListElement { label: "WIFI"; value: "Online"; state: "healthy"; message: "NetworkManager connection is active." }
            ListElement { label: "CAM"; value: "Ready"; state: "healthy"; message: "Camera backend is available." }
        }

        property var modeCardsModel: ListModel {
            ListElement { mode_id: "read_text"; name: "Read Text"; description: "Hear printed text clearly" }
            ListElement { mode_id: "summarize_document"; name: "Summarize Document"; description: "Get the key points quickly" }
            ListElement { mode_id: "analyze_image"; name: "Analyze Image"; description: "Understand what you see" }
            ListElement { mode_id: "professional_assistant"; name: "Professional Assistant"; description: "Write, plan, and organize" }
            ListElement { mode_id: "solve_problem"; name: "Solve Problem"; description: "Work through questions step by step" }
        }

        property var cameraAnalysisModel: ListModel {
            ListElement { key: "Camera"; label: "Ready"; status: "healthy" }
            ListElement { key: "Autofocus"; label: "Continuous"; status: "healthy" }
            ListElement { key: "Lighting"; label: "Balanced"; status: "healthy" }
            ListElement { key: "Sharpness"; label: "Good"; status: "healthy" }
        }

        property var historyEntriesModel: ListModel {
            ListElement { entry_id: "one"; mode_label: "Read Text"; status: "done"; created_at: "Today, 10:42"; summary: "A clear reading of the captured document is available."; model_used: "gpt-4.1-mini"; duration_seconds: 2.1; retry_status: "" }
            ListElement { entry_id: "two"; mode_label: "Analyze Image"; status: "done"; created_at: "Yesterday, 16:19"; summary: "A concise visual analysis was saved for review."; model_used: "gpt-4.1-mini"; duration_seconds: 3.4; retry_status: "" }
            ListElement { entry_id: "three"; mode_label: "Solve Problem"; status: "queued"; created_at: "Yesterday, 13:06"; summary: "This request is saved and will retry when the network is available."; model_used: ""; duration_seconds: 0; retry_status: "queued" }
        }

        function selectMode(mode) { selectedMode = mode }
        function openHistory() { }
        function runConfigurationReset() { }
        function runFullFactoryReset(removeWifi) { }
        function deleteAllData() { }
        function goBack() { }
        function capture() { }
        function confirmReviewedImage() { }
        function retakeCapture() { }
        function openSettings() { }
        function openDeviceHealth() { }
        function refreshDeviceHealth() { }
        function clearResult() { }
        function retry() { }
        function openHistoryItem(entryId) { }
        function clearHistory() { }
        function deleteHistoryItem(entryId) { }
    }

    Item {
        id: shell
        anchors.fill: parent
        anchors.margins: 20

        AppHeader {
            id: header
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            theme: appTheme
            controller: mockController
        }

        Rectangle {
            id: divider
            anchors.top: header.bottom
            anchors.topMargin: 16
            anchors.left: parent.left
            anchors.right: parent.right
            height: appTheme.dividerStrong
            color: appTheme.primary
        }

        Loader {
            id: screenLoader
            anchors.top: divider.bottom
            anchors.topMargin: 18
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            sourceComponent: {
                switch (window.requestedScreen) {
                case "camera": return cameraComponent
                case "review": return reviewComponent
                case "settings": return settingsComponent
                case "device_health": return deviceHealthComponent
                case "processing": return processingComponent
                case "result": return resultComponent
                case "error": return errorComponent
                case "history": return historyComponent
                case "history_detail": return historyDetailComponent
                case "device_actions": return deviceActionsComponent
                default: return homeComponent
                }
            }

            onLoaded: {
                if (window.requestedScreen === "device_actions" && item) {
                    Qt.callLater(function() { item.openDeviceActionsPreview() })
                }
            }
        }
    }

    Component { id: homeComponent; HomeScreen { theme: appTheme; controller: mockController } }
    Component {
        id: deviceActionsComponent
        HomeScreen {
            theme: appTheme
            controller: mockController
        }
    }
    Component { id: cameraComponent; CameraScreen { theme: appTheme; controller: mockController } }
    Component { id: reviewComponent; ReviewScreen { theme: appTheme; controller: mockController } }
    Component { id: settingsComponent; SettingsScreen { theme: appTheme; controller: mockController } }
    Component { id: deviceHealthComponent; DeviceHealthScreen { theme: appTheme; controller: mockController } }
    Component { id: processingComponent; ProcessingScreen { theme: appTheme; controller: mockController } }
    Component { id: resultComponent; ResultScreen { theme: appTheme; controller: mockController } }
    Component { id: errorComponent; ErrorScreen { theme: appTheme; controller: mockController } }
    Component { id: historyComponent; HistoryScreen { theme: appTheme; controller: mockController } }
    Component { id: historyDetailComponent; HistoryDetailScreen { theme: appTheme; controller: mockController } }

    Timer {
        interval: 1400
        running: String(window.outputPath || "").length > 0
        repeat: false
        onTriggered: window.capturePreview()
    }
}
