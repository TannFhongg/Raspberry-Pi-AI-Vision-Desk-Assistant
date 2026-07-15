import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../../qt_app/qml/theme"
import "../../qt_app/qml/components"
import "../../qt_app/qml/screens"

Rectangle {
    id: window
    width: 1366
    height: 768
    color: appTheme.setupPageBackground

    property string requestedStep: "welcome"
    property url outputPath: ""
    readonly property var setupSteps: ["welcome", "wifi", "openai", "camera", "gpio", "finish"]

    function normalizeStep(step) {
        return setupSteps.indexOf(step) >= 0 ? step : "welcome"
    }

    function resolvedOutputPath() {
        let path = String(window.outputPath || "")
        if (path.indexOf("file:///") === 0) {
            path = path.substring(8)
        } else if (path.indexOf("file://") === 0) {
            path = path.substring(7)
        }
        return decodeURIComponent(path)
    }

    function capturePreview() {
        const outputFile = window.resolvedOutputPath()
        if (!outputFile.length) {
            return
        }
        shell.grabToImage(function(result) {
            console.log("Capturing setup preview", requestedStep, shell.width, shell.height, outputFile)
            const saved = result.saveToFile(outputFile)
            if (result.image) {
                console.log("Captured image size", result.image.width, result.image.height, "saved=", saved)
            }
            if (!saved) {
                console.log("Failed to save preview to " + outputFile)
            }
            Qt.quit()
        })
    }

    Theme {
        id: appTheme
    }

    QtObject {
        id: mockController

        property string currentScreen: "setup"
        property string setupCurrentStep: window.normalizeStep(String(window.requestedStep || "").toLowerCase())
        property string setupRuntimeContext: "desktop_mock"
        property string setupFinishMessage: "Setup complete. VisionDesk will relaunch into Home after the wizard finishes."
        property string setupWarningsText: ""
        property string globalStatusText: "Setup required"
        property string globalStatusTone: "warning"
        property bool setupHasApiKey: true
        property bool setupApiKeyVerified: true
        property bool setupApiKeyBusy: false
        property string setupApiKeyDisplayText: setupHasApiKey ? "API key saved" : "No API key configured"
        property string setupDeviceChecksStatus: "pass"
        property bool setupDeviceChecksBusy: false
        property string setupDeviceChecksMessage: "All required first-boot diagnostics passed."
        property string setupWifiMessage: "Connected to VisionDesk Lab on 5 GHz."
        property string setupWifiScanStatus: "pass"
        property string setupWifiStatus: "pass"
        property string setupWifiSsid: "VisionDesk Lab"
        property string setupOpenAiMessage: "API key saved to the protected environment file and verified successfully."
        property string setupOpenAiStatus: "pass"
        property string setupCameraMessage: "Camera test completed successfully. Live capture is ready."
        property string setupCameraStatus: "pass"
        property string setupCameraAutofocusMode: "continuous"
        property string setupCameraResolutionLabel: "1920 x 1080"
        property string setupCameraPreviewFpsLabel: "30"
        property string setupCameraExposureLabel: "auto"
        property string setupGpioMessage: "All configured buttons responded to a press."
        property string setupGpioStatus: "pass"
        property bool setupGpioActive: false
        property bool cameraPreviewAvailable: false
        property int cameraPreviewRevision: 0
        property string cameraPreviewState: "Standby"
        property string cameraPreviewTitle: "Live Preview Placeholder"
        property string cameraPreviewMessage: "This preview scene renders the new layout without the live camera provider."
        property bool setupReadyToFinish: setupWifiStatus === "pass"
                                           && setupApiKeyVerified
                                           && setupCameraStatus === "pass"
                                           && setupGpioStatus === "pass"

        property var healthMetricsModel: ListModel {
            id: healthMetrics
            ListElement { label: "SYS"; value: "Ready"; state: "healthy"; message: "System services available." }
            ListElement { label: "CPU"; value: "52 C"; state: "healthy"; message: "Thermals are within range." }
            ListElement { label: "RAM"; value: "41%"; state: "healthy"; message: "Plenty of memory remains." }
            ListElement { label: "WIFI"; value: "Online"; state: "healthy"; message: "NetworkManager connection is active." }
            ListElement { label: "CAM"; value: "Ready"; state: "healthy"; message: "Camera backend is available." }
        }

        property var deviceChecksModel: ListModel {
            id: deviceChecks
            ListElement { name: "config_access"; status: "pass"; message: "Device config is readable."; required: true }
            ListElement { name: "writable_storage"; status: "pass"; message: "Persistent storage paths are writable."; required: true }
            ListElement { name: "display_session"; status: "pass"; message: "Desktop session is ready for kiosk launch."; required: true }
            ListElement { name: "camera_backend"; status: "pass"; message: "Camera backend can open the configured device."; required: true }
            ListElement { name: "gpio_access"; status: "pass"; message: "GPIO access is available."; required: true }
            ListElement { name: "network_manager"; status: "pass"; message: "NetworkManager is installed and active."; required: true }
        }

        property var wifiNetworksModel: ListModel {
            id: wifiNetworks
            ListElement { ssid: "VisionDesk Lab"; signal: 92; security: "wpa2" }
            ListElement { ssid: "Office-5G"; signal: 81; security: "wpa2" }
            ListElement { ssid: "Technician Hotspot"; signal: 67; security: "wpa2" }
            ListElement { ssid: "Hidden staging"; signal: 54; security: "" }
        }

        property var gpioRequirementsModel: ListModel {
            id: gpioRequirements
            ListElement { label: "Capture"; pin: 17; pressed: true }
            ListElement { label: "Mode Read Text"; pin: 5; pressed: true }
            ListElement { label: "Mode Summarize"; pin: 6; pressed: true }
            ListElement { label: "Mode Analyze Image"; pin: 13; pressed: true }
        }

        function setMetric(index, value, state, message) {
            healthMetrics.setProperty(index, "value", value)
            healthMetrics.setProperty(index, "state", state)
            healthMetrics.setProperty(index, "message", message)
        }

        function setAllPressed(pressed) {
            for (let i = 0; i < gpioRequirements.count; i += 1) {
                gpioRequirements.setProperty(i, "pressed", pressed)
            }
        }

        function setPressedState(flags) {
            for (let i = 0; i < gpioRequirements.count; i += 1) {
                gpioRequirements.setProperty(i, "pressed", !!flags[i])
            }
        }

        function resetScenario() {
            setupFinishMessage = "Setup complete. VisionDesk will relaunch into Home after the wizard finishes."
            setupWarningsText = ""
            setupHasApiKey = true
            setupApiKeyVerified = true
            setupDeviceChecksStatus = "pass"
            setupDeviceChecksMessage = "All required first-boot diagnostics passed."
            setupWifiMessage = "Connected to VisionDesk Lab on 5 GHz."
            setupWifiScanStatus = "pass"
            setupWifiStatus = "pass"
            setupWifiSsid = "VisionDesk Lab"
            setupOpenAiMessage = "API key saved to the protected environment file and verified successfully."
            setupOpenAiStatus = "pass"
            setupCameraMessage = "Camera test completed successfully. Live capture is ready."
            setupCameraStatus = "pass"
            setupCameraAutofocusMode = "continuous"
            setupCameraResolutionLabel = "1920 x 1080"
            setupCameraPreviewFpsLabel = "30"
            setupCameraExposureLabel = "auto"
            setupGpioMessage = "All configured buttons responded to a press."
            setupGpioStatus = "pass"
            setupGpioActive = false
            cameraPreviewAvailable = false
            cameraPreviewRevision = 0
            cameraPreviewState = "Standby"
            cameraPreviewTitle = "Live Preview Placeholder"
            cameraPreviewMessage = "This preview scene renders the new layout without the live camera provider."
            setMetric(0, "Ready", "healthy", "System services available.")
            setMetric(1, "52 C", "healthy", "Thermals are within range.")
            setMetric(2, "41%", "healthy", "Plenty of memory remains.")
            setMetric(3, "Online", "healthy", "NetworkManager connection is active.")
            setMetric(4, "Ready", "healthy", "Camera backend is available.")
            setAllPressed(true)
        }

        function applyScenario(step) {
            resetScenario()
            if (step === "welcome") {
                setupWifiStatus = "idle"
                setupWifiSsid = ""
                setupWifiMessage = ""
                setupOpenAiStatus = "idle"
                setupOpenAiMessage = ""
                setupHasApiKey = false
                setupApiKeyVerified = false
                setupCameraStatus = "idle"
                setupCameraMessage = "Camera test will run later in the wizard."
                setupGpioStatus = "idle"
                setupGpioMessage = "GPIO verification happens after the camera step."
                setupWarningsText = "Finish remains locked until Wi-Fi, OpenAI, camera, and GPIO all pass."
                setMetric(0, "Preparing", "warning", "System setup is still in progress.")
                setMetric(3, "Pending", "warning", "Wi-Fi has not been configured yet.")
                setMetric(4, "Standby", "warning", "Camera test still pending.")
                setAllPressed(false)
            } else if (step === "wifi") {
                setupWifiStatus = "pass"
                setupWifiMessage = "Connected to VisionDesk Lab on 5 GHz."
                setupOpenAiStatus = "idle"
                setupOpenAiMessage = ""
                setupHasApiKey = false
                setupApiKeyVerified = false
                setupCameraStatus = "idle"
                setupCameraMessage = "Camera test pending."
                setupGpioStatus = "idle"
                setupGpioMessage = "GPIO test pending."
                setMetric(3, "Online", "healthy", "NetworkManager connection is active.")
                setMetric(4, "Standby", "warning", "Camera test still pending.")
                setAllPressed(false)
            } else if (step === "openai") {
                setupOpenAiStatus = "pass"
                setupOpenAiMessage = "API key saved to the protected environment file and verified successfully."
                setupHasApiKey = true
                setupApiKeyVerified = true
                setupCameraStatus = "idle"
                setupCameraMessage = "Camera test pending."
                setupGpioStatus = "idle"
                setupGpioMessage = "GPIO test pending."
                setMetric(4, "Standby", "warning", "Camera test still pending.")
                setAllPressed(false)
            } else if (step === "camera") {
                setupCameraStatus = "running"
                setupCameraMessage = "Preview ready. Run the capture test to confirm one-shot capture."
                cameraPreviewState = "Preview ready"
                cameraPreviewTitle = "Camera Preview"
                cameraPreviewMessage = "A live preview is expected here on device. This mock keeps the layout renderable in CI and desktop review."
                setupGpioStatus = "idle"
                setupGpioMessage = "GPIO test pending."
                setMetric(4, "Preview", "warning", "Camera preview is available in the live app.")
                setAllPressed(false)
            } else if (step === "gpio") {
                setupGpioStatus = "running"
                setupGpioActive = true
                setupGpioMessage = "Press the remaining hardware buttons to complete verification."
                setPressedState([true, true, false, false])
            } else if (step === "finish") {
                setupFinishMessage = "All required setup gates passed. Restart into VisionDesk Home."
                setupWarningsText = ""
                setMetric(4, "Ready", "healthy", "Camera backend is available.")
                setAllPressed(true)
            }
        }

        onSetupCurrentStepChanged: applyScenario(setupCurrentStep)

        function goToSetupStep(step) {
            setupCurrentStep = window.normalizeStep(step)
        }

        function goToSetupNextStep() {
            const currentIndex = window.setupSteps.indexOf(setupCurrentStep)
            if (currentIndex < 0 || currentIndex >= window.setupSteps.length - 1) {
                return
            }
            setupCurrentStep = window.setupSteps[currentIndex + 1]
        }

        function goToSetupPreviousStep() {
            const currentIndex = window.setupSteps.indexOf(setupCurrentStep)
            if (currentIndex <= 0) {
                return
            }
            setupCurrentStep = window.setupSteps[currentIndex - 1]
        }

        function runSetupDeviceChecks() {
            setupDeviceChecksStatus = "pass"
            setupDeviceChecksMessage = "All required first-boot diagnostics passed."
        }

        function scanWifi() {
            setupWifiScanStatus = "pass"
            setupWifiMessage = "Found 4 nearby Wi-Fi networks."
        }

        function connectWifi(selectedSsid, manualSsid, password) {
            const resolvedSsid = (manualSsid || selectedSsid || "").trim()
            if (!resolvedSsid.length) {
                setupWifiStatus = "fail"
                setupWifiMessage = "Enter or select an SSID before connecting."
                return
            }
            setupWifiStatus = "pass"
            setupWifiSsid = resolvedSsid
            setupWifiMessage = password.length === 0
                               ? "Connected to open network " + resolvedSsid + "."
                               : "Connected to " + resolvedSsid + " successfully."
        }

        function verifyApiKey(apiKey) {
            const trimmed = (apiKey || "").trim()
            if (trimmed.indexOf("sk-") !== 0) {
                setupHasApiKey = false
                setupApiKeyVerified = false
                setupOpenAiStatus = "fail"
                setupOpenAiMessage = "Enter a valid OPENAI_API_KEY starting with sk- before continuing."
                return
            }
            setupHasApiKey = true
            setupApiKeyVerified = true
            setupOpenAiStatus = "pass"
            setupOpenAiMessage = "API key saved to the protected environment file and verified successfully."
        }

        function clearApiKey() {
            setupHasApiKey = false
            setupApiKeyVerified = false
            setupOpenAiStatus = "idle"
            setupOpenAiMessage = "OpenAI API key cleared. Enter a new key to continue."
        }

        function runCameraTest() {
            setupCameraStatus = "pass"
            setupCameraMessage = "Camera test completed successfully. Live capture is ready."
            cameraPreviewState = "Validated"
            setMetric(4, "Ready", "healthy", "Camera backend is available.")
        }

        function startGpioTest() {
            setupGpioActive = true
            setupGpioStatus = "running"
            setupGpioMessage = "GPIO listener active. Press the remaining hardware buttons."
            setPressedState([true, true, false, false])
        }

        function stopGpioTest() {
            setupGpioActive = false
            setupGpioStatus = "pass"
            setupGpioMessage = "GPIO verification stopped after all configured buttons responded."
            setAllPressed(true)
        }

        function finishSetup() {
            setupFinishMessage = "Setup complete. VisionDesk would restart into Home now."
        }

        Component.onCompleted: applyScenario(setupCurrentStep)
    }

    Timer {
        interval: 1200
        running: window.resolvedOutputPath().length > 0
        repeat: false
        onTriggered: window.capturePreview()
    }

    Rectangle {
        anchors.fill: parent
        color: appTheme.setupPageBackground

        Item {
            id: shell
            anchors.fill: parent
            anchors.margins: 20

            HeaderBar {
                id: headerBar
                theme: appTheme
                controller: mockController
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
            }

            Rectangle {
                id: divider
                anchors.top: headerBar.bottom
                anchors.topMargin: 16
                anchors.left: parent.left
                anchors.right: parent.right
                height: appTheme.dividerStrong
                color: appTheme.primary
            }

            SetupScreen {
                anchors.top: divider.bottom
                anchors.topMargin: 18
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                theme: appTheme
                controller: mockController
            }
        }
    }
}
